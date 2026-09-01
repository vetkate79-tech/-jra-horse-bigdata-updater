#!/usr/bin/env python3
import json,re
from pathlib import Path
G=Path('docs/data/oral-chat-golden-cases.json');B=Path('docs/data/horses/base_catalog.json');C=Path('docs/data/race_cards.json');O=Path('status/oral-golden-running-style-diagnostic.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def main():
 g=json.loads(G.read_text());b=json.loads(B.read_text());c=json.loads(C.read_text());byid={str(h.get('horse_id')):h for h in b.get('horses',[])};cm={key(r):r for r in c.get('races',[])};rows=[]
 for x in g['cases']:
  race=cm.get(key(x),{});hs=[]
  expected={no(x.get('axis')):'AXIS'}
  for n in [no(y) for y in x.get('partners',[]) if no(y)]:expected[n]='PARTNER'
  for n in [no(y) for y in x.get('holes',[]) if no(y)]:expected[n]='HOLE'
  for h in race.get('horses',[]):
   n=str(h.get('n'));base=byid.get(str(h.get('horse_id')),{});hs.append({'n':n,'name':h.get('name'),'expected_role':expected.get(n),'running_style':base.get('running_style') or base.get('style'),'running_style_basis':base.get('running_style_basis'),'starts_used':base.get('running_style_starts')})
  rows.append({'date':x['date'],'track':x['track'],'race_no':x['race_no'],'horses':hs})
 O.parent.mkdir(exist_ok=True);O.write_text(json.dumps({'races':rows},ensure_ascii=False,indent=2));print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':main()
