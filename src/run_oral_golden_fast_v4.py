#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess
from pathlib import Path
from oral_operational_layer import analyze_race
SRC=Path('docs/data/oral-golden-fast-v3.json');OUT=Path('docs/data/oral-golden-fast-v4.json')

def f(v,d=0.0):
 try:return float(v)
 except:return d

def effective(h):
 base=f(h.get('base_score_v1'));structure=min(50.0,max(0.0,f(h.get('oral_structure_score'))));unc=max(0.0,min(1.0,f(h.get('uncertainty'))))
 raw=base+structure
 reliability=max(.45,1-.70*unc)
 return round(raw*reliability,3),round(raw,3),round(reliability,3)

def main():
 if not SRC.exists():subprocess.run(['python','src/run_oral_golden_fast_v3.py'],check=True)
 d=json.loads(SRC.read_text());rows=[];summary=[]
 for r in d['races']:
  rank=[]
  for h in r['ranked_snapshot']:
   x=dict(h);eff,raw,rel=effective(x);x['score_before_consensus']=f(x.get('score'));x['structure_score_capped']=round(min(50.0,max(0.0,f(x.get('oral_structure_score')))),3);x['consensus_raw_score']=raw;x['axis_reliability_factor']=rel;x['score']=eff;rank.append(x)
  rank.sort(key=lambda x:(-f(x.get('score')),int(str(x.get('n') or 999))))
  rr={**r,'ranked_snapshot':rank};a=analyze_race(rr)
  axis=rank[0] if rank else {};latest_same=axis.get('latest_same_class_finish');hist_exact=f(axis.get('exact_class_top3_rate'))
  recovery_axis=bool(latest_same and int(latest_same)>3 and hist_exact>=.60)
  if recovery_axis and a.get('pre_market_decision')=='BUY':
   a['pre_market_decision']='CAUTION';a['classification']='C';a['decision_override_reason']='現級での再現実績は高いが直近現級戦が馬券外のため、復調前提軸として1段階慎重化'
  a['consensus_policy']='base ability + capped structural fit (max 50) + axis reliability penalty; no odds/popularity/results'
  a['recovery_axis']=recovery_axis
  row={**{k:r.get(k) for k in ('date','track','race_no','race_name','surface','distance_m','target_class')},'analysis':a,'ranked_snapshot':rank};rows.append(row)
  summary.append({'track':r['track'],'race_no':r['race_no'],'axis':a['axis'],'decision':a['pre_market_decision'],'ticket_count':a['ticket_count'],'recovery_axis':recovery_axis,'top7':[{'n':x['n'],'name':x['name'],'score':x['score'],'base':x.get('base_score_v1'),'structure_capped':x['structure_score_capped'],'reliability':x['axis_reliability_factor'],'latest_same_class':x.get('latest_same_class_finish'),'exact_class_top3_rate':x.get('exact_class_top3_rate')} for x in rank[:7]]})
 OUT.write_text(json.dumps({'version':'ORAL_GOLDEN_FAST_V4_TWO_ENGINE_CONSENSUS','result_data_used':False,'odds_popularity_used':False,'summary':summary,'races':rows},ensure_ascii=False,indent=2));print(json.dumps({'summary':summary},ensure_ascii=False))
if __name__=='__main__':main()
