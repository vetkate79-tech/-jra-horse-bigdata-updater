#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
V12=Path('docs/data/oral-v12-72-rank-consensus-sealed.json');C=Path('docs/data/pretarget-class-feature-cache-72.json');OUT=Path('status/oral-v12-current-class-candidate-diagnostic.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def f(v,d=0.0):
 try:return float(v)
 except:return d
def i(v,d=0):
 try:return int(v)
 except:return d
def cls_score(h):
 return round(28*f(h.get('same_class_top3_rate'))+38*f(h.get('exact_class_top3_rate'))+5*min(i(h.get('same_class_starts')),6)+7*min(i(h.get('exact_class_starts')),4)+5*(1 if i(h.get('latest_same_class_finish'),99)<=3 else 0)+8*(1 if i(h.get('latest_exact_class_finish'),99)<=3 else 0)+.12*f(h.get('base_score_v1')),3)
def main():
 v=json.loads(V12.read_text());c=json.loads(C.read_text());cm={key(r):r for r in c['races']};rows=[]
 for r in v['races']:
  a=r['analysis'];old=str((a.get('axis') or {}).get('horse_no') or '');cr=cm[key(r)];hs=cr['horses'];by={str(h['n']):h for h in hs};oh=by.get(old,{})
  cand=[h for h in hs if i(h.get('same_class_starts'))>=2 and f(h.get('same_class_top3_rate'))>=.4 and f(h.get('uncertainty'),1)<=.4];cand.sort(key=lambda h:(-cls_score(h),int(h['n'])));best=cand[0] if cand else None
  rows.append({'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'target_class':cr.get('target_class'),'v12_axis':old,'v12_axis_class_score':cls_score(oh) if oh else None,'v12_axis_features':{k:oh.get(k) for k in ('same_class_starts','same_class_top3_rate','exact_class_starts','exact_class_top3_rate','latest_same_class_finish','latest_exact_class_finish','history_rows_before','uncertainty','base_score_v1')},'best_class_candidate':str(best['n']) if best else None,'best_class_score':cls_score(best) if best else None,'best_class_features':({k:best.get(k) for k in ('name','same_class_starts','same_class_top3_rate','exact_class_starts','exact_class_top3_rate','latest_same_class_finish','latest_exact_class_finish','history_rows_before','uncertainty','base_score_v1')} if best else None),'score_gap_candidate_minus_v12':round(cls_score(best)-cls_score(oh),3) if best and oh else None})
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'source':'sealed V12 + pretarget class cache; no target results/odds/popularity','race_count':len(rows),'rows':rows},ensure_ascii=False,indent=2));print(json.dumps({'race_count':len(rows),'different_best':sum(x['best_class_candidate'] and x['best_class_candidate']!=x['v12_axis'] for x in rows)},ensure_ascii=False))
if __name__=='__main__':main()
