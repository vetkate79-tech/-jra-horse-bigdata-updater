#!/usr/bin/env python3
"""Chronological PDCA calibration for the Aug blind replay.

2026-08-29 is calibration only. 2026-08-30 is held out and never used to
choose thresholds/strategy. This does not rewrite the sealed v0.2 predictions;
it produces a separate v0.3 diagnostic/config for future model work.
"""
import json,itertools
from pathlib import Path

SRC=Path('docs/data/replay-2026-08-29-30-full.json')
OUT=Path('docs/data/model-calibration-v03.json')
STATUS=Path('status/model-calibration-v03.json')


def combo(nums): return '-'.join(map(str,sorted(map(int,nums))))
def truth(r): return r.get('trio_result','')

def strategy(r,kind):
    ranked=r.get('ranked_snapshot') or []
    nums=[str(x.get('n')) for x in ranked[:7] if str(x.get('n','')).isdigit()]
    if len(nums)<3:return []
    if kind=='AXIS7':
        a=nums[0]; pairs=[(1,2),(1,3),(1,4),(2,3),(2,4),(3,4),(1,5)]
        return list(dict.fromkeys(combo([a,nums[i],nums[j]]) for i,j in pairs if j<len(nums)))
    if kind=='DUAL9':
        a,b=nums[:2]; rest=nums[2:6]; out=[]
        for x in rest: out.append(combo([a,b,x]))
        for x,y in itertools.combinations(rest,2):
            if len(out)>=9:break
            out.append(combo([a,x,y]))
        return list(dict.fromkeys(out))[:9]
    if kind=='GROUP10':
        return [combo(c) for c in itertools.combinations(nums[:5],3)][:10]
    return []

def features(r):
    rr=r.get('ranked_snapshot') or []
    if len(rr)<2:return 0,1,0
    gap=float(rr[0].get('score',0))-float(rr[1].get('score',0))
    unc=float(rr[0].get('uncertainty',1))
    starts=float(rr[0].get('starts_before',0))
    return gap,unc,starts

def decide(r,cfg):
    gap,unc,starts=features(r)
    if starts<cfg['min_starts'] or unc>cfg['max_uncertainty']:return 'PASS',[]
    if gap>=cfg['axis_gap']: kind='AXIS7'
    elif gap>=cfg['dual_gap']: kind='DUAL9'
    else: kind='GROUP10'
    return kind,strategy(r,kind)

def score(rows,cfg):
    s={'races':len(rows),'bets':0,'passes':0,'hits':0,'stake':0,'return':0,'axis_survived':0,'candidate_top3_complete':0}
    for r in rows:
        kind,tickets=decide(r,cfg)
        if r.get('axis_survived'):s['axis_survived']+=1
        if r.get('candidate_top3_captured')==3:s['candidate_top3_complete']+=1
        if kind=='PASS':s['passes']+=1;continue
        s['bets']+=1;s['stake']+=100*len(tickets)
        if truth(r) and truth(r) in tickets:
            s['hits']+=1;s['return']+=int(r.get('trio_payout') or 0)
    s['hit_rate_pct']=round(100*s['hits']/s['bets'],2) if s['bets'] else 0
    s['roi_pct']=round(100*s['return']/s['stake'],2) if s['stake'] else 0
    return s

def main():
    doc=json.loads(SRC.read_text(encoding='utf-8'))
    rows=doc.get('races',[])
    train=[r for r in rows if r.get('date')=='2026-08-29' and r.get('prediction_source')=='BLIND_REPLAY_RECONSTRUCTION']
    test=[r for r in rows if r.get('date')=='2026-08-30' and r.get('prediction_source')=='BLIND_REPLAY_RECONSTRUCTION']
    candidates=[]
    for axis_gap in (2.0,3.0,4.0,5.0,6.0):
      for dual_gap in (0.8,1.2,1.6,2.0):
       if dual_gap>=axis_gap:continue
       for min_starts in (1,2,3):
        for max_uncertainty in (0.4,0.6,0.8):
         cfg={'axis_gap':axis_gap,'dual_gap':dual_gap,'min_starts':min_starts,'max_uncertainty':max_uncertainty}
         st=score(train,cfg)
         # Prefer candidate quality + sustainable hit rate; ROI is secondary due tiny sample.
         objective=st['hits']*20 + st['hit_rate_pct']*0.6 + min(st['roi_pct'],200)*0.08 - st['passes']*0.15
         candidates.append((objective,cfg,st))
    candidates.sort(key=lambda x:(-x[0],-x[2]['hits'],-x[2]['hit_rate_pct']))
    _,best,train_score=candidates[0]
    test_score=score(test,best)
    out={
      'version':'BLIND_RULE_REPLAY_V0.3_PDCA',
      'method':'chronological holdout',
      'calibration_date':'2026-08-29','holdout_date':'2026-08-30',
      'truth_note':'Thresholds and ticket strategy are selected only on 8/29. 8/30 is scored once as holdout.',
      'base_policy':'Keep the same horse ranking foundation; improve PASS/axis fixation/ticket-shape conversion only.',
      'selected_config':best,
      'ticket_shapes':{
        'AXIS7':'top1 fixed; 7 trio combinations when score gap is strong',
        'DUAL9':'top2 centered; up to 9 combinations when two horses form the core',
        'GROUP10':'top5 box-like 10 combinations when axis fixation is weak'
      },
      'calibration_result':train_score,
      'holdout_result':test_score,
      'limitations':['Only one weekend is available. Holdout sample remains small.','This is a PDCA candidate, not production promotion.','Odds/popularity are excluded from horse ranking and calibration.']
    }
    OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(exist_ok=True)
    raw=json.dumps(out,ensure_ascii=False,indent=2)
    OUT.write_text(raw,encoding='utf-8');STATUS.write_text(raw,encoding='utf-8')
    print(raw)
if __name__=='__main__':main()
