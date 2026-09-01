#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

V7=Path('docs/data/oral-v7-72-style-scored.json')
V8=Path('docs/data/oral-v8-72-fullstyle-scored.json')
OUT=Path('status/oral-v8-improvement-diagnostic.json')

def k(r):return (r['date'],r['track'],int(r['race_no']))
def main():
    a=json.loads(V7.read_text());b=json.loads(V8.read_text());am={k(x):x for x in a['races']};bm={k(x):x for x in b['races']}
    changed=[]
    for kk,x in bm.items():
        y=am.get(kk)
        if not y:continue
        if y.get('tickets')!=x.get('tickets') or y.get('main_partners')!=x.get('main_partners') or y.get('holes')!=x.get('holes'):
            changed.append({'date':kk[0],'track':kk[1],'race_no':kk[2],'axis_grade':x.get('axis_grade'),'v7_trio_hit':y.get('trio_hit'),'v8_trio_hit':x.get('trio_hit'),'actual_top3':x.get('actual_top3'),'v7_main':y.get('main_partners'),'v8_main':x.get('main_partners'),'v7_holes':y.get('holes'),'v8_holes':x.get('holes'),'v7_tickets':y.get('tickets'),'v8_tickets':x.get('tickets')})
    improved=[x for x in changed if not x['v7_trio_hit'] and x['v8_trio_hit']]
    worsened=[x for x in changed if x['v7_trio_hit'] and not x['v8_trio_hit']]
    out={'changed_races':len(changed),'new_hits':len(improved),'lost_hits':len(worsened),'improved':improved,'worsened':worsened,'changed':changed}
    OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'changed':len(changed),'new_hits':len(improved),'lost_hits':len(worsened)},ensure_ascii=False))
if __name__=='__main__':main()
