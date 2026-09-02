#!/usr/bin/env python3
import json,re
from pathlib import Path
G=Path('docs/data/oral-chat-golden-cases.json');V=Path('docs/data/oral-v12-72-rank-consensus-sealed.json');C=Path('docs/data/pretarget-class-shortlist-72.json');O=Path('status/golden-class-shortlist-audit.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def main():
 g=json.loads(G.read_text());v={key(r):r for r in json.loads(V.read_text())['races']};c={key(r):r for r in json.loads(C.read_text())['races']};rows=[]
 fields=('name','n','v4_effective','history_rows_before','uncertainty','recent_top3_rate','exact_distance_top3_rate','same_class_starts','same_class_top3_rate','exact_class_starts','exact_class_top3_rate','latest_finish','latest_same_class_finish','latest_exact_class_finish')
 for x in g['cases']:
  k=key(x);cr=c[k];vm=v[k];va=str((vm['analysis'].get('axis') or {}).get('horse_no') or '');ga=no(x['axis']);by={str(h['n']):h for h in cr['horses']};rows.append({'date':k[0],'track':k[1],'race_no':k[2],'target_class':cr['target_class'],'golden_axis':ga,'v12_axis':va,'golden_features':{z:by.get(ga,{}).get(z) for z in fields},'v12_features':{z:by.get(va,{}).get(z) for z in fields}})
 O.parent.mkdir(exist_ok=True);O.write_text(json.dumps({'post_builder_audit_only':True,'rows':rows},ensure_ascii=False,indent=2));print(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
