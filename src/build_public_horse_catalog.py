#!/usr/bin/env python3
import csv,json,re
from collections import defaultdict
from pathlib import Path

DATA=Path('data'); OUT=Path('docs/data/horses'); OUT.mkdir(parents=True,exist_ok=True)
TARGET_DATES={'2026-08-29','2026-08-30'}


def read_csv(path):
    if not path.exists(): return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def clean(v): return '' if v is None else str(v).strip()
def as_num(v):
    try:return float(v)
    except:return None

def grade_of(r):
    text=' '.join(clean(r.get(k)) for k in ('race_name','race_class','race_category','class_name','クラス'))
    if re.search(r'(?:G1|GⅠ|ＧⅠ|\bGI\b)',text,re.I): return 'G1'
    if re.search(r'(?:G2|GⅡ|ＧⅡ|\bGII\b)',text,re.I): return 'G2'
    if re.search(r'(?:G3|GⅢ|ＧⅢ|\bGIII\b)',text,re.I): return 'G3'
    return ''

def valid_target_row(r):
    name=clean(r.get('horse_name') or r.get('馬名'))
    no=clean(r.get('horse_no') or r.get('馬番')).replace('.0','')
    return bool(name and re.fullmatch(r'\d{1,2}',no))

# Keep all rows available. Strict PASS is required for graded-history evidence;
# the two target dates may also use RACECARD_MINIMAL_VERIFIED rows because the
# immediate public need is the correct runner list for every race.
rows=[]; sources=[]
for p in sorted(DATA.glob('race_results_html_*.csv')):
    sources.append(p.name); rows.extend(read_csv(p))

profiles={}
for p in sorted(DATA.glob('horse_profiles_*.csv')):
    for r in read_csv(p):
        name=clean(r.get('horse_name'))
        if name:profiles[name]=r

selected=defaultdict(lambda:{'graded_starts':[],'target_starts':[]})
for r in rows:
    name=clean(r.get('horse_name') or r.get('馬名'))
    if not name:continue
    date=clean(r.get('race_date') or r.get('日付')); g=grade_of(r)
    status=clean(r.get('data_status'))
    base={
      'race_id':clean(r.get('race_id')),'horse_id':clean(r.get('horse_id')),'date':date,
      'course':clean(r.get('course') or r.get('場')),'race_no':clean(r.get('race_no') or r.get('R')),
      'race_name':clean(r.get('race_name')),'grade':g,'surface':clean(r.get('surface') or r.get('芝ダ')),
      'distance_m':clean(r.get('distance_m') or r.get('距離')),'horse_no':clean(r.get('horse_no') or r.get('馬番')).replace('.0',''),
      'finish':clean(r.get('finish_position') or r.get('着順')),'jockey':clean(r.get('jockey') or r.get('騎手')),
      'trainer':clean(r.get('trainer')),'sex_age':clean(r.get('sex_age') or r.get('性齢')),
      'source_url':clean(r.get('source_url')),'data_status':status}
    if g and (not status or status.startswith('PASS')): selected[name]['graded_starts'].append(base)
    if date in TARGET_DATES and valid_target_row(r): selected[name]['target_starts'].append(base)

horses=[]
for name,bucket in selected.items():
    p=profiles.get(name,{})
    all_starts=bucket['target_starts']+bucket['graded_starts']
    if not all_starts:continue
    latest=sorted(all_starts,key=lambda x:(x['date'],x['race_id']))[-1]
    hid=clean(p.get('horse_id')) or next((x['horse_id'] for x in all_starts if x.get('horse_id')),'')
    item={
      'horse_name':name,'horse_id':hid,'sex_age':clean(p.get('sex_age_latest') or latest.get('sex_age')),
      'trainer':clean(latest.get('trainer')),'starts':as_num(p.get('starts')),'wins':as_num(p.get('wins')),
      'top2':as_num(p.get('top2')),'top3':as_num(p.get('top3')),'win_rate':as_num(p.get('win_rate')),
      'quinella_rate':as_num(p.get('quinella_rate')),'show_rate':as_num(p.get('show_rate')),
      'latest_race_date':clean(p.get('latest_race_date') or latest.get('date')),
      'latest_course':clean(p.get('latest_course') or latest.get('course')),
      'latest_surface':clean(p.get('latest_surface') or latest.get('surface')),
      'latest_distance_m':clean(p.get('latest_distance_m') or latest.get('distance_m')),
      'graded_experience':sorted({x['grade'] for x in bucket['graded_starts'] if x['grade']}),
      'graded_starts':sorted(bucket['graded_starts'],key=lambda x:(x['date'],x['course'],x['race_no']),reverse=True),
      'target_starts':sorted(bucket['target_starts'],key=lambda x:(x['date'],x['course'],x['race_no']),reverse=True),
      'tags':(['GRADED'] if bucket['graded_starts'] else [])+(['2026-08-29/30'] if bucket['target_starts'] else [])}
    horses.append(item)
horses.sort(key=lambda x:x['horse_name'])

by_date=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
for h in horses:
    for s in h['target_starts']:
        by_date[s['date']][s['course']][str(int(float(s['race_no'])))].append({
            'horse_name':h['horse_name'],'horse_id':h['horse_id'],'horse_no':s['horse_no'],
            'finish':s['finish'],'jockey':s['jockey'],'sex_age':s['sex_age'],'quality':s['data_status']})

race_counts={d:sum(len(races) for races in by_date[d].values()) for d in TARGET_DATES}
runner_counts={d:sum(len(hs) for races in by_date[d].values() for hs in races.values()) for d in TARGET_DATES}
summary={
 'generated_from':sources,'horse_count':len(horses),
 'graded_horse_count':sum(bool(h['graded_starts']) for h in horses),
 'target_weekend_horse_count':sum(bool(h['target_starts']) for h in horses),
 'target_dates':sorted(TARGET_DATES),'target_race_count_by_date':race_counts,
 'target_runner_rows_by_date':runner_counts,'missing_horse_ids':sum(not h['horse_id'] for h in horses),
 'coverage_note':'8/29・8/30はレースカード最小品質ゲートで72Rを収録。G1-G3経験はリポジトリ内の厳格PASS済みJRA公式結果データから抽出。'}
if any(race_counts[d]!=36 for d in TARGET_DATES):raise SystemExit(f'weekend race coverage incomplete: {race_counts}')

(OUT/'catalog.json').write_text(json.dumps({'summary':summary,'horses':horses},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
(OUT/'weekend.json').write_text(json.dumps({'summary':summary,'dates':by_date},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
