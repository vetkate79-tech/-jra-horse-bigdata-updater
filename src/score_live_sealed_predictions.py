#!/usr/bin/env python3
from __future__ import annotations
import csv,json
from collections import Counter,defaultdict
from pathlib import Path

PRED=Path('docs/data/live_predictions_sealed.json')
RES=Path('data/race_results_html_2026.csv')
OUT=Path('docs/data/live_prediction_scores.json')
STATUS=Path('status/live_prediction_scoring.json')

def i(v):
    try:return int(float(str(v).strip()))
    except:return None

def norm(v):return str(v or '').strip().replace('競馬場','')
def key(d,t,n):return(str(d or ''),norm(t),i(n))
def combo(xs):return '-'.join(map(str,sorted(int(x) for x in xs)))

def main():
    pred=json.loads(PRED.read_text(encoding='utf-8')) if PRED.exists() else {'races':[]}
    raw=[]
    if RES.exists():
        with RES.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
    by=defaultdict(list)
    for r in raw:by[key(r.get('race_date'),r.get('course'),r.get('race_no'))].append(r)
    rows=[];pending=[];grade=Counter();decisions=Counter();trio_hits=0;trio_buys=0
    for p in pred.get('races',[]):
        k=key(p.get('date'),p.get('track'),p.get('race_no'));rr=by.get(k,[]);a=p.get('analysis') or {}
        if not rr:
            pending.append({'date':k[0],'track':k[1],'race_no':k[2],'reason':'RESULT_PENDING'});continue
        axis=str((a.get('axis') or {}).get('horse_no') or '')
        ar=next((x for x in rr if str(x.get('horse_no') or '').lstrip('0')==axis.lstrip('0')),None)
        if not ar:
            pending.append({'date':k[0],'track':k[1],'race_no':k[2],'reason':'AXIS_RESULT_NOT_JOINED'});continue
        finish=i(ar.get('finish_position'));pop=i(ar.get('popularity'))
        if finish==1:g='HIT';label='◎ 予想的中'
        elif finish is not None and finish<=3:g='PLACE';label='△ 馬券内'
        else:g='MISS';label='× 不的中'
        grade[g]+=1;decisions[str(a.get('pre_market_decision') or 'UNKNOWN')]+=1
        top3=sorted([x for x in rr if i(x.get('finish_position')) in (1,2,3)],key=lambda x:i(x.get('finish_position')) or 99)
        actual=combo([x.get('horse_no') for x in top3]) if len(top3)==3 else None
        tickets=set(a.get('trio_tickets') or [])
        bought=str(a.get('pre_market_decision'))!='PASS' and bool(tickets)
        th=bool(bought and actual and actual in tickets)
        if bought:trio_buys+=1;trio_hits+=int(th)
        rows.append({'date':k[0],'track':k[1],'race_no':k[2],'race_name':p.get('race_name'),'prediction_hash_sha256':pred.get('prediction_hash_sha256'),'decision':a.get('pre_market_decision'),'axis_horse_no':axis,'axis_horse_name':(a.get('axis') or {}).get('horse_name'),'axis_finish':finish,'axis_popularity_result_only':pop,'axis_grade':g,'axis_label':label,'actual_top3':[{'horse_no':str(x.get('horse_no') or ''),'horse_name':x.get('horse_name'),'finish':i(x.get('finish_position'))} for x in top3],'trio_hit':th})
    scored=len(rows);top3=grade['HIT']+grade['PLACE']
    summary={'source_prediction_hash_sha256':pred.get('prediction_hash_sha256'),'sealed_predictions_immutable':True,'scored_race_count':scored,'pending_race_count':len(pending),'axis_1st':grade['HIT'],'axis_2nd_3rd':grade['PLACE'],'axis_outside_top3':grade['MISS'],'axis_top3_rate_pct':round(top3/scored*100,2) if scored else None,'decision_counts':dict(decisions),'trio_bought_races':trio_buys,'trio_hits':trio_hits,'trio_hit_rate_pct':round(trio_hits/trio_buys*100,2) if trio_buys else None,'result_fields_used_only_after_seal':True}
    payload={'summary':summary,'pending':pending,'races':rows}
    OUT.parent.mkdir(exist_ok=True);STATUS.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
