#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
import csv
import sys
sys.path.insert(0,'src')
from axis_survival_shadow import post_result_scenario_audit

SCORES=Path('docs/data/live_prediction_scores.json')
OUT=Path('docs/data/live_pdca.json')
STATUS=Path('status/live_pdca.json')
SEALED=Path('docs/data/live_predictions_sealed.json')
RESULTS=Path('data/race_results_html_2026.csv')

def _load_json(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return default

def _result_rows():
    if not RESULTS.exists():return []
    with RESULTS.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    d=json.loads(SCORES.read_text(encoding='utf-8')) if SCORES.exists() else {'summary':{},'races':[],'pending':[]}
    races=d.get('races') or []
    sealed=_load_json(SEALED,{'races':[]})
    seal_by={(str(x.get('date') or ''),str(x.get('track') or ''),int(x.get('race_no') or 0)):x for x in sealed.get('races') or []}
    result_map={}
    for rr in _result_rows():
        try:key=(str(rr.get('race_date') or ''),str(rr.get('course') or '').replace('競馬場',''),int(rr.get('race_no') or 0),str(int(float(rr.get('horse_no') or 0))))
        except Exception:continue
        result_map[key]=rr
    scenario_audits=[]
    for x in races:
        try:k=(str(x.get('date') or ''),str(x.get('track') or ''),int(x.get('race_no') or 0))
        except Exception:continue
        pred=seal_by.get(k) or {}
        shadow=((pred.get('analysis') or {}).get('axis_survival_shadow') or {})
        axis=(shadow.get('axis') or {})
        no=str(axis.get('horse_no') or '')
        rr=result_map.get((k[0],k[1],k[2],no))
        if not rr:continue
        audit=post_result_scenario_audit(axis,rr.get('corner_positions'),rr.get('finish_position'))
        scenario_audits.append({'date':k[0],'track':k[1],'race_no':k[2],'axis':axis,'corner_positions':rr.get('corner_positions'),'audit':audit})
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
    scenario_quality=Counter((x.get('audit') or {}).get('prediction_quality') for x in scenario_audits)
    payload={'mode':'POST_RESULT_PDCA_ONLY','source_prediction_hash_sha256':(d.get('summary') or {}).get('source_prediction_hash_sha256'),'sealed_predictions_mutated':False,'scored_race_count':len(races),'pending_race_count':len(d.get('pending') or []),'failure_counts':failure_counts,'by_decision':by_decision,'recommended_actions':actions,'axis_learning_objective':'TOP3_SURVIVAL_FIRST','axis_scenario_audits':scenario_audits,'axis_scenario_quality_counts':dict(scenario_quality),'governance':'PDCA output is diagnostic only; it does not automatically rewrite the certified production model.'}
    OUT.parent.mkdir(exist_ok=True);STATUS.parent.mkdir(exist_ok=True)
    txt=json.dumps(payload,ensure_ascii=False,indent=2);OUT.write_text(txt,encoding='utf-8');STATUS.write_text(txt,encoding='utf-8');print(json.dumps(payload,ensure_ascii=False))
if __name__=='__main__':main()
