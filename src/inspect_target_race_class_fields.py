#!/usr/bin/env python3
import json
from pathlib import Path
P=Path('docs/data/race_cards.json');OUT=Path('status/target-race-class-field-diagnostic.json')
def main():
 d=json.loads(P.read_text());targets={('2026-08-29','中京',6),('2026-08-29','中京',7),('2026-08-29','新潟',7)};rows=[]
 for r in d.get('races',[]):
  k=(r.get('date'),r.get('track'),int(r.get('race_no') or 0))
  if k in targets:
   rows.append({'key':k,'race_fields':{x:v for x,v in r.items() if x!='horses'},'horse_field_names':sorted((r.get('horses') or [{}])[0].keys())})
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'cases':rows},ensure_ascii=False,indent=2));print(json.dumps({'cases':rows},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
