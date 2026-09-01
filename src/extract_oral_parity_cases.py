#!/usr/bin/env python3
import json,re
from pathlib import Path

A=Path('docs/data/replay-demo-2026-08-29-30.json')
B=Path('docs/data/replay-2026-08-29-30-sealed.json')
S=Path('docs/data/oral-integrated-v1-shadow-sealed.json')
O=Path('docs/data/oral-parity-case-details.json')

def key(r):return (r.get('date'),r.get('track'),int(r.get('race_no') or 0))
def n(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def ns(xs):return [n(x) for x in (xs or []) if n(x)]

def main():
 a=json.loads(A.read_text());b=json.loads(B.read_text());s=json.loads(S.read_text())
 bm={key(r):r for r in b.get('races',[])};sm={key(r):r for r in s.get('races',[])}
 rows=[]
 for x in a.get('races',[]):
  if not str(x.get('prediction_source','')).startswith('PRE_RACE_CONVERSATION_LOG'):continue
  k=key(x); sr=sm.get(k); br=bm.get(k)
  if not sr:continue
  an=sr.get('analysis') or {}
  rows.append({
   'date':k[0],'track':k[1],'race_no':k[2],'race_name':x.get('race_name') or (br or {}).get('race_name'),
   'actual':{
    'axis':x.get('axis'),'partners':x.get('partners',[]),'holes':x.get('holes',[]),'decision':x.get('decision'),'formation':x.get('formation'),
    'ticket_count':x.get('ticket_count'),'tickets':x.get('tickets',[]),'pre_note':x.get('pre_note'),'type_label':x.get('type_label')
   },
   'system':{
    'axis':an.get('axis'),'axis_durability':an.get('axis_durability'),'partner_roles':an.get('partner_roles'),
    'third_place_intrusion':an.get('third_place_intrusion'),'failure_scenarios':an.get('failure_scenarios'),
    'classification':an.get('classification'),'decision':an.get('pre_market_decision'),'ticket_shape':an.get('ticket_shape'),
    'ticket_count':an.get('ticket_count'),'tickets':an.get('trio_tickets'),'data_quality':an.get('data_quality')
   },
   'base_ranked_snapshot':(br or {}).get('ranked_snapshot',[])[:10]
  })
 O.write_text(json.dumps({'case_count':len(rows),'cases':rows},ensure_ascii=False,indent=2));print(json.dumps({'case_count':len(rows),'keys':[(r['date'],r['track'],r['race_no']) for r in rows]},ensure_ascii=False))
if __name__=='__main__':main()
