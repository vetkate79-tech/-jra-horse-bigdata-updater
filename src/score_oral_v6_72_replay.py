#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re
from collections import Counter,defaultdict
from pathlib import Path
PRED=Path('docs/data/oral-v6-72-predictions-sealed.json')
RES=Path('data/race_results_html_2026.csv')
OUT=Path('docs/data/oral-v6-72-scored.json')
STATUS=Path('status/oral-v6-72-scored.json')

def norm_track(v):return str(v or '').strip().replace('競馬場','')
def i(v):
 try:return int(float(str(v).strip()))
 except:return None
def key(date,track,race_no):return(str(date),norm_track(track),i(race_no))
def ticket_key(xs):return '-'.join(map(str,sorted(int(x) for x in xs)))

def main():
 pred=json.loads(PRED.read_text())
 rows=[]
 with RES.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
 by_race=defaultdict(list)
 for r in raw:
  k=key(r.get('race_date'),r.get('course'),r.get('race_no'))
  if k[0] in ('2026-08-29','2026-08-30'):by_race[k].append(r)
 scored=[];grade=Counter();decision=Counter();pop_hits=Counter();trio_hit=0;trio_bought=0;missing=[]
 for p in pred.get('races',[]):
  k=key(p.get('date'),p.get('track'),p.get('race_no'));rr=by_race.get(k,[]);a=p.get('analysis') or {};axis=str((a.get('axis') or {}).get('horse_no') or '')
  decision[str(a.get('pre_market_decision') or 'UNKNOWN')]+=1
  axisrow=next((x for x in rr if str(x.get('horse_no') or '').lstrip('0')==axis.lstrip('0')),None)
  if not rr or not axisrow:missing.append({'date':k[0],'track':k[1],'race_no':k[2],'axis':axis});continue
  finish=i(axisrow.get('finish_position'));pop=i(axisrow.get('popularity'))
  if finish==1:g='HIT';label='◎ 予想的中';grade[g]+=1
  elif finish is not None and finish<=3:g='PLACE';label='△ 馬券内';grade[g]+=1
  else:g='MISS';label='× 不的中';grade[g]+=1
  if g in ('HIT','PLACE') and pop:pop_hits[pop]+=1
  top3=sorted([x for x in rr if i(x.get('finish_position')) in (1,2,3)],key=lambda x:i(x.get('finish_position')) or 99)
  actual=ticket_key([x.get('horse_no') for x in top3]) if len(top3)==3 else None
  tickets=set(a.get('trio_tickets') or []);bought=str(a.get('pre_market_decision'))!='PASS' and bool(tickets)
  th=bool(actual and actual in tickets) if bought else False
  if bought:trio_bought+=1;trio_hit+=int(th)
  scored.append({'date':k[0],'track':k[1],'race_no':k[2],'race_name':p.get('race_name'),'decision':a.get('pre_market_decision'),'axis_horse_no':axis,'axis_horse_name':(a.get('axis') or {}).get('horse_name'),'axis_popularity':pop,'axis_finish':finish,'axis_grade':g,'axis_label':label,'main_partners':a.get('role_main_partners') or [],'holes':a.get('role_holes') or [],'tickets':a.get('trio_tickets') or [],'actual_top3':[{'horse_no':str(x.get('horse_no')),'horse_name':x.get('horse_name'),'finish':i(x.get('finish_position')),'popularity':i(x.get('popularity'))} for x in top3],'trio_hit':th})
 total=len(scored);place_or_better=grade['HIT']+grade['PLACE']
 by_track={}
 for tr in sorted(set(x['track'] for x in scored)):
  xs=[x for x in scored if x['track']==tr];c=Counter(x['axis_grade'] for x in xs);by_track[tr]={'races':len(xs),'axis_1st':c['HIT'],'axis_2nd_3rd':c['PLACE'],'axis_out':c['MISS'],'axis_top3_rate':round((c['HIT']+c['PLACE'])/len(xs)*100,2) if xs else 0}
 by_date={}
 for dt in sorted(set(x['date'] for x in scored)):
  xs=[x for x in scored if x['date']==dt];c=Counter(x['axis_grade'] for x in xs);by_date[dt]={'races':len(xs),'axis_1st':c['HIT'],'axis_2nd_3rd':c['PLACE'],'axis_out':c['MISS'],'axis_top3_rate':round((c['HIT']+c['PLACE'])/len(xs)*100,2) if xs else 0}
 summary={'model_version':pred.get('version'),'prediction_hash_sha256':pred.get('prediction_hash_sha256'),'race_count_expected':pred.get('race_count'),'race_count_scored':total,'missing_result_joins':missing,'decision_counts':dict(decision),'axis_1st':grade['HIT'],'axis_2nd_3rd':grade['PLACE'],'axis_outside_top3':grade['MISS'],'axis_win_rate_pct':round(grade['HIT']/total*100,2) if total else 0,'axis_top3_rate_pct':round(place_or_better/total*100,2) if total else 0,'axis_top3_by_popularity':dict(sorted(pop_hits.items())),'trio_bought_races':trio_bought,'trio_hits':trio_hit,'trio_hit_rate_pct':round(trio_hit/trio_bought*100,2) if trio_bought else 0,'by_date':by_date,'by_track':by_track,'result_opened_after_prediction_seal':True}
 payload={'summary':summary,'races':scored};txt=json.dumps(payload,ensure_ascii=False,indent=2);OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
