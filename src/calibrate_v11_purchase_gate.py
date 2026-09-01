#!/usr/bin/env python3
from __future__ import annotations
import hashlib,itertools,json,math
from pathlib import Path
PRED=Path('docs/data/oral-v10-72-connected-durability-sealed.json')
SCORE=Path('docs/data/oral-v10-72-connected-durability-scored.json')
OUT=Path('status/oral-v11-purchase-gate-config.json')
TRAIN='2026-08-29'

def f(v,d=0.0):
    try:return float(v)
    except:return d

def main():
    p=json.loads(PRED.read_text());s=json.loads(SCORE.read_text())
    sm={(x['date'],x['track'],int(x['race_no'])):x for x in s['races'] if x['date']==TRAIN}
    rows=[]
    for r in p['races']:
        if r['date']!=TRAIN:continue
        sc=sm.get((r['date'],r['track'],int(r['race_no'])));a=r['analysis'];d=a.get('axis_durability') or {}
        if not sc:continue
        rows.append({'score':f(d.get('score')),'gap':f(d.get('gap_to_second')),'unc':f(d.get('uncertainty'),1),'top3':sc['axis_grade'] in ('HIT','PLACE'),'win':sc['axis_grade']=='HIT'})
    assert len(rows)==36
    best=None;candidates=[]
    score_lows=[0,35,40,45,50,55,60]
    score_highs=[50,55,60,65,70,80,101]
    gap_mins=[0,1,2,3,4,5]
    gap_maxs=[4,6,8,12,999]
    unc_maxs=[.4,.6,.8,1.01]
    for lo,hi,glo,ghi,umax in itertools.product(score_lows,score_highs,gap_mins,gap_maxs,unc_maxs):
        if lo>=hi or glo>ghi:continue
        xs=[x for x in rows if lo<=x['score']<hi and glo<=x['gap']<=ghi and x['unc']<=umax]
        n=len(xs)
        if n<8 or n>14:continue
        top=sum(x['top3'] for x in xs);wins=sum(x['win'] for x in xs);rate=top/n;wr=wins/n
        # Precision first, but penalize tiny subsets and require a practical number of bets.
        objective=rate + .12*wr + .012*math.sqrt(n)
        cand={'score_min':lo,'score_max_exclusive':hi,'gap_min':glo,'gap_max':ghi,'uncertainty_max':umax,'train_selected':n,'train_axis_top3':top,'train_axis_wins':wins,'train_axis_top3_rate_pct':round(rate*100,2),'train_axis_win_rate_pct':round(wr*100,2),'objective':round(objective,6)}
        candidates.append(cand)
        if best is None or (cand['objective'],cand['train_selected'])>(best['objective'],best['train_selected']):best=cand
    assert best is not None
    payload={'version':'V11_PURCHASE_GATE_CALIBRATION','train_date':TRAIN,'holdout_date':'2026-08-30','result_fields_used_for_training':['axis_grade on train_date only'],'holdout_results_accessed_for_calibration':False,'minimum_train_purchases':8,'maximum_train_purchases':14,'selected_rule':best,'candidate_count':len(candidates),'policy':'No track/race identity, popularity, odds, or holdout result may enter the gate. Rule is sealed before holdout scoring.'}
    canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['config_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print(json.dumps(payload,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
