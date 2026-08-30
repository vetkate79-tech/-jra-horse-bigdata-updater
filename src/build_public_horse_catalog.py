#!/usr/bin/env python3
import csv,json,re,os
from collections import defaultdict
from pathlib import Path

DATA=Path('data'); OUT=Path('docs/data/horses'); OUT.mkdir(parents=True,exist_ok=True)
TARGET_DATES={'2026-08-29','2026-08-30'}
GRADE_RE=re.compile(r'(G\s*[123ⅠⅡⅢＩＩＩ]+|GI{1,3}|GⅠ|GⅡ|GⅢ|ＧⅠ|ＧⅡ|ＧⅢ)',re.I)

def read_csv(path):
    if not path.exists(): return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def clean(v): return '' if v is None else str(v).strip()

def grade_of(r):
    text=' '.join(clean(r.get(k)) for k in ('race_name','race_class','race_category','class_name','クラス'))
    if re.search(r'(G1|GI|GⅠ|ＧⅠ)(?!I)',text,re.I): return 'G1'
    if re.search(r'(G2|GII|GⅡ|ＧⅡ)',text,re.I): return 'G2'
    if re.search(r'(G3|GIII|GⅢ|ＧⅢ)',text,re.I): return 'G3'
    return ''

def as_num(v):
    try:return float(v)
    except:return None

rows=[]
for p in sorted(DATA.glob('race_results_html_*.csv')):
    rows.extend([r for r in read_csv(p) if not clean(r.get('data_status')) or clean(r.get('data_status')).startswith('PASS')])

profiles={}
for p in sorted(DATA.glob('horse_profiles_*.csv')):
    for r in read_csv(p):
        name=clean(r.get('horse_name'))
        if name: profiles[name]=r

selected=defaultdict(lambda:{'graded_starts':[],'target_starts':[]})
for r in rows:
    name=clean(r.get('horse_name') or r.get('馬名'))
    if not name: continue
    date=clean(r.get('race_date') or r.get('日付'))
    g=grade_of(r)
    base={
      'race_id':clean(r.get('race_id')),'date':date,'course':clean(r.get('course') or r.get('場')),
      'race_no':clean(r.get('race_no') or r.get('R')),'race_name':clean(r.get('race_name')),
      'grade':g,'surface':clean(r.get('surface') or r.get('芝ダ')),'distance_m':clean(r.get('distance_m') or r.get('距離')),
      'horse_no':clean(r.get('horse_no') or r.get('馬番')),'finish':clean(r.get('finish_position') or r.get('着順')),
      'jockey':clean(r.get('jockey') or r.get('騎手')),'trainer':clean(r.get('trainer')),
      'sex_age':clean(r.get('sex_age') or r.get('性齢')),'source_url':clean(r.get('source_url'))
    }
    if g: selected[name]['graded_starts'].append(base)
    if date in TARGET_DATES: selected[name]['target_starts'].append(base)

horses=[]
for name,bucket in selected.items():
    if not bucket['graded_starts'] and not bucket['target_starts']: continue
    p=profiles.get(name,{})
    latest=(bucket['target_starts'] or bucket['graded_starts'])[-1]
    starts=as_num(p.get('starts')); wins=as_num(p.get('wins')); top2=as_num(p.get('top2')); top3=as_num(p.get('top3'))
    item={
      'horse_name':name,
      'horse_id':clean(p.get('horse_id') or next((x.get('race_id') for x in bucket['target_starts'] if x.get('race_id')),'')),
      'sex_age':clean(p.get('sex_age_latest') or latest.get('sex_age')),
      'trainer':clean(latest.get('trainer')),
      'starts':starts,'wins':wins,'top2':top2,'top3':top3,
      'win_rate':as_num(p.get('win_rate')),'quinella_rate':as_num(p.get('quinella_rate')),'show_rate':as_num(p.get('show_rate')),
      'latest_race_date':clean(p.get('latest_race_date') or latest.get('date')),
      'latest_course':clean(p.get('latest_course') or latest.get('course')),
      'latest_surface':clean(p.get('latest_surface') or latest.get('surface')),
      'latest_distance_m':clean(p.get('latest_distance_m') or latest.get('distance_m')),
      'graded_experience':sorted({x['grade'] for x in bucket['graded_starts'] if x['grade']}),
      'graded_starts':sorted(bucket['graded_starts'],key=lambda x:(x['date'],x['course'],x['race_no']),reverse=True),
      'target_starts':sorted(bucket['target_starts'],key=lambda x:(x['date'],x['course'],x['race_no']),reverse=True),
      'tags':([ 'GRADED' ] if bucket['graded_starts'] else []) + ([ '2026-08-29/30' ] if bucket['target_starts'] else [])
    }
    horses.append(item)

horses.sort(key=lambda x:x['horse_name'])
by_date=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
for h in horses:
    for s in h['target_starts']:
        by_date[s['date']][s['course']][str(s['race_no'])].append({'horse_name':h['horse_name'],'horse_no':s['horse_no'],'finish':s['finish'],'jockey':s['jockey'],'sex_age':s['sex_age']})

summary={
 'generated_from':[p.name for p in sorted(DATA.glob('race_results_html_*.csv'))],
 'horse_count':len(horses),
 'graded_horse_count':sum(bool(h['graded_starts']) for h in horses),
 'target_weekend_horse_count':sum(bool(h['target_starts']) for h in horses),
 'target_dates':sorted(TARGET_DATES),
 'coverage_note':'G1-G3経験は現在リポジトリに存在するJRA公式結果年の範囲で抽出。8/29・8/30は2026結果データが取得済みの場合に全中央出走馬を収録。'
}
(OUT/'catalog.json').write_text(json.dumps({'summary':summary,'horses':horses},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
(OUT/'weekend.json').write_text(json.dumps({'summary':summary,'dates':by_date},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
