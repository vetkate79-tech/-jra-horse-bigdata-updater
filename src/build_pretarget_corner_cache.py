#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,csv,json,re,sys,urllib.parse,urllib.request
from collections import defaultdict
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, UA

CARDS=Path('docs/data/race_cards.json')
OUT=Path('docs/data/pretarget-corner-cache.json')
STATUS=Path('status/pretarget-corner-cache.json')
BASE='https://www.jra.go.jp'
CUTOFF='2026-08-29'

def canonical_horse_id(value):
    s=str(value or '')
    nums=''.join(re.findall(r'\d+',s))
    # JRA profile horse IDs are the trailing 10 digits. Internal pw01dud IDs
    # may contain a leading route/version prefix before the same 10-digit ID.
    return nums[-10:] if len(nums)>=10 else nums

def parse_date(s):
    m=re.search(r'(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})',str(s or ''))
    if not m:return ''
    return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'

def profile_race_links(hid):
    html=request_profile(hid)
    soup=BeautifulSoup(html,'html.parser')
    rows=[]
    # history table rows contain date text + official race-result link
    for tr in soup.find_all('tr'):
        text=' '.join(tr.stripped_strings)
        dt=parse_date(text)
        if not dt or dt>=CUTOFF:continue
        a=tr.find('a',href=True)
        if not a or 'accessS.html?CNAME=pw01sde' not in a.get('href',''):continue
        rows.append({'date':dt,'url':urllib.parse.urljoin(BASE,a['href'])})
    # fallback: links in document order when row/date extraction fails
    if not rows:
        links=[urllib.parse.urljoin(BASE,a['href']) for a in soup.find_all('a',href=True) if 'accessS.html?CNAME=pw01sde' in a.get('href','')]
        for u in links[:8]:rows.append({'date':'','url':u})
    seen=set();out=[]
    for x in rows:
        if x['url'] in seen:continue
        seen.add(x['url']);out.append(x)
        if len(out)>=8:break
    return out

def decode(raw):
    for enc in ('utf-8','cp932','euc_jp'):
        try:
            t=raw.decode(enc)
            if '着順' in t or '通過' in t or 'コーナー' in t:return t
        except:pass
    return raw.decode('cp932','replace')

def fetch_result(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Referer':BASE+'/','Accept-Language':'ja'})
    with urllib.request.urlopen(req,timeout=30) as r:raw=r.read()
    return BeautifulSoup(decode(raw),'html.parser')

def race_horse_corners(url):
    soup=fetch_result(url)
    out={}
    # JRA result table: identify rows containing horse number/name and corner/passing-order-like cells.
    for tr in soup.find_all('tr'):
        cells=[' '.join(c.stripped_strings) for c in tr.find_all(['th','td'])]
        if len(cells)<4:continue
        joined=' | '.join(cells)
        # horse number: small integer cell; horse link usually has CNAME=pw01dud or horse id in href
        horse_anchor=tr.find('a',href=True)
        hid=''
        if horse_anchor:
            href=horse_anchor.get('href','')
            m=re.search(r'(?:JRA_ID|horse_id|CNAME=pw01dud[^#?]*).*?(\d{10})',href)
            if m:hid=m.group(1)
            if not hid:
                m=re.search(r'(\d{10})',href)
                if m:hid=m.group(1)
        # extract plausible horse number and corner sequence (e.g. 3-3 / 7-6-5-4)
        no=''
        for c in cells[:5]:
            if re.fullmatch(r'\d{1,2}',c):
                v=int(c)
                if 1<=v<=20:no=str(v);break
        corner_candidates=[]
        for c in cells:
            if re.fullmatch(r'\d{1,2}(?:[-－ー]\d{1,2}){1,3}',c.replace(' ','').replace('→','-')):
                corner_candidates.append(c)
        if not corner_candidates:
            # sometimes passing order is a single integer for sprint/straight courses
            labels=' '.join(soup.find_all(string=re.compile('通過|コーナー'))[:3])
        if hid and corner_candidates:
            cp=corner_candidates[-1]
            out[canonical_horse_id(hid)]={'horse_no':no,'corner_positions':cp,'cells':cells[:20]}
    return out

def main():
    cards=json.loads(CARDS.read_text())
    ids=sorted({str(h.get('horse_id') or '') for r in cards.get('races',[]) for h in r.get('horses',[]) if h.get('horse_id')})
    profiles={};errors=[]
    def pjob(h):return h,profile_race_links(h)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        fs={ex.submit(pjob,h):h for h in ids}
        for i,fu in enumerate(concurrent.futures.as_completed(fs),1):
            hid=fs[fu]
            try:k,v=fu.result();profiles[k]=v
            except Exception as e:profiles[hid]=[];errors.append({'stage':'profile','horse_id':hid,'error':repr(e)})
            if i%100==0:print('profiles',i,len(ids),flush=True)
    urls=sorted({x['url'] for xs in profiles.values() for x in xs})
    result_cache={}
    def rjob(u):return u,race_horse_corners(u)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        fs={ex.submit(rjob,u):u for u in urls}
        for i,fu in enumerate(concurrent.futures.as_completed(fs),1):
            u=fs[fu]
            try:k,v=fu.result();result_cache[k]=v
            except Exception as e:result_cache[u]={};errors.append({'stage':'result','url':u,'error':repr(e)})
            if i%250==0:print('results',i,len(urls),flush=True)
    horses={};resolved=0
    for hid,xs in profiles.items():
        ss=[]
        for x in xs:
            rr=result_cache.get(x['url'],{}).get(canonical_horse_id(hid))
            if rr and rr.get('corner_positions'):
                ss.append({'date':x['date'],'url':x['url'],'corner_positions':rr['corner_positions']})
        if ss:resolved+=1
        horses[hid]=ss
    payload={'source':'JRA_OFFICIAL_PROFILE_LINKS_AND_RESULTS','cutoff_exclusive':CUTOFF,'horse_count':len(ids),'horse_with_corner_history':resolved,'race_urls_fetched':len(urls),'errors':errors,'horses':horses}
    txt=json.dumps(payload,ensure_ascii=False,indent=2);OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({k:payload[k] for k in ('source','cutoff_exclusive','horse_count','horse_with_corner_history','race_urls_fetched') }|{'error_count':len(errors)},ensure_ascii=False,indent=2));print(json.dumps({'horses':len(ids),'resolved':resolved,'urls':len(urls),'errors':len(errors)},ensure_ascii=False))
if __name__=='__main__':main()
