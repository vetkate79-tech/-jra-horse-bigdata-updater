#!/usr/bin/env python3
from __future__ import annotations
import csv,json,os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

TZ=ZoneInfo('Asia/Tokyo')
target=os.getenv('TARGET_DATE') or datetime.now(TZ).date().isoformat()
year=target[:4]
RES=Path(f'data/race_results_html_{year}.csv')
PAY=Path(f'data/race_payouts_{year}.csv')
PRED=Path('docs/data/live_predictions_sealed.json')
OUT=Path(f'docs/data/today-results-{target}.json')
PRED_ARCHIVE=Path(f'docs/data/prediction-archive-{target}.json')
REPLAY=Path(f'docs/data/replay-{target}.json')

def i(v):
    try:return int(float(str(v).strip()))
    except:return None

def combo(xs):
    return '-'.join(map(str,sorted(int(x) for x in xs)))

def readcsv(p):
    if not p.exists():return []
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    rr=[r for r in readcsv(RES) if str(r.get('race_date'))==target]
    pp=[r for r in readcsv(PAY) if str(r.get('race_date'))==target]
    pred=json.loads(PRED.read_text(encoding='utf-8')) if PRED.exists() else {'races':[]}
    by=defaultdict(list)
    for r in rr:by[(str(r.get('course','')).replace('競馬場',''),i(r.get('race_no')))].append(r)
    payout={}
    for r in pp:
        bet=str(r.get('bet_type',''))
        if '三連複' in bet or '3連複' in bet:
            payout[str(r.get('race_id',''))]=r.get('payout_per_100_yen') or ''
    pred_by={(str(p.get('track','')).replace('競馬場',''),i(p.get('race_no'))):p for p in (pred.get('races') or []) if p.get('date')==target}
    out=[]
    for k,xs in sorted(by.items(),key=lambda kv:(kv[0][0],kv[0][1] or 99)):
        top=sorted([x for x in xs if i(x.get('finish_position')) in (1,2,3)],key=lambda x:i(x.get('finish_position')) or 99)
        if len(top)!=3:continue
        p=pred_by.get(k)
        nums=[str(i(x.get('horse_no'))) for x in top]
        actual=combo(nums)
        a=(p or {}).get('analysis') or {}
        tickets=set(a.get('trio_tickets') or [])
        hit=(actual in tickets) if p else None
        rid=str(top[0].get('race_id') or '')
        py=payout.get(rid,'')
        out.append({
            'date':target,'track':k[0],'race_no':k[1],
            'race_name':(p or {}).get('race_name') or top[0].get('race_name') or '',
            'top3':'－'.join(nums),
            'top3_rows':[{'finish':j+1,'horse_no':nums[j],'horse_name':top[j].get('horse_name') or ''} for j in range(3)],
            'has_sealed_prediction':bool(p),
            'axis_horse_no':str((a.get('axis') or {}).get('horse_no') or ''),
            'axis_horse_name':str((a.get('axis') or {}).get('horse_name') or ''),
            'trio_hit':hit,
            'trio_payout':(f"{int(py):,}円" if str(py).isdigit() else ('払戻確認中' if hit else '')),
            'source':top[0].get('source_url') or ''
        })
    payload={'date':target,'summary':{'checked':len(out),'complete':len(out)>=36},'races':out,'source':'JRA_OFFICIAL_RESULTS_DB'}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    archived_races=[p for p in (pred.get('races') or []) if p.get('date')==target]
    archived_pending=[p for p in (pred.get('pending') or []) if p.get('date')==target]
    pred_archive={
        'schema_version':pred.get('schema_version'),
        'mode':'IMMUTABLE_PREDICTION_ARCHIVE',
        'source_mode':pred.get('mode'),
        'model_version':pred.get('model_version'),
        'sealed_generated_at':pred.get('generated_at'),
        'prediction_hash_sha256':pred.get('prediction_hash_sha256'),
        'date':target,
        'odds_popularity_used':pred.get('odds_popularity_used',False),
        'results_used':pred.get('results_used',False),
        'races':archived_races,
        'pending':archived_pending
    }
    PRED_ARCHIVE.write_text(json.dumps(pred_archive,ensure_ascii=False,indent=2),encoding='utf-8')

    # One canonical public replay artifact per completed date.
    pred_map={(str(p.get('track','')).replace('競馬場',''),i(p.get('race_no'))):p for p in archived_races}
    replay_rows=[]
    for r in out:
        key=(r['track'],i(r['race_no']))
        p=pred_map.get(key)
        a=(p or {}).get('analysis') or {}
        axis_no=str((a.get('axis') or {}).get('horse_no') or r.get('axis_horse_no') or '')
        axis_name=str((a.get('axis') or {}).get('horse_name') or r.get('axis_horse_name') or '')
        top3_rows=r.get('top3_rows') or []
        finish=None
        if axis_no:
            for row in top3_rows:
                if str(row.get('horse_no'))==axis_no:
                    finish=i(row.get('finish'))
                    break
            if finish is None and len(top3_rows)==3:
                finish=4
        replay_rows.append({
            'date':target,
            'track':r['track'],
            'race_no':r['race_no'],
            'race_name':r.get('race_name') or '',
            'prediction':({
                'sealed':True,
                'axis_no':axis_no,
                'axis_name':axis_name,
                'decision':a.get('pre_market_decision') or a.get('classification') or '—',
                'candidate':[
                    ' '.join(str(v) for v in (x.get('horse_no'),x.get('horse_name')) if v not in (None,''))
                    for x in (a.get('partner_roles') or [])[:5]
                ],
                'tickets':a.get('trio_tickets') or []
            } if p else {'sealed':False}),
            'result':{
                'axis_finish':finish,
                'top3':top3_rows,
                'trio_hit':r.get('trio_hit'),
                'trio_payout':r.get('trio_payout') or '',
                'source':r.get('source') or ''
            }
        })
    replay_payload={
        'schema_version':1,
        'mode':'CANONICAL_REPLAY_DATE',
        'date':target,
        'summary':{
            'races':len(replay_rows),
            'sealed':sum(1 for x in replay_rows if x['prediction'].get('sealed') is not False),
            'results':sum(1 for x in replay_rows if len(x['result'].get('top3') or [])==3)
        },
        'races':replay_rows
    }
    REPLAY.write_text(json.dumps(replay_payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'results':payload['summary'],'replay':replay_payload['summary']},ensure_ascii=False))
if __name__=='__main__':main()
