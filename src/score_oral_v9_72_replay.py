#!/usr/bin/env python3
from __future__ import annotations
import csv,json
from collections import Counter,defaultdict
from pathlib import Path
PRED=Path('docs/data/oral-v9-72-confidence-style-predictions-sealed.json');RES=Path('data/race_results_html_2026.csv');V7=Path('docs/data/oral-v7-72-style-scored.json');OUT=Path('docs/data/oral-v9-72-confidence-style-scored.json');STATUS=Path('status/oral-v9-72-confidence-style-scored.json')
def norm(v):return str(v or '').strip().replace('競馬場','')
def i(v):
 try:return int(float(str(v).strip()))
 except:return None
def key(d,t,r):return(str(d),norm(t),i(r))
def ticket(xs):return '-'.join(map(str,sorted(int(x) for x in xs)))
def main():
 p=json.loads(PRED.read_text());raw=list(csv.DictReader(RES.open(encoding='utf-8-sig',newline='')));by=defaultdict(list)
 for r in raw:
  k=key(r.get('race_date'),r.get('course'),r.get('race_no'))
  if k[0] in ('2026-08-29','2026-08-30'):by[k].append(r)
 rows=[];g=Counter();dec=Counter();th=tb=0;missing=[]
 for r in p['races']:
  k=key(r['date'],r['track'],r['race_no']);rr=by.get(k,[]);a=r['analysis'];axis=str((a.get('axis') or {}).get('horse_no') or '');dec[str(a.get('pre_market_decision') or 'UNKNOWN')]+=1;ar=next((x for x in rr if str(x.get('horse_no') or '').lstrip('0')==axis.lstrip('0')),None)
  if not rr or not ar:missing.append(k);continue
  fin=i(ar.get('finish_position'));grade='HIT' if fin==1 else 'PLACE' if fin and fin<=3 else 'MISS';g[grade]+=1;top3=sorted([x for x in rr if i(x.get('finish_position')) in (1,2,3)],key=lambda x:i(x.get('finish_position')) or 99);actual=ticket([x['horse_no'] for x in top3]) if len(top3)==3 else None;t=set(a.get('trio_tickets') or []);bought=a.get('pre_market_decision')!='PASS' and bool(t);hit=bool(bought and actual in t)
  if bought:tb+=1;th+=int(hit)
  rows.append({'date':k[0],'track':k[1],'race_no':k[2],'decision':a.get('pre_market_decision'),'axis':axis,'axis_finish':fin,'axis_grade':grade,'trio_hit':hit,'style_gate':a.get('style_confidence_gate')})
 total=len(rows);summary={'model_version':p['version'],'prediction_hash_sha256':p['prediction_hash_sha256'],'race_count_scored':total,'missing_result_joins':missing,'decision_counts':dict(dec),'axis_1st':g['HIT'],'axis_2nd_3rd':g['PLACE'],'axis_outside_top3':g['MISS'],'axis_top3_rate_pct':round((g['HIT']+g['PLACE'])/total*100,2),'trio_bought_races':tb,'trio_hits':th,'trio_hit_rate_pct':round(th/tb*100,2) if tb else 0,'result_opened_after_prediction_seal':True}
 if V7.exists():
  old=json.loads(V7.read_text()).get('summary',{});summary['vs_v7']={'axis_top3_delta':(g['HIT']+g['PLACE'])-(int(old.get('axis_1st',0))+int(old.get('axis_2nd_3rd',0))),'trio_hits_delta':th-int(old.get('trio_hits',0))}
 payload={'summary':summary,'races':rows};OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
