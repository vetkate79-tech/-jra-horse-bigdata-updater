#!/usr/bin/env python3
from __future__ import annotations
import csv,json
from collections import Counter,defaultdict
from pathlib import Path
PRED=Path('docs/data/oral-v7-72-style-predictions-sealed.json')
BASE=Path('docs/data/oral-v6-72-scored.json')
RES=Path('data/race_results_html_2026.csv')
OUT=Path('docs/data/oral-v7-72-style-scored.json')
STATUS=Path('status/oral-v7-72-style-scored.json')

def norm_track(v):return str(v or '').strip().replace('競馬場','')
def i(v):
 try:return int(float(str(v).strip()))
 except:return None
def key(date,track,race_no):return(str(date),norm_track(track),i(race_no))
def ticket_key(xs):return '-'.join(map(str,sorted(int(x) for x in xs)))

def summarize(scored,pred):
 grade=Counter(x['axis_grade'] for x in scored);decision=Counter(x['decision'] for x in scored);pop_hits=Counter(x['axis_popularity'] for x in scored if x['axis_grade'] in ('HIT','PLACE') and x['axis_popularity']);trio_bought=sum(1 for x in scored if x['bought']);trio_hits=sum(1 for x in scored if x['trio_hit']);total=len(scored)
 by_track={}
 for tr in sorted(set(x['track'] for x in scored)):
  xs=[x for x in scored if x['track']==tr];c=Counter(x['axis_grade'] for x in xs);by_track[tr]={'races':len(xs),'axis_1st':c['HIT'],'axis_2nd_3rd':c['PLACE'],'axis_out':c['MISS'],'axis_top3_rate':round((c['HIT']+c['PLACE'])/len(xs)*100,2)}
 by_date={}
 for dt in sorted(set(x['date'] for x in scored)):
  xs=[x for x in scored if x['date']==dt];c=Counter(x['axis_grade'] for x in xs);by_date[dt]={'races':len(xs),'axis_1st':c['HIT'],'axis_2nd_3rd':c['PLACE'],'axis_out':c['MISS'],'axis_top3_rate':round((c['HIT']+c['PLACE'])/len(xs)*100,2)}
 return {'model_version':pred.get('version'),'prediction_hash_sha256':pred.get('prediction_hash_sha256'),'race_count_expected':pred.get('race_count'),'race_count_scored':total,'decision_counts':dict(decision),'axis_1st':grade['HIT'],'axis_2nd_3rd':grade['PLACE'],'axis_outside_top3':grade['MISS'],'axis_win_rate_pct':round(grade['HIT']/total*100,2),'axis_top3_rate_pct':round((grade['HIT']+grade['PLACE'])/total*100,2),'axis_top3_by_popularity':dict(sorted(pop_hits.items())),'trio_bought_races':trio_bought,'trio_hits':trio_hits,'trio_hit_rate_pct':round(trio_hits/trio_bought*100,2) if trio_bought else 0,'by_date':by_date,'by_track':by_track,'result_opened_after_prediction_seal':True}

def main():
 pred=json.loads(PRED.read_text());base=json.loads(BASE.read_text()) if BASE.exists() else {'summary':{}}
 with RES.open(encoding='utf-8-sig',newline='') as fh:raw=list(csv.DictReader(fh))
 by_race=defaultdict(list)
 for r in raw:
  k=key(r.get('race_date'),r.get('course'),r.get('race_no'))
  if k[0] in ('2026-08-29','2026-08-30'):by_race[k].append(r)
 scored=[];missing=[]
 for p in pred.get('races',[]):
  k=key(p.get('date'),p.get('track'),p.get('race_no'));rr=by_race.get(k,[]);a=p.get('analysis') or {};axis=str((a.get('axis') or {}).get('horse_no') or '');axisrow=next((x for x in rr if str(x.get('horse_no') or '').lstrip('0')==axis.lstrip('0')),None)
  if not rr or not axisrow:missing.append({'date':k[0],'track':k[1],'race_no':k[2],'axis':axis});continue
  finish=i(axisrow.get('finish_position'));pop=i(axisrow.get('popularity'))
  if finish==1:g='HIT';label='◎ 予想的中'
  elif finish is not None and finish<=3:g='PLACE';label='△ 馬券内'
  else:g='MISS';label='× 不的中'
  top3=sorted([x for x in rr if i(x.get('finish_position')) in (1,2,3)],key=lambda x:i(x.get('finish_position')) or 99);actual=ticket_key([x.get('horse_no') for x in top3]) if len(top3)==3 else None;tickets=set(a.get('trio_tickets') or []);bought=str(a.get('pre_market_decision'))!='PASS' and bool(tickets);th=bool(actual and actual in tickets) if bought else False
  scored.append({'date':k[0],'track':k[1],'race_no':k[2],'race_name':p.get('race_name'),'decision':a.get('pre_market_decision'),'axis_horse_no':axis,'axis_horse_name':(a.get('axis') or {}).get('horse_name'),'axis_running_style':a.get('axis_running_style'),'axis_running_style_label':a.get('axis_running_style_label'),'axis_popularity':pop,'axis_finish':finish,'axis_grade':g,'axis_label':label,'main_partners':a.get('role_main_partners') or [],'holes':a.get('role_holes') or [],'tickets':a.get('trio_tickets') or [],'actual_top3':[{'horse_no':str(x.get('horse_no')),'horse_name':x.get('horse_name'),'finish':i(x.get('finish_position')),'popularity':i(x.get('popularity'))} for x in top3],'bought':bought,'trio_hit':th})
 summary=summarize(scored,pred);summary['missing_result_joins']=missing
 b=base.get('summary') or {};summary['vs_v6_no_style']={'axis_1st_delta':summary['axis_1st']-int(b.get('axis_1st') or 0),'axis_top3_delta':(summary['axis_1st']+summary['axis_2nd_3rd'])-(int(b.get('axis_1st') or 0)+int(b.get('axis_2nd_3rd') or 0)),'axis_top3_rate_delta_pct_points':round(summary['axis_top3_rate_pct']-float(b.get('axis_top3_rate_pct') or 0),2),'trio_hits_delta':summary['trio_hits']-int(b.get('trio_hits') or 0),'trio_hit_rate_delta_pct_points':round(summary['trio_hit_rate_pct']-float(b.get('trio_hit_rate_pct') or 0),2)}
 payload={'summary':summary,'races':scored};txt=json.dumps(payload,ensure_ascii=False,indent=2);OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
