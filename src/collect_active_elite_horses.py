#!/usr/bin/env python3
"""Build active JRA graded/open horse catalogs from official JRA evidence.

Primary source is JRA horse profiles. If the profile page layout prevents reliable
class/grade parsing (for example a zero elite result across a large candidate
pool), fall back to the already-built lightweight master. That master is derived
only from recorded JRA official results plus JRA's official graded-race list.
No inferred or third-party data is introduced.
"""
from __future__ import annotations
import csv,json,os,re,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from io import StringIO
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

ROOT=Path('.');DATA=ROOT/'data';DOCS=ROOT/'docs/data/horses';CACHE=ROOT/'cache/jra_horse_profiles';STATUS=ROOT/'status/active_elite_catalog.json'
BASE='https://www.jra.go.jp/JRADB/accessU.html';UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
WORKERS=max(1,int(os.getenv('ELITE_PROFILE_WORKERS','4')));MAX_PROFILES=int(os.getenv('ELITE_MAX_PROFILES','0'));OPEN_THRESHOLD_YEN=16_000_000
GRADE_PATTERNS=[
 ('G1',re.compile(r'(?<!J[・\-])(?:GⅠ|ＧⅠ|\bG1\b|\bGI\b)',re.I)),
 ('G2',re.compile(r'(?<!J[・\-])(?:GⅡ|ＧⅡ|\bG2\b|\bGII\b)',re.I)),
 ('G3',re.compile(r'(?<!J[・\-])(?:GⅢ|ＧⅢ|\bG3\b|\bGIII\b)',re.I)),
]

def clean(v):
    if v is None:return ''
    s=str(v).strip();return '' if s.lower()=='nan' else s

def read_csv(path):
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def add_candidate(by_id,hid,name,source):
    hid=clean(hid);name=clean(name)
    if not hid:return
    item=by_id.setdefault(hid,{'horse_id':hid,'horse_name':name,'candidate_sources':set()})
    if not item['horse_name'] and name:item['horse_name']=name
    item['candidate_sources'].add(source)

def candidate_pool():
    by_id={}
    for r in read_csv(DATA/'horse_ids_2025.csv'):add_candidate(by_id,r.get('horse_id'),r.get('horse_name'),'2025')
    for r in read_csv(DATA/'race_results_html_2026_weekend.csv'):add_candidate(by_id,r.get('horse_id'),r.get('horse_name'),'2026-08-29/30')
    for r in read_csv(DATA/'current_registered_horse_ids.csv'):add_candidate(by_id,r.get('horse_id'),'','CURRENT_REGISTERED_ROSTER')
    vals=list(by_id.values());vals.sort(key=lambda x:(x['horse_name'] or '~~~~',x['horse_id']))
    return vals[:MAX_PROFILES] if MAX_PROFILES>0 else vals

def profile_url(hid):return BASE+'?CNAME='+urllib.parse.quote(hid,safe='')

def request_profile(hid,retries=4):
    CACHE.mkdir(parents=True,exist_ok=True);safe=re.sub(r'[^A-Za-z0-9_.-]+','_',hid)+'.html';path=CACHE/safe
    if path.exists() and path.stat().st_size>10_000:return path.read_text(encoding='utf-8')
    req=urllib.request.Request(profile_url(hid),headers={'User-Agent':UA,'Referer':'https://www.jra.go.jp/','Accept-Language':'ja,en-US;q=0.7'})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=45) as resp:raw=resp.read()
            if len(raw)<10_000:raise RuntimeError(f'short profile {len(raw)}')
            enc='cp932';head=raw[:3000].lower()
            if b'charset=utf-8' in head or b'charset="utf-8"' in head:enc='utf-8'
            text=raw.decode(enc,'replace');path.write_text(text,encoding='utf-8');return text
        except Exception:
            if attempt==retries-1:raise
            time.sleep(1.5*(attempt+1))
    raise RuntimeError('unreachable')

def html_with_image_labels(html):
    soup=BeautifulSoup(html,'html.parser')
    for img in soup.find_all('img'):
        label=clean(img.get('alt') or img.get('title'))
        if label and re.search(r'G[ⅠⅡⅢ123]|Ｇ[ⅠⅡⅢ]',label,re.I):img.replace_with(' '+label+' ')
    return str(soup)

def money(text,label):
    bare=label.replace('（','').replace('）','').replace('(','').replace(')','')
    pats=[re.escape(label)+r'\s*([0-9０-９,，]+)\s*円',
      r'収得賞金\s*[（(]?\s*平地\s*[）)]?\s*([0-9０-９,，]+)\s*円' if '平地' in bare else r'収得賞金\s*[（(]?\s*障害\s*[）)]?\s*([0-9０-９,，]+)\s*円']
    trans=str.maketrans('０１２３４５６７８９，','0123456789,')
    for pat in pats:
        m=re.search(pat,text,re.I)
        if m:return int(m.group(1).translate(trans).replace(',',''))
    return None

def flat_class_from_prize(prize):
    if prize is None:return 'UNKNOWN'
    if prize>16_000_000:return 'OPEN'
    if prize>10_000_000:return '3WIN'
    if prize>5_000_000:return '2WIN'
    if prize>0:return '1WIN'
    return 'ZERO'

def field_between(text,label,next_labels):
    nxt='|'.join(re.escape(x) for x in next_labels);m=re.search(re.escape(label)+r'\s*(.*?)\s*(?='+nxt+r')',text,re.S)
    return re.sub(r'\s+',' ',m.group(1)).strip() if m else ''

def profile_name(soup,text,fallback=''):
    if fallback:return fallback
    for sel in ('.horse_name','.name_horse','.horse-name','h1 .name','h2 .name'):
        node=soup.select_one(sel)
        if node:
            v=re.sub(r'\s+','',node.get_text(' ',strip=True))
            if v and v!='競走馬情報':return v
    m=re.search(r'競走馬情報\s*(.*?)\s*[A-Za-z][A-Za-z .\'-]*[（(]JPN[）)]',text)
    if m:
        parts=[p for p in re.findall(r'[一-龯々〆ヵヶぁ-んァ-ヶー・]+',m.group(1)) if p!='競走馬情報']
        if parts:return max(parts,key=len)
    return ''

def normalized_tables(html):
    try:tables=pd.read_html(StringIO(html_with_image_labels(html)))
    except Exception:return []
    out=[]
    for t in tables:
        cols=[]
        for c in t.columns:
            if isinstance(c,tuple):c=' '.join(str(x) for x in c if str(x)!='nan')
            cols.append(re.sub(r'\s+','',str(c)))
        t.columns=cols;out.append(t)
    return out

def grade_name(text):
    for grade,pat in GRADE_PATTERNS:
        if pat.search(text):return grade
    return ''

def flat_summary_stats(text):
    """Read JRA's official 平地レース合計 row when present.

    This is preferred for career starts/wins because it is already the JRA
    aggregate and is independent of individual race-table layout.
    """
    m=re.search(r'平地レース合計(.*?)(?:障害レース合計|コース別成績)',text,re.S)
    if not m:return None
    part=m.group(1)
    h=re.search(r'3着\s*内率',part)
    if h:part=part[h.end():]
    nums=re.findall(r'(?<![\d.])(\d+)(?![\d.])',part)
    if len(nums)<5:return None
    try:
        wins=int(nums[0]);starts=int(nums[4])
    except Exception:return None
    if starts<0 or wins<0 or wins>starts:return None
    return starts,wins

def race_history(html):
    graded=[];open_rows=[];all_count=0;flat_starts=0;flat_wins=0
    parsed=[]

    # Primary parser: JRA's official "出走レース" HTML table. This does not
    # depend on pandas' inferred headers and survives the current profile layout.
    soup=BeautifulSoup(html_with_image_labels(html),'html.parser')
    for table in soup.find_all('table'):
        trs=table.find_all('tr')
        if not trs:continue
        headers=[]
        header_i=None
        for i,tr in enumerate(trs[:4]):
            hs=[clean(x.get_text(' ',strip=True)).replace(' ','') for x in tr.find_all(['th','td'])]
            if any('レース名' in h for h in hs) and any(('着順' in h or h=='着') for h in hs):
                headers=hs;header_i=i;break
        if header_i is None:continue
        for tr in trs[header_i+1:]:
            cells=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'])]
            if not cells:continue
            vals={headers[i]:cells[i] for i in range(min(len(headers),len(cells)))}
            race_name=next((v for k,v in vals.items() if 'レース名' in k),'')
            if not race_name:continue
            date=next((v for k,v in vals.items() if '年月日' in k or k=='日付'),'')
            venue=next((v for k,v in vals.items() if k in ('場','競馬場')),'')
            finish=next((v for k,v in vals.items() if '着順' in k or k=='着'),'')
            distance=next((v for k,v in vals.items() if '距離' in k),'')
            joined=' '.join(cells)
            parsed.append((date,venue,race_name,finish,distance,joined))

    # Fallback for historical/cached layouts that pandas can still normalize.
    if not parsed:
        for table in normalized_tables(html):
            if not any('レース名' in col for col in table.columns):continue
            for _,row in table.iterrows():
                vals={col:clean(v) for col,v in row.items()};joined=' '.join(vals.values())
                race_name=next((v for col,v in vals.items() if 'レース名' in col),'')
                if not race_name:continue
                date=next((v for col,v in vals.items() if '年月日' in col or col=='日付'),'')
                venue=next((v for col,v in vals.items() if col in ('場','競馬場')),'')
                finish=next((v for col,v in vals.items() if '着順' in col),'')
                distance=next((v for col,v in vals.items() if '距離' in col),'')
                parsed.append((date,venue,race_name,finish,distance,joined))

    seen=set()
    for date,venue,race_name,finish,distance,joined in parsed:
        k=(date,venue,race_name,distance,finish)
        if k in seen:continue
        seen.add(k);all_count+=1
        grade=grade_name(joined)
        is_jump=('障害' in race_name) or ('障' in distance) or ('J・G' in joined) or ('J-G' in joined)
        item={'date':date,'venue':venue,'race_name':race_name,'grade':grade,'finish':finish}
        if not is_jump:
            flat_starts+=1
            try:
                if int(float(str(finish).strip()))==1:flat_wins+=1
            except Exception:
                pass
            if grade:graded.append(item)
            if ('オープン' in race_name or 'リステッド' in joined or 'Listed' in joined or grade):open_rows.append(item)

    return graded,open_rows,all_count,flat_starts,flat_wins

def parse_profile(candidate,html):
    labeled=html_with_image_labels(html);soup=BeautifulSoup(labeled,'html.parser');text=re.sub(r'\s+',' ',soup.get_text(' ',strip=True));erased=re.search(r'抹消年月日\s*(\d{4}年\d{1,2}月\d{1,2}日)',text)
    flat_prize=money(text,'収得賞金（平地）');obstacle_prize=money(text,'収得賞金（障害）');graded,open_history,race_count,flat_starts,flat_wins=race_history(labeled);name=profile_name(soup,text,candidate['horse_name'])
    summary_stats=flat_summary_stats(text)
    if summary_stats is not None:
        flat_starts,flat_wins=summary_stats
    return {'horse_name':name,'horse_id':candidate['horse_id'],'active':not bool(erased),'deregistered_at':erased.group(1) if erased else None,
      'sex':field_between(text,'性別',['馬主名','母']),'age':field_between(text,'馬齢',['調教師名','母の父']),'trainer':field_between(text,'調教師名',['母の父','生年月日']),
      'owner':field_between(text,'馬主名',['母','馬齢']),'sire':field_between(text,'父',['性別','馬主名']),'dam':field_between(text,'母',['馬齢','調教師名']),
      'damsire':field_between(text,'母の父',['生年月日','生産牧場']),'birth_date':field_between(text,'生年月日',['生産牧場','母の母']),'breeder':field_between(text,'生産牧場',['母の母','毛色']),'coat':field_between(text,'毛色',['産地','馬名意味']),'birthplace':field_between(text,'産地',['馬名意味','取引市場']),
      'flat_acquired_prize_yen':flat_prize,'obstacle_acquired_prize_yen':obstacle_prize,'current_flat_class':flat_class_from_prize(flat_prize),
      'graded_experience':sorted({r['grade'] for r in graded}),'graded_starts':graded,'open_or_higher_history':open_history,'profile_race_rows':race_count,
      'flat_career_starts':flat_starts,'flat_career_wins':flat_wins,'flat_unbeaten':bool(flat_starts>=2 and flat_wins==flat_starts),
      'profile_url':profile_url(candidate['horse_id']),'candidate_sources':sorted(candidate['candidate_sources'])}

def verified_result_fallback():
    """Use only the public master's JRA-official evidence when profile parsing is structurally empty."""
    p=DOCS/'base_catalog.json'
    if not p.exists():return [],[],[]
    doc=json.loads(p.read_text(encoding='utf-8'));horses=doc.get('horses',[])
    graded=[];opened=[]
    for h in horses:
        if not h.get('active',True):continue
        tags=set(h.get('tags') or [])
        item=dict(h);item['candidate_sources']=['JRA_OFFICIAL_RESULT_FALLBACK']
        if 'GRADED' in tags:
            if not item.get('graded_starts'):
                item['graded_starts']=[{'source':'JRA_OFFICIAL_RESULT_HISTORY','race_names':item.get('graded_race_names',[])}]
            graded.append(item)
        if h.get('current_class')=='OPEN' or 'OPEN' in tags:
            item['current_flat_class']='OPEN'
            if not item.get('open_or_higher_history'):
                item['open_or_higher_history']=[{'source':'JRA_OFFICIAL_LATEST_CLASS'}]
            opened.append(item)
    by={h.get('horse_id') or h.get('horse_name'):h for h in graded+opened}
    return graded,opened,list(by.values())

def main():
    candidates=candidate_pool();DOCS.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(exist_ok=True);profiles=[];errors=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures={ex.submit(request_profile,c['horse_id']):c for c in candidates}
        for i,f in enumerate(as_completed(futures),1):
            c=futures[f]
            try:
                p=parse_profile(c,f.result())
                if not p['horse_name']:raise RuntimeError('horse name unresolved')
                profiles.append(p)
            except Exception as e:errors.append({'horse_id':c['horse_id'],'horse_name':c['horse_name'],'error':repr(e)})
            if i%250==0:print(f'profiles {i}/{len(candidates)} ok={len(profiles)} errors={len(errors)}',flush=True)
    profiles.sort(key=lambda x:x['horse_name']);active=[x for x in profiles if x['active']];graded=[x for x in active if x['graded_starts']];opened=[x for x in active if x['current_flat_class']=='OPEN']
    fallback_used=False
    # A large successfully fetched pool producing zero graded AND zero open horses is a parser-layout failure, not credible racing data.
    if len(profiles)>=100 and not graded and not opened:
        fg,fo,fe=verified_result_fallback()
        if fe:
            graded,opened=fg,fo;elite=fe;fallback_used=True
        else: elite=[]
    else:
        elite_ids={x['horse_id'] for x in graded+opened};elite=[x for x in active if x['horse_id'] in elite_ids]
    meta={'source':'JRA_OFFICIAL_HORSE_PROFILE' if not fallback_used else 'JRA_OFFICIAL_RESULTS_FALLBACK_AFTER_PROFILE_LAYOUT_FAILURE',
      'candidate_count':len(candidates),'profiles_ok':len(profiles),'profiles_error':len(errors),'active_count':len(active),
      'active_graded_count':len(graded),'active_open_count':len(opened),'elite_union_count':len(elite),
      'open_definition':'JRA flat acquired prize > 16,000,000 yen; fallback uses latest recorded JRA OPEN class',
      'open_threshold_yen':OPEN_THRESHOLD_YEN,'graded_definition':'active horse with recorded flat G1/G2/G3 start in JRA official evidence',
      'registered_roster_candidates':sum('CURRENT_REGISTERED_ROSTER' in x['candidate_sources'] for x in candidates),
      'profile_layout_fallback_used':fallback_used,'fallback_policy':'never infer; use only base_catalog evidence derived from JRA official results and official graded-race list'}
    for fn,hs in [('active_graded.json',graded),('active_open.json',opened),('active_elite.json',elite)]:
        (DOCS/fn).write_text(json.dumps({'summary':meta,'horses':hs},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    STATUS.write_text(json.dumps({'summary':meta,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(meta,ensure_ascii=False,indent=2))
    if errors:raise SystemExit(f'profile collection incomplete: {len(errors)} errors')
    if len(profiles)>=100 and not elite:raise SystemExit('elite catalog structurally empty after verified fallback')

if __name__=='__main__':main()
