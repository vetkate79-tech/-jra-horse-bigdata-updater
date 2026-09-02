#!/usr/bin/env python3
from __future__ import annotations
import csv,json
from collections import Counter,defaultdict
from pathlib import Path
P=Path('docs/data/oral-v12-72-rank-consensus-sealed.json');R=Path('data/race_results_html_2026.csv');O=Path('status/oral-v12-trio-failure-diagnostic.json')
def i(v):
 try:return int(float(str(v)))
 except:return None
def key(d,t,r):return(str(d),str(t or '').strip().replace('競馬場',''),i(r))
def combo(xs):return '-'.join(map(str,sorted(int(x) for x in xs)))
def main():
 p=json.loads(P.read_text());by=defaultdict(list)
 with R.open(encoding='utf-8-sig',newline='') as f:
  for x in csv.DictReader(f):
   k=key(x.get('race_date'),x.get('course'),x.get('race_no'))
   if k[0] in ('2026-08-29','2026-08-30'):by[k].append(x)
 c=Counter();rows=[]
 for r in p['races']:
  a=r['analysis'];decision=a.get('pre_market_decision');tickets=set(a.get('trio_tickets') or [])
  if decision=='PASS' or not tickets:continue
  rr=by[key(r['date'],r['track'],r['race_no'])];top=sorted([x for x in rr if i(x.get('finish_position')) in (1,2,3)],key=lambda x:i(x['finish_position']));actual=combo([x['horse_no'] for x in top]) if len(top)==3 else None;axis=str((a.get('axis') or {}).get('horse_no') or '');topnos={str(x['horse_no']).lstrip('0') for x in top};axisin=axis.lstrip('0') in topnos;roles={str(x.get('horse_no') or '').lstrip('0') for x in (a.get('role_main_partners') or [])+(a.get('role_holes') or [])};needed=topnos-{axis.lstrip('0')};hit=actual in tickets if actual else False
  if hit:typ='HIT'
  elif not axisin:typ='AXIS_MISS'
  elif needed.issubset(roles):typ='TICKET_CONVERSION_MISS'
  else:typ='PARTNER_SELECTION_MISS'
  c[typ]+=1;rows.append({'date':r['date'],'track':r['track'],'race_no':r['race_no'],'type':typ,'axis':axis,'actual_top3':sorted(topnos),'role_pool':sorted(roles),'tickets':sorted(tickets),'actual_ticket':actual})
 O.parent.mkdir(exist_ok=True);O.write_text(json.dumps({'post_result_pdca_only':True,'must_not_be_prediction_input':True,'counts':dict(c),'rows':rows},ensure_ascii=False,indent=2));print(json.dumps(dict(c),ensure_ascii=False))
if __name__=='__main__':main()
