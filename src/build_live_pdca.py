#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

SCORES=Path('docs/data/live_prediction_scores.json')
OUT=Path('docs/data/live_pdca.json')
STATUS=Path('status/live_pdca.json')

def main():
    d=json.loads(SCORES.read_text(encoding='utf-8')) if SCORES.exists() else {'summary':{},'races':[],'pending':[]}
    races=d.get('races') or []
    grade=Counter(r.get('axis_grade') for r in races)
    by_decision={}
    for dec in ('BUY','CAUTION','PASS'):
        xs=[r for r in races if r.get('decision')==dec]
        if xs:
            c=Counter(r.get('axis_grade') for r in xs)
            by_decision[dec]={'races':len(xs),'axis_1st':c['HIT'],'axis_2nd_3rd':c['PLACE'],'axis_out':c['MISS'],'axis_top3_rate_pct':round((c['HIT']+c['PLACE'])/len(xs)*100,2)}
    failure_counts={
      'axis_outside_top3':grade['MISS'],
      'axis_survived_but_trio_missed':sum(1 for r in races if r.get('axis_grade') in ('HIT','PLACE') and r.get('decision')!='PASS' and not r.get('trio_hit')),
      'axis_and_trio_hit':sum(1 for r in races if r.get('axis_grade') in ('HIT','PLACE') and r.get('trio_hit'))
    }
    actions=[]
    if failure_counts['axis_outside_top3']>failure_counts['axis_survived_but_trio_missed']:
        actions.append('優先課題: 買い目拡張より軸選定・軸耐久性の改善を優先')
    if failure_counts['axis_survived_but_trio_missed']>0:
        actions.append('相手役割分散・3着侵入・相手内完結の取りこぼしを個別監査')
    if not races:actions.append('結果接続待ち。予想ロジックを結果なしで変更しない')
    payload={'mode':'POST_RESULT_PDCA_ONLY','source_prediction_hash_sha256':(d.get('summary') or {}).get('source_prediction_hash_sha256'),'sealed_predictions_mutated':False,'scored_race_count':len(races),'pending_race_count':len(d.get('pending') or []),'failure_counts':failure_counts,'by_decision':by_decision,'recommended_actions':actions,'governance':'PDCA output is diagnostic only; it does not automatically rewrite the certified production model.'}
    OUT.parent.mkdir(exist_ok=True);STATUS.parent.mkdir(exist_ok=True)
    txt=json.dumps(payload,ensure_ascii=False,indent=2);OUT.write_text(txt,encoding='utf-8');STATUS.write_text(txt,encoding='utf-8');print(json.dumps(payload,ensure_ascii=False))
if __name__=='__main__':main()
