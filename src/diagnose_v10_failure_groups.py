#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path
PRED=Path('docs/data/oral-v10-72-connected-durability-sealed.json')
SCORE=Path('docs/data/oral-v10-72-connected-durability-scored.json')
OUT=Path('status/oral-v10-failure-groups.json')

def main():
    if not PRED.exists() or not SCORE.exists():
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps({'status':'WAITING_FOR_V10'},ensure_ascii=False,indent=2));print('WAITING_FOR_V10');return
    p=json.loads(PRED.read_text());s=json.loads(SCORE.read_text());sm={(x['date'],x['track'],int(x['race_no'])):x for x in s['races']};groups=defaultdict(lambda:{'races':0,'top3':0,'wins':0,'trio_bought':0,'trio_hits':0})
    def add(name,r,sc):
        g=groups[name];g['races']+=1;g['top3']+=int(sc['axis_grade'] in ('HIT','PLACE'));g['wins']+=int(sc['axis_grade']=='HIT');b=r['analysis'].get('pre_market_decision')!='PASS' and bool(r['analysis'].get('trio_tickets'));g['trio_bought']+=int(b);g['trio_hits']+=int(sc.get('trio_hit',False))
    for r in p['races']:
        sc=sm.get((r['date'],r['track'],int(r['race_no'])));a=r['analysis']
        if not sc:continue
        add('ALL',r,sc);add('DECISION_'+str(a.get('pre_market_decision')),r,sc);add('TRACK_'+r['track'],r,sc);add('DUR_'+str((a.get('axis_durability') or {}).get('status','UNKNOWN')),r,sc);add('QUALITY_'+str(a.get('data_quality','UNKNOWN')),r,sc)
        if a.get('pre_market_decision')!='PASS':add('PURCHASED',r,sc);add('PURCHASED_TRACK_'+r['track'],r,sc);add('PURCHASED_DUR_'+str((a.get('axis_durability') or {}).get('status','UNKNOWN')),r,sc)
    out={}
    for k,v in groups.items():
        v['axis_top3_rate_pct']=round(v['top3']/v['races']*100,2) if v['races'] else 0;v['axis_win_rate_pct']=round(v['wins']/v['races']*100,2) if v['races'] else 0;v['trio_hit_rate_pct']=round(v['trio_hits']/v['trio_bought']*100,2) if v['trio_bought'] else None;out[k]=v
    payload={'status':'READY','policy':'Diagnostics only; use generalizable groups, not race identities.','groups':dict(sorted(out.items()))};OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print(json.dumps(payload,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
