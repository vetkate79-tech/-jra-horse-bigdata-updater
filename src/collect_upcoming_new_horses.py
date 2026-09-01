#!/usr/bin/env python3
"""Discover upcoming JRA racecards and register debut horses before racing.

Discovery strategy:
- inspect the JRA home page for current-week accessD racecard links
- use one discovered race as a seed per venue/day
- expand to all race links exposed by that racecard page
- keep only 新馬 / メイクデビュー races
- merge horse IDs/names into the unified public catalog before debut

No prediction, odds or inferred training state is created here.
"""
from __future__ import annotations
import datetime as dt, html as html_lib, json, re, time, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path
from bs4 import BeautifulSoup
import sys
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, parse_profile

ROOT=Path('.')
CAT=ROOT/'docs/data/horses/catalog.json'
OUT=ROOT/'docs/data/upcoming_new_horses.json'
STATUS=ROOT/'status/upcoming_new_horses.json'
HOME='https://www.jra.go.jp/'
ENTRY='https://www.jra.go.jp/JRADB/accessD.html'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
META=re.compile(r'pw01dde(?:01|10)(?P<course>\d{2})(?P<year>\d{4})(?P<meeting>\d{2})(?P<day>\d{2})(?P<race>\d{2})(?P<date>\d{8})')
LINK=re.compile(r'pw01dde(?:01|10)\d{20}/[A-Fa-f0-9]{2}')
HORSE_ID=re.compile(r'pw01dud\d{12}/[A-Fa-f0-9]{2}')
COURSE={'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京','06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}

def fetch(url,retries=4):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Referer':HOME,'Accept-Language':'ja,en-US;q=0.7'})
    for a in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=45) as r: raw=r.read()
            for enc in ('utf-8','cp932'):
                try:return raw.decode(enc)
                except UnicodeDecodeError:pass
            return raw.decode('cp932','replace')
        except Exception:
            if a==retries-1:raise
            time.sleep(1.5*(a+1))

def cname_url(cname): return ENTRY+'?CNAME='+urllib.parse.quote(cname,safe='')

def extract_links(text):
    x=urllib.parse.unquote(html_lib.unescape(text))
    return list(dict.fromkeys(LINK.findall(x)))

def date_of(c):
    m=META.search(c)
    if not m:return None
    d=m.group('date')
    return dt.date(int(d[:4]),int(d[4:6]),int(d[6:]))

def current_week_seeds():
    raw=fetch(HOME)
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    end=today+dt.timedelta(days=7)
    seeds={}
    for c in extract_links(raw):
        m=META.search(c); d=date_of(c)
        if not m or not d or not(today<=d<=end):continue
        key=(m.group('date'),m.group('course'))
        seeds.setdefault(key,c)
    return seeds

def race_title(soup):
    for sel in ('main h2','#main h2','.race_num + h2','h2'):
        n=soup.select_one(sel)
        if n:
            t=' '.join(n.stripped_strings)
            if t:return t
    text=' '.join(soup.stripped_strings)
    m=re.search(r'(メイクデビュー[^ ]*|\d歳新馬|新馬)',text)
    return m.group(1) if m else ''

def horse_rows(cname,html):
    soup=BeautifulSoup(html,'html.parser'); title=race_title(soup)
    if '新馬' not in title and 'メイクデビュー' not in title:return None
    m=META.search(cname); date=m.group('date'); date=f'{date[:4]}-{date[4:6]}-{date[6:]}'
    race_no=int(m.group('race')); track=COURSE.get(m.group('course'),m.group('course'))
    horses=[];seen=set()
    for a in soup.find_all('a'):
        href=urllib.parse.unquote(html_lib.unescape(a.get('href','')))
        hm=HORSE_ID.search(href)
        if not hm:continue
        hid=hm.group(0); name=' '.join(a.stripped_strings).strip()
        if not name or hid in seen:continue
        seen.add(hid);tr=a.find_parent('tr');rowtxt=' '.join(tr.stripped_strings) if tr else ''
        no=''
        if tr:
            cells=[' '.join(x.stripped_strings) for x in tr.find_all(['th','td'])]
            for x in cells[:3]:
                mm=re.fullmatch(r'\d{1,2}',x.strip())
                if mm:no=mm.group(0)
        horses.append({'horse_id':hid,'horse_name':name,'horse_no':no,'row_text':rowtxt})
    return {'race_id':META.search(cname).group(0),'date':date,'track':track,'race_no':race_no,'race_name':title,'source_url':cname_url(cname),'horses':horses}

def load_catalog():
    if not CAT.exists():return {'summary':{},'horses':[]}
    return json.loads(CAT.read_text(encoding='utf-8'))

def merge(races):
    doc=load_catalog();hs=doc.get('horses',[]);by_id={h.get('horse_id'):h for h in hs if h.get('horse_id')};added=updated=0;profile_errors=[]
    for r in races:
        for x in r['horses']:
            h=by_id.get(x['horse_id'])
            if h is None:
                h={'horse_name':x['horse_name'],'horse_id':x['horse_id'],'sex_age':'','trainer':'','win_rate':None,'quinella_rate':None,'show_rate':None,'target_starts':[],'tags':[]}
                hs.append(h);by_id[x['horse_id']]=h;added+=1
            else:updated+=1
            h['horse_name']=x['horse_name'] or h.get('horse_name','')
            h['current_class']='NEW';h['current_class_label']='新馬'
            tags=set(h.get('tags') or []);tags.update({'NEW','NEW_ENTRY'});h['tags']=sorted(tags)
            starts=h.setdefault('upcoming_starts',[])
            item={k:r[k] for k in ('race_id','date','track','race_no','race_name','source_url')};item['horse_no']=x.get('horse_no','')
            if not any(s.get('race_id')==item['race_id'] for s in starts):starts.append(item)
            try:
                p=parse_profile({'horse_id':x['horse_id'],'horse_name':x['horse_name'],'candidate_sources':{'NEW_ENTRY'}},request_profile(x['horse_id']))
                h['pedigree_summary']={'sire':p.get('sire') or None,'damsire':p.get('damsire') or None,'dam':p.get('dam') or None}
                for k in ('birth_date','breeder','trainer','owner','coat'):
                    if p.get(k):h[k]=p[k]
            except Exception as e:profile_errors.append({'horse_id':x['horse_id'],'horse_name':x['horse_name'],'error':repr(e)})
            h.setdefault('training_summary',None)
    hs.sort(key=lambda h:h.get('horse_name',''))
    s=dict(doc.get('summary') or {});s.update({'unified_horse_count':len(hs),'upcoming_new_horse_added':added,'upcoming_new_horse_updated':updated,'new_horse_registration_policy':'register from verified JRA racecard before debut'})
    doc['summary']=s;doc['horses']=hs;CAT.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    return added,updated,profile_errors

def main():
    STATUS.parent.mkdir(exist_ok=True);OUT.parent.mkdir(parents=True,exist_ok=True)
    seeds=current_week_seeds();races=[];errors=[]
    for key,seed in seeds.items():
        try:
            seed_html=fetch(cname_url(seed));links=extract_links(seed_html)+[seed]
            target=[];seen=set()
            for c in links:
                m=META.search(c)
                if not m or (m.group('date'),m.group('course'))!=key:continue
                logical=(m.group('date'),m.group('course'),m.group('race'))
                if logical in seen:continue
                seen.add(logical);target.append(c)
            for c in target:
                try:
                    rr=horse_rows(c,fetch(cname_url(c)))
                    if rr and rr['horses']:races.append(rr)
                except Exception as e:errors.append({'race':c,'error':repr(e)})
        except Exception as e:errors.append({'seed':seed,'error':repr(e)})
    uniq={r['race_id']:r for r in races};races=sorted(uniq.values(),key=lambda r:(r['date'],r['track'],r['race_no']))
    added=updated=0;profile_errors=[]
    if races:added,updated,profile_errors=merge(races)
    payload={'source':'JRA_OFFICIAL_UPCOMING_RACECARD','status':'UPDATED' if races else 'NO_UPCOMING_RACECARDS','seed_count':len(seeds),'new_race_count':len(races),'new_runner_rows':sum(len(r['horses']) for r in races),'added_to_master':added,'updated_in_master':updated,'races':races}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    STATUS.write_text(json.dumps({**{k:v for k,v in payload.items() if k!='races'},'errors':errors,'profile_errors':profile_errors},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k!='races'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
