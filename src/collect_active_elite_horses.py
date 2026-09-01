#!/usr/bin/env python3
"""Build active JRA graded/open horse catalogs from official horse profiles.

Source of truth:
- active: no 抹消年月日 on JRA horse profile
- open class (flat): 収得賞金（平地） > 16,000,000 yen
- graded experience: at least one flat GⅠ/GⅡ/GⅢ race in profile race history

The candidate pool is the union of known 2025 JRA horse IDs and the verified
2026-08-29/30 runner IDs. Cached HTML is reused across runs.
"""
from __future__ import annotations
import csv,json,os,re,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from io import StringIO
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

ROOT=Path('.')
DATA=ROOT/'data'
DOCS=ROOT/'docs/data/horses'
CACHE=ROOT/'cache/jra_horse_profiles'
STATUS=ROOT/'status/active_elite_catalog.json'
BASE='https://www.jra.go.jp/JRADB/accessU.html'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
WORKERS=max(1,int(os.getenv('ELITE_PROFILE_WORKERS','4')))
MAX_PROFILES=int(os.getenv('ELITE_MAX_PROFILES','0')) # 0 = all candidates
OPEN_THRESHOLD_YEN=16_000_000

GRADE_RE=re.compile(r'(?<!J[・\-])(?:GⅠ|ＧⅠ|\bG1\b|\bGI\b|GⅡ|ＧⅡ|\bG2\b|\bGII\b|GⅢ|ＧⅢ|\bG3\b|\bGIII\b)',re.I)
GRADE_PATTERNS=[
 ('G1',re.compile(r'(?<!J[・\-])(?:GⅠ|ＧⅠ|\bG1\b|\bGI\b)',re.I)),
 ('G2',re.compile(r'(?<!J[・\-])(?:GⅡ|ＧⅡ|\bG2\b|\bGII\b)',re.I)),
 ('G3',re.compile(r'(?<!J[・\-])(?:GⅢ|ＧⅢ|\bG3\b|\bGIII\b)',re.I)),
]


def clean(v):
    if v is None:return ''
    s=str(v).strip()
    return '' if s.lower()=='nan' else s


def read_csv(path):
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def candidate_pool():
    by_id={}
    for r in read_csv(DATA/'horse_ids_2025.csv'):
        hid=clean(r.get('horse_id')); name=clean(r.get('horse_name'))
        if hid:by_id.setdefault(hid,{'horse_id':hid,'horse_name':name,'candidate_sources':set()})['candidate_sources'].add('2025')
    for r in read_csv(DATA/'race_results_html_2026_weekend.csv'):
        hid=clean(r.get('horse_id')); name=clean(r.get('horse_name'))
        if hid:
            item=by_id.setdefault(hid,{'horse_id':hid,'horse_name':name,'candidate_sources':set()})
            if not item['horse_name'] and name:item['horse_name']=name
            item['candidate_sources'].add('2026-08-29/30')
    vals=list(by_id.values())
    vals.sort(key=lambda x:(x['horse_name'],x['horse_id']))
    if MAX_PROFILES>0:vals=vals[:MAX_PROFILES]
    return vals


def profile_url(hid):
    return BASE+'?CNAME='+urllib.parse.quote(hid,safe='')


def request_profile(hid,retries=4):
    CACHE.mkdir(parents=True,exist_ok=True)
    safe=re.sub(r'[^A-Za-z0-9_.-]+','_',hid)+'.html'
    path=CACHE/safe
    if path.exists() and path.stat().st_size>10_000:
        return path.read_text(encoding='utf-8')
    req=urllib.request.Request(profile_url(hid),headers={'User-Agent':UA,'Referer':'https://www.jra.go.jp/','Accept-Language':'ja,en-US;q=0.7'})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=45) as resp:raw=resp.read()
            if len(raw)<10_000:raise RuntimeError(f'short profile {len(raw)}')
            text=raw.decode('cp932','replace')
            path.write_text(text,encoding='utf-8')
            return text
        except Exception:
            if attempt==retries-1:raise
            time.sleep(1.5*(attempt+1))
    raise RuntimeError('unreachable')


def money(text,label):
    m=re.search(re.escape(label)+r'\s*([0-9,]+)円',text)
    return int(m.group(1).replace(',','')) if m else None


def field_between(text,label,next_labels):
    nxt='|'.join(re.escape(x) for x in next_labels)
    m=re.search(re.escape(label)+r'\s*(.*?)\s*(?='+nxt+r')',text,re.S)
    return re.sub(r'\s+',' ',m.group(1)).strip() if m else ''


def normalized_tables(html):
    out=[]
    try:tables=pd.read_html(StringIO(html))
    except Exception:return out
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


def race_history(html):
    graded=[]; open_rows=[]; all_count=0
    for table in normalized_tables(html):
        if not any('レース名' in c for c in table.columns):continue
        for _,row in table.iterrows():
            vals={c:clean(v) for c,v in row.items()}
            joined=' '.join(vals.values())
            race_name=next((v for c,v in vals.items() if 'レース名' in c), '')
            date=next((v for c,v in vals.items() if '年月日' in c or c=='日付'), '')
            venue=next((v for c,v in vals.items() if c in ('場','競馬場')), '')
            finish=next((v for c,v in vals.items() if '着順' in c), '')
            if not race_name:continue
            all_count+=1
            grade=grade_name(joined)
            is_jump=('障害' in race_name) or ('J・G' in joined) or ('J-G' in joined)
            if grade and not is_jump:
                graded.append({'date':date,'venue':venue,'race_name':race_name,'grade':grade,'finish':finish})
            if ('オープン' in race_name or 'リステッド' in joined or 'Listed' in joined or grade) and not is_jump:
                open_rows.append({'date':date,'venue':venue,'race_name':race_name,'grade':grade,'finish':finish})
    # de-duplicate occasional duplicated responsive tables
    def dedup(rows):
        seen=set();out=[]
        for r in rows:
            k=(r['date'],r['venue'],r['race_name'],r['grade'],r['finish'])
            if k not in seen:seen.add(k);out.append(r)
        return out
    return dedup(graded),dedup(open_rows),all_count


def parse_profile(candidate,html):
    soup=BeautifulSoup(html,'html.parser')
    text=re.sub(r'\s+',' ',soup.get_text(' ',strip=True))
    erased=re.search(r'抹消年月日\s*(\d{4}年\d{1,2}月\d{1,2}日)',text)
    active=not bool(erased)
    flat_prize=money(text,'収得賞金（平地）')
    obstacle_prize=money(text,'収得賞金（障害）')
    graded,open_history,race_count=race_history(html)
    name=candidate['horse_name']
    profile={
      'horse_name':name,'horse_id':candidate['horse_id'],'active':active,
      'deregistered_at':erased.group(1) if erased else None,
      'sex':field_between(text,'性別',['馬主名','母']),
      'age':field_between(text,'馬齢',['調教師名','母の父']),
      'trainer':field_between(text,'調教師名',['母の父','生年月日']),
      'owner':field_between(text,'馬主名',['母','馬齢']),
      'sire':field_between(text,'父',['性別','馬主名']),
      'dam':field_between(text,'母',['馬齢','調教師名']),
      'damsire':field_between(text,'母の父',['生年月日','生産牧場']),
      'birth_date':field_between(text,'生年月日',['生産牧場','母の母']),
      'breeder':field_between(text,'生産牧場',['母の母','毛色']),
      'coat':field_between(text,'毛色',['産地','馬名意味']),
      'birthplace':field_between(text,'産地',['馬名意味','取引市場']),
      'flat_acquired_prize_yen':flat_prize,
      'obstacle_acquired_prize_yen':obstacle_prize,
      'current_flat_class':('OPEN' if flat_prize is not None and flat_prize>OPEN_THRESHOLD_YEN else 'NON_OPEN_OR_UNKNOWN'),
      'graded_experience':sorted({r['grade'] for r in graded}),
      'graded_starts':graded,'open_or_higher_history':open_history,
      'profile_race_rows':race_count,'profile_url':profile_url(candidate['horse_id']),
      'candidate_sources':sorted(candidate['candidate_sources'])
    }
    return profile


def main():
    candidates=candidate_pool(); DOCS.mkdir(parents=True,exist_ok=True); STATUS.parent.mkdir(exist_ok=True)
    profiles=[];errors=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures={ex.submit(request_profile,c['horse_id']):c for c in candidates}
        for i,f in enumerate(as_completed(futures),1):
            c=futures[f]
            try:profiles.append(parse_profile(c,f.result()))
            except Exception as e:errors.append({'horse_id':c['horse_id'],'horse_name':c['horse_name'],'error':repr(e)})
            if i%250==0:print(f'profiles {i}/{len(candidates)} ok={len(profiles)} errors={len(errors)}',flush=True)

    profiles.sort(key=lambda x:x['horse_name'])
    active=[x for x in profiles if x['active']]
    graded=[x for x in active if x['graded_starts']]
    opened=[x for x in active if (x['flat_acquired_prize_yen'] is not None and x['flat_acquired_prize_yen']>OPEN_THRESHOLD_YEN)]
    # Union is useful for the eventual unified horse master.
    elite_ids={x['horse_id'] for x in graded+opened}
    elite=[x for x in active if x['horse_id'] in elite_ids]
    meta={
      'source':'JRA_OFFICIAL_HORSE_PROFILE','candidate_count':len(candidates),
      'profiles_ok':len(profiles),'profiles_error':len(errors),'active_count':len(active),
      'active_graded_count':len(graded),'active_open_count':len(opened),'elite_union_count':len(elite),
      'open_definition':'JRA flat acquired prize > 16,000,000 yen','open_threshold_yen':OPEN_THRESHOLD_YEN,
      'graded_definition':'active JRA horse with at least one flat G1/G2/G3 start in profile history'
    }
    (DOCS/'active_graded.json').write_text(json.dumps({'summary':meta,'horses':graded},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (DOCS/'active_open.json').write_text(json.dumps({'summary':meta,'horses':opened},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (DOCS/'active_elite.json').write_text(json.dumps({'summary':meta,'horses':elite},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    STATUS.write_text(json.dumps({'summary':meta,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))
    # Network failures should not silently produce a partial master.
    if errors:raise SystemExit(f'profile collection incomplete: {len(errors)} errors')

if __name__=='__main__':main()
