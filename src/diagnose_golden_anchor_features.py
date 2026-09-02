#!/usr/bin/env python3
import json,re
from pathlib import Path
CACHE=Path('docs/data/pretarget-feature-cache-72.json');GOLD=Path('docs/data/oral-chat-golden-cases.json');V6=Path('docs/data/oral-v6-72-predictions-sealed.json');V12=Path('docs/data/oral-v12-72-rank-consensus-sealed.json');OUT=Path('status/golden-anchor-feature-diagnostic.json')
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def k(r):return (r['date'],r['track'],int(r['race_no']))
def main():
 c=json.loads(CACHE.read_text());g=json.loads(GOLD.read_text());v6=json.loads(V6.read_text());v12=json.loads(V12.read_text());cm={k(r):r for r in c['races']};m6={k(r):r for r in v6['races']};m12={k(r):r for r in v12['races']};rows=[]
 for x in g['cases']:
  key=k(x);cr=cm[key];actual=no(x['axis']);r6=m6.get(key,{});r12=m12.get(key,{});a6=str(((r6.get('analysis') or {}).get('axis') or {}).get('horse_no') or '');a12=str(((r12.get('analysis') or {}).get('axis') or {}).get('horse_no') or '')
  feats={str(h['n']):h for h in cr['horses']};af=feats.get(actual,{});f6=feats.get(a6,{});f12=feats.get(a12,{})
  def slim(h):return {z:h.get(z) for z in ('n','name','history_rows_before','recent_top3_rate','exact_distance_top3_rate','near_distance_top3_rate','same_course_top3_rate','exact_course_top3_rate','latest_finish','latest_exact_finish','latest_course_finish','latest_exact_course_finish','recent_form','condition_fit','show_rate_prior','uncertainty','running_style','style_sample_starts')}
  rows.append({'date':x['date'],'track':x['track'],'race_no':x['race_no'],'actual_axis':actual,'v6_axis':a6,'v12_axis':a12,'actual_features':slim(af),'v6_features':slim(f6),'v12_features':slim(f12)})
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'cases':rows},ensure_ascii=False,indent=2));print(json.dumps({'cases':rows},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
