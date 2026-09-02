#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re
from collections import Counter,defaultdict
from pathlib import Path
PRED=Path('docs/data/oral-v12-72-rank-consensus-sealed.json');GOLD=Path('docs/data/oral-chat-golden-cases.json');RES=Path('data/race_results_html_2026.csv');OUT=Path('docs/data/oral-v12-72-rank-consensus-scored.json');STATUS=Path('status/oral-v12-72-rank-consensus-scored.json');AUDIT=Path('status/oral-v12-golden-parity.json')
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def norm(v):return str(v or '').strip().replace('競馬場','')
def i(v):
 try:return int(float(str(v).strip()))
 except:return None
def key(d,t,r):return(str(d),norm(t),i(r))
def combo(xs):return '-'.join(map(str,sorted(int(x) for x in xs)))
def main():
 p=json.loads(PRED.read_text());pm={(r['date'],r['track'],int(r['race_no'])):r for r in p['races']};g=json.loads(GOLD.read_text());cases=[]
 for x in g['cases']:
  r=pm.get((x['date'],x['track'],int(x['race_no'])));a=(r or {}).get('analysis') or {};axis=str((a.get('axis') or {}).get('horse_no') or '');axis_ok=axis==no(x.get('axis'));dec_ok=a.get('pre_market_decision')==x.get('decision');actual_t=sorted(set(x.get('tickets') or []));sys_t=sorted(set(a.get('trio_tickets') or []));ticket_ok=(actual_t==sys_t) if x.get('tickets_verified') else None;cases.append({'date':x['date'],'track':x['track'],'race_no':x['race_no'],'axis_match':axis_ok,'decision_match':dec_ok,'tickets_verified':bool(x.get('tickets_verified')),'ticket_exact_match':ticket_ok,'actual_axis':no(x.get('axis')),'system_axis':axis,'actual_decision':x.get('decision'),'system_decision':a.get('pre_market_decision')})
 parity={'axis_all':all(x['axis_match'] for x in cases),'decision_all':all(x['decision_match'] for x in cases),'tickets_all_verified':all(x['ticket_exact_match'] for x in cases if x['tickets_verified']),'cases':cases};parity['certified']=bool(parity['axis_all'] and parity['decision_all'] and parity['tickets_all_verified']);AUDIT.parent.mkdir(exist_ok=True);AUDIT.write_text(json.dumps(parity,ensure_ascii=False,indent=2))
 raw=list(csv.DictReader(RES.open(encoding='utf-8-sig',newline='')));by=defaultdict(list)
 for x in raw:
  k=key(x.get('race_date'),x.get('course'),x.get('race_no'))
  if k[0] in ('2026-08-29','2026-08-30'):by[k].append(x)
 rows=[];grade=Counter();dec=Counter();tb=th=0;missing=[]
 for r in p['races']:
  rr=by.get(key(r['date'],r['track'],r['race_no']),[]);a=r['analysis'];axis=str((a.get('axis') or {}).get('horse_no') or '');dec[str(a.get('pre_market_decision') or 'UNKNOWN')]+=1;ar=next((x for x in rr if str(x.get('horse_no') or '').lstrip('0')==axis.lstrip('0')),None)
  if not ar:missing.append((r['date'],r['track'],r['race_no']));continue
  fin=i(ar.get('finish_position'));gr='HIT' if fin==1 else 'PLACE' if fin and fin<=3 else 'MISS';grade[gr]+=1;top3=[x for x in rr if i(x.get('finish_position')) in (1,2,3)];actual=combo([x['horse_no'] for x in top3]) if len(top3)==3 else None;bought=a.get('pre_market_decision')!='PASS' and bool(a.get('trio_tickets'));hit=bool(bought and actual in set(a.get('trio_tickets') or []));tb+=int(bought);th+=int(hit);rows.append({'date':r['date'],'track':r['track'],'race_no':r['race_no'],'decision':a.get('pre_market_decision'),'axis':axis,'axis_finish':fin,'axis_grade':gr,'trio_hit':hit})
 total=len(rows);summary={'version':p['version'],'prediction_hash':p['prediction_hash_sha256'],'golden_parity_certified':parity['certified'],'race_count_scored':total,'missing_result_joins':missing,'decision_counts':dict(dec),'axis_1st':grade['HIT'],'axis_2nd_3rd':grade['PLACE'],'axis_outside_top3':grade['MISS'],'axis_top3_rate_pct':round((grade['HIT']+grade['PLACE'])/total*100,2),'trio_bought_races':tb,'trio_hits':th,'trio_hit_rate_pct':round(th/tb*100,2) if tb else 0,'results_opened_after_seal':True};OUT.write_text(json.dumps({'summary':summary,'races':rows},ensure_ascii=False,indent=2));STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps({'parity':parity,'summary':summary},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
