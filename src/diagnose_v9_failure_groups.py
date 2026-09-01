#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path
PRED=Path('docs/data/oral-v9-72-confidence-style-predictions-sealed.json')
SCORE=Path('docs/data/oral-v9-72-confidence-style-scored.json')
OUT=Path('status/oral-v9-failure-groups.json')

def main():
 p=json.loads(PRED.read_text());s=json.loads(SCORE.read_text());sm={(x['date'],x['track'],int(x['race_no'])):x for x in s['races']};groups=defaultdict(lambda:{'races':0,'top3':0,'wins':0,'trio_bought':0,'trio_hits':0})
 def add(name,r,sc):
  g=groups[name];g['races']+=1;g['top3']+=int(sc['axis_grade'] in ('HIT','PLACE'));g['wins']+=int(sc['axis_grade']=='HIT');b=r['analysis'].get('pre_market_decision')!='PASS' and bool(r['analysis'].get('trio_tickets'));g['trio_bought']+=int(b);g['trio_hits']+=int(sc.get('trio_hit',False))
 for r in p['races']:
  sc=sm.get((r['date'],r['track'],int(r['race_no'])));a=r['analysis'];
  if not sc:continue
  add('ALL',r,sc);add('DECISION_'+str(a.get('pre_market_decision')),r,sc);add('TRACK_'+r['track'],r,sc)
  gate=a.get('style_confidence_gate') or {};ratio=float(gate.get('resolved_ratio') or 0);bucket='STYLE_HIGH' if ratio>=.7 else 'STYLE_MID' if ratio>=.4 else 'STYLE_LOW';add(bucket,r,sc)
  dur=(a.get('axis_durability') or {}).get('status') or 'UNKNOWN';add('DUR_'+dur,r,sc)
  if a.get('pre_market_decision')!='PASS':add('PURCHASED',r,sc);add('PURCHASED_'+bucket,r,sc);add('PURCHASED_TRACK_'+r['track'],r,sc)
 out={}
 for k,v in groups.items():
  v['axis_top3_rate_pct']=round(v['top3']/v['races']*100,2) if v['races'] else 0;v['axis_win_rate_pct']=round(v['wins']/v['races']*100,2) if v['races'] else 0;v['trio_hit_rate_pct']=round(v['trio_hits']/v['trio_bought']*100,2) if v['trio_bought'] else None;out[k]=v
 payload={'policy':'Diagnostics only. Do not tune by individual race identity; use only stable/generalizable group patterns.','groups':dict(sorted(out.items()))};OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print(json.dumps(payload,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
