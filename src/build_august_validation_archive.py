#!/usr/bin/env python3
from __future__ import annotations
import csv, json
from pathlib import Path

OUT=Path('docs/data/august-validation-archive.json')
DATES=['2026-08-01','2026-08-02','2026-08-08','2026-08-09','2026-08-15','2026-08-16','2026-08-22','2026-08-23','2026-08-29','2026-08-30']
TARGET=set(DATES)

def integer(v,d=None):
    try:return int(float(str(v).strip()))
    except Exception:return d

def load_json(path,default=None):
    p=Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else (default if default is not None else {})

def load_results():
    paths=[]
    for pat in ('data/race_results_html_2026_evo_*.csv','data/race_results_html_2026_holdout_0822_23.csv','data/race_results_html_2026.csv'):
        paths.extend(Path('.').glob(pat))
    horse_rows={}
    for p in paths:
        try:
            with p.open(encoding='utf-8-sig',newline='') as f:
                for r in csv.DictReader(f):
                    date=str(r.get('race_date') or '')
                    if date not in TARGET:continue
                    track=str(r.get('course') or r.get('track') or '')
                    rn=integer(r.get('race_no'));hn=integer(r.get('horse_no'));fin=integer(r.get('finish_position'))
                    if not track or rn is None or hn is None:continue
                    key=(date,track,rn,hn)
                    if key not in horse_rows or (fin is not None and horse_rows[key].get('finish') is None):
                        horse_rows[key]={'date':date,'track':track,'race_no':rn,'horse_no':str(hn),'horse_name':str(r.get('horse_name') or ''),'finish':fin,'race_name':str(r.get('race_name') or '')}
        except Exception:
            continue
    by_race={}
    for row in horse_rows.values():
        key=(row['date'],row['track'],row['race_no']);by_race.setdefault(key,[]).append(row)
    out={}
    for key,rs in by_race.items():
        top=sorted([x for x in rs if x.get('finish') is not None],key=lambda x:x['finish'])[:3]
        out[key]={'race_name':next((x['race_name'] for x in rs if x.get('race_name')),''),'top3':[{'horse_no':x['horse_no'],'horse_name':x['horse_name'],'finish':x['finish']} for x in top],
                  'finish_by_no':{x['horse_no']:x.get('finish') for x in rs}}
    return out

def name_map_216():
    d=load_json('validation/august_evolution_216r_base_sealed.json',{})
    out={}
    for r in d.get('races') or []:
        key=(r.get('date'),r.get('track'),integer(r.get('race_no')))
        for h in r.get('ranked_snapshot') or []:out[(key,str(h.get('n')))] = h.get('name','')
    return out

def add_record(store,rec):
    key=(rec['date'],rec['track'],int(rec['race_no']))
    if key in store:raise RuntimeError(f'duplicate archive prediction {key}')
    store[key]=rec

def build():
    results=load_results();records={};names=name_map_216()
    evo=load_json('validation/august_evolution_216r_scored.json',{})
    for d in evo.get('details') or []:
        date=d.get('date');track=d.get('track');rn=integer(d.get('race_no'))
        if date not in TARGET or not track or rn is None:continue
        key=(date,track,rn);axis=str(d.get('axis') or '');res=results.get(key,{})
        add_record(records,{'date':date,'track':track,'race_no':rn,'race_name':res.get('race_name',''),'archive_type':'RESULT_SEALED_VALIDATION',
          'prediction':{'source':'AUGUST_216R_V1.2_BASE_SEALED','model_version':'ORAL_INTEGRATED_V1_2_SHADOW','axis_no':axis,'axis_name':names.get((key,axis),''),'decision':d.get('decision'),'candidate':d.get('candidate') or [],'tickets':d.get('tickets') or []},
          'result':{'top3':res.get('top3') or [{'horse_no':str(x),'horse_name':'','finish':i+1} for i,x in enumerate(d.get('actual_top3') or [])],
                    'axis_finish':res.get('finish_by_no',{}).get(axis),'axis_top3':(res.get('finish_by_no',{}).get(axis) in (1,2,3)) if res else None,'trio_hit':bool(d.get('hit'))}})
    hold=load_json('validation/holdout_20260822_23_v12_sealed.json',{})
    for r in hold.get('races') or []:
        date=r.get('date');track=r.get('track');rn=integer(r.get('race_no'))
        if date not in TARGET or not track or rn is None:continue
        key=(date,track,rn);res=results.get(key,{});a=r.get('analysis') or {};axis_obj=a.get('axis') or {};axis_no=str(axis_obj.get('horse_no') or '')
        top3nos=sorted(str(x.get('horse_no')) for x in res.get('top3',[]));tickets=r.get('tickets') or []
        trio_hit=any(sorted(t.split('-'))==top3nos for t in tickets if isinstance(t,str) and t.count('-')==2) if top3nos else None
        candidate=[str(x.get('n')) for x in (r.get('ranked_snapshot') or [])[:7]]
        add_record(records,{'date':date,'track':track,'race_no':rn,'race_name':r.get('race_name') or res.get('race_name',''),'archive_type':'RESULT_SEALED_VALIDATION',
          'prediction':{'source':'V1.2_STRICT_HOLDOUT','model_version':hold.get('model_version'),'axis_no':axis_no,'axis_name':axis_obj.get('horse_name',''),'decision':r.get('decision'),'candidate':candidate,'tickets':tickets},
          'result':{'top3':res.get('top3',[]),'axis_finish':res.get('finish_by_no',{}).get(axis_no),'axis_top3':(res.get('finish_by_no',{}).get(axis_no) in (1,2,3)) if res else None,'trio_hit':trio_hit}})
    replay=load_json('docs/data/replay-axis-results.json',{})
    for x in replay.get('rows') or []:
        date=x.get('date');track=x.get('track');rn=integer(x.get('race_no'))
        if date not in ('2026-08-29','2026-08-30') or not track or rn is None:continue
        key=(date,track,rn);res=results.get(key,{});axis_no=str(x.get('axis_horse_no') or '')
        add_record(records,{'date':date,'track':track,'race_no':rn,'race_name':res.get('race_name',''),'archive_type':'FIXED_AUGUST_RESULT_ARCHIVE',
          'prediction':{'source':'SEALED_AXIS_ARCHIVE','model_version':'AUGUST_29_30_SEALED_ARCHIVE','axis_no':axis_no,'axis_name':x.get('axis_horse_name') or x.get('horse_name') or '','decision':'ARCHIVE_AXIS_ONLY','candidate':[],'tickets':[]},
          'result':{'top3':res.get('top3',[]),'axis_finish':x.get('finish'),'axis_top3':x.get('finish') in (1,2,3),'axis_evaluation':x.get('evaluation'),'trio_hit':None}})
    rows=sorted(records.values(),key=lambda x:(x['date'],x['track'],x['race_no']))
    counts={d:sum(x['date']==d for x in rows) for d in DATES}
    if len(rows)!=360 or any(counts[d]!=36 for d in DATES):
        raise RuntimeError(f'August archive must be exactly 360 races / 36 per date; got {len(rows)} {counts}')
    payload={'schema_version':1,'mode':'FIXED_AUGUST_2026_ONE_RACE_ONE_PREDICTION','note':'検証用固定アーカイブ。実際の発走前会話ログではない。結果を見る前に封印済みの代表予想を1Rにつき1件だけ表示し、モデル比較の複数予想は公開しない。',
      'one_prediction_per_race':True,'fixed':True,'dates':DATES,'race_count':len(rows),'race_count_by_date':counts,'races':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'status':'PASS','race_count':len(rows),'counts':counts},ensure_ascii=False))

if __name__=='__main__':build()
