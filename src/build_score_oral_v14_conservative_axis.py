#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json,re
from collections import Counter,defaultdict
from pathlib import Path
V12=Path('docs/data/oral-v12-72-rank-consensus-sealed.json');C=Path('docs/data/pretarget-class-shortlist-72.json');G=Path('docs/data/oral-chat-golden-cases.json');R=Path('data/race_results_html_2026.csv');OP=Path('docs/data/oral-v14-72-conservative-axis-sealed.json');OS=Path('status/oral-v14-72-conservative-axis-scored.json');OG=Path('status/oral-v14-golden-axis-decision.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def f(v,d=0.0):
 try:return float(v)
 except:return d
def i(v,d=0):
 try:return int(float(str(v)))
 except:return d
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def arb(h):
 v=f(h.get('v4_effective'));hist=min(i(h.get('history_rows_before')),20);unc=f(h.get('uncertainty'),1);bonus=3*(1-unc)+.15*hist
 if i(h.get('latest_same_class_finish'),99)<=3:bonus+=6
 if f(h.get('exact_class_top3_rate'))>=.5:bonus+=3
 if f(h.get('same_class_top3_rate'))>=.5:bonus+=2
 return round(v+bonus,3)
def main():
 v=json.loads(V12.read_text());c=json.loads(C.read_text());cm={key(r):r for r in c['races']};rows=[];over=[]
 for r in v['races']:
  a=json.loads(json.dumps(r['analysis'],ensure_ascii=False));cr=cm[key(r)];by={str(h['n']):h for h in cr['horses']};old=str((a.get('axis') or {}).get('horse_no') or '');oh=by.get(old);cand=sorted(cr['horses'],key=lambda h:(-arb(h),int(h['n'])));best=cand[0] if cand else None
  change=bool(oh and best and str(best['n'])!=old and f(best.get('v4_effective'))>=f(oh.get('v4_effective'))-2.0 and arb(best)>=arb(oh)+2.5)
  if change:
   n=str(best['n']);recovery=i(best.get('latest_finish'),99)>3 and (i(best.get('latest_same_class_finish'),99)<=3 or f(best.get('exact_class_top3_rate'))>=.6);a['axis']={'horse_no':n,'horse_name':best.get('name')};a['pre_market_decision']='CAUTION' if recovery else ('BUY' if i(best.get('latest_finish'),99)<=3 and f(best.get('uncertainty'),1)<=.2 else a.get('pre_market_decision'));a['classification']='C' if a['pre_market_decision']=='CAUTION' else 'B' if a['pre_market_decision']=='BUY' else a.get('classification');a['v14_axis_override']=True;a['v14_recovery_axis']=recovery;over.append({'date':r['date'],'track':r['track'],'race_no':r['race_no'],'from':old,'to':n,'old_arb':arb(oh),'new_arb':arb(best),'old_v4':oh.get('v4_effective'),'new_v4':best.get('v4_effective'),'decision':a.get('pre_market_decision')})
  else:a['v14_axis_override']=False
  a['v14_policy']='V12 default; override only nearby V4 candidate with >=2.5 generic reliability/current-class arbitration edge; no target result/odds/popularity';rows.append({**{z:r.get(z) for z in ('race_id','date','track','race_no','race_name','surface','distance_m')},'analysis':a})
 p={'version':'ORAL_V14_CONSERVATIVE_AXIS_ARBITRATION','result_data_used':False,'odds_popularity_used':False,'target_result_rows_used':False,'class_cache_hash':c.get('cache_hash_sha256'),'override_count':len(over),'overrides':over,'races':rows};raw=json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':'));p['prediction_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest();OP.write_text(json.dumps(p,ensure_ascii=False,indent=2))
 # Golden axis+decision audit after seal.
 gm={key(x):x for x in json.loads(G.read_text())['cases']};pm={key(x):x for x in rows};cases=[]
 for k,g in gm.items():
  a=pm[k]['analysis'];cases.append({'date':k[0],'track':k[1],'race_no':k[2],'axis_match':str((a.get('axis') or {}).get('horse_no') or '')==no(g['axis']),'decision_match':a.get('pre_market_decision')==g.get('decision'),'system_axis':(a.get('axis') or {}).get('horse_no'),'golden_axis':no(g['axis']),'system_decision':a.get('pre_market_decision'),'golden_decision':g.get('decision')})
 ga={'axis_all':all(x['axis_match'] for x in cases),'decision_all':all(x['decision_match'] for x in cases),'cases':cases,'ticket_parity_not_evaluated_in_axis_stage':True};OG.parent.mkdir(exist_ok=True);OG.write_text(json.dumps(ga,ensure_ascii=False,indent=2))
 # Results after seal.
 by=defaultdict(list)
 with R.open(encoding='utf-8-sig',newline='') as f0:
  for x in csv.DictReader(f0):
   k=(str(x.get('race_date')),str(x.get('course')).strip().replace('競馬場',''),i(x.get('race_no')))
   if k[0] in ('2026-08-29','2026-08-30'):by[k].append(x)
 gr=Counter();missing=[]
 for r in rows:
  a=r['analysis'];axis=str((a.get('axis') or {}).get('horse_no') or '');rr=by[(r['date'],r['track'],int(r['race_no']))];ar=next((x for x in rr if str(x.get('horse_no') or '').lstrip('0')==axis.lstrip('0')),None)
  if not ar:missing.append(key(r));continue
  fin=i(ar.get('finish_position'),99);gr['HIT' if fin==1 else 'PLACE' if fin<=3 else 'MISS']+=1
 total=sum(gr.values());s={'version':p['version'],'prediction_hash':p['prediction_hash_sha256'],'override_count':len(over),'golden_axis_all':ga['axis_all'],'golden_decision_all':ga['decision_all'],'race_count_scored':total,'missing':missing,'axis_1st':gr['HIT'],'axis_2nd_3rd':gr['PLACE'],'axis_outside':gr['MISS'],'axis_top3_rate_pct':round((gr['HIT']+gr['PLACE'])/total*100,2) if total else 0,'v12_reference_axis_top3_rate_pct':56.94,'results_opened_after_prediction_seal':True};OS.write_text(json.dumps(s,ensure_ascii=False,indent=2));print(json.dumps({'golden':ga,'score':s,'overrides':over},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
