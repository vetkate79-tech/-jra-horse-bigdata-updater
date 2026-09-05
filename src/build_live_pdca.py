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
HISTORY=Path('docs/data/pdca-history')

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
    detailed_failure_audits=[]
    for x in races:
        try:k=(str(x.get('date') or ''),str(x.get('track') or ''),int(x.get('race_no') or 0))
        except Exception:continue
        pred=seal_by.get(k) or {}
        analysis=pred.get('analysis') or {}
        ranked=pred.get('ranked_snapshot') or []
        actual=[str(n) for n in (x.get('actual_top3') or [])]
        candidate_set=set()
        ax=(analysis.get('axis') or {}).get('horse_no')
        if ax:candidate_set.add(str(ax))
        for row in analysis.get('partner_roles') or []:
            if row.get('horse_no') is not None:candidate_set.add(str(row.get('horse_no')))
        for row in analysis.get('third_place_intrusion') or []:
            if row.get('horse_no') is not None:candidate_set.add(str(row.get('horse_no')))
        if not candidate_set:
            candidate_set=set(str(h.get('n')) for h in ranked[:6] if h.get('n') is not None)
        axis_ok=x.get('axis_grade') in ('HIT','PLACE')
        trio_hit=bool(x.get('trio_hit'))
        candidate_complete=bool(actual) and all(n in candidate_set for n in actual)
        if trio_hit:
            failure_type='FULL_SUCCESS'
        elif not axis_ok:
            failure_type='AXIS_MISS'
        elif not candidate_complete:
            failure_type='OPPONENT_CANDIDATE_MISS'
        else:
            failure_type='TICKET_CONVERSION_MISS'
        missed=[n for n in actual if n not in candidate_set]
        position_buckets=[]
        for n in missed:
            rr=result_map.get((k[0],k[1],k[2],n))
            if not rr:continue
            vals=[]
            for token in str(rr.get('corner_positions') or '').replace(',',' ').split():
                try:vals.append(int(token))
                except Exception:pass
            if vals:
                avg=(sum(vals)+vals[-1])/float(len(vals)+1)
                bucket='FRONT' if avg<=3.5 else ('MID' if avg<=7.5 else 'BACK')
                position_buckets.append(bucket)
        detailed_failure_audits.append({
            'date':k[0],'track':k[1],'race_no':k[2],
            'failure_type':failure_type,'axis_top3':axis_ok,'trio_hit':trio_hit,
            'candidate_complete':candidate_complete,'missed_actual_horses':missed,
            'missed_position_buckets':position_buckets,
        })
    detailed_failure_counts=Counter(x.get('failure_type') for x in detailed_failure_audits)
    missed_position_counts=Counter(b for x in detailed_failure_audits for b in x.get('missed_position_buckets') or [])

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
    failure_taxonomy={
      'AXIS_MISS':sum(1 for r in races if r.get('axis_grade')=='MISS'),
      'AXIS_OK_OPPONENT_MISS':sum(1 for r in races if r.get('axis_grade') in ('HIT','PLACE') and r.get('decision')!='PASS' and not r.get('trio_hit')),
      'FULL_SUCCESS':sum(1 for r in races if r.get('trio_hit')),
    }
    actions=[]
    if failure_counts['axis_outside_top3']>failure_counts['axis_survived_but_trio_missed']:
        actions.append('優先課題: 買い目拡張より軸選定・軸耐久性の改善を優先')
    if failure_counts['axis_survived_but_trio_missed']>0:
        actions.append('相手役割分散・3着侵入・相手内完結の取りこぼしを個別監査')
    if not races:actions.append('結果接続待ち。予想ロジックを結果なしで変更しない')
    scenario_quality=Counter((x.get('audit') or {}).get('prediction_quality') for x in scenario_audits)
    payload={'mode':'POST_RESULT_PDCA_ONLY','source_prediction_hash_sha256':(d.get('summary') or {}).get('source_prediction_hash_sha256'),'sealed_predictions_mutated':False,'scored_race_count':len(races),'pending_race_count':len(d.get('pending') or []),'failure_counts':failure_counts,'by_decision':by_decision,'recommended_actions':actions,'axis_learning_objective':'TOP3_SURVIVAL_FIRST','failure_taxonomy':failure_taxonomy,'detailed_failure_counts':dict(detailed_failure_counts),'missed_opponent_position_counts':dict(missed_position_counts),'detailed_failure_audits':detailed_failure_audits,'axis_scenario_audits':scenario_audits,'axis_scenario_quality_counts':dict(scenario_quality),'governance':'PDCA output is diagnostic only; it does not automatically rewrite the certified production model.'}
    OUT.parent.mkdir(exist_ok=True);STATUS.parent.mkdir(exist_ok=True)
    txt=json.dumps(payload,ensure_ascii=False,indent=2)
    dates=sorted({str(x.get('date') or '') for x in races+(d.get('pending') or []) if str(x.get('date') or '')}) or ['undated']
    digest=str(payload.get('source_prediction_hash_sha256') or 'missing-hash')
    for date in dates:
        d=HISTORY/date;d.mkdir(parents=True,exist_ok=True);p=d/(digest+'.json')
        if not p.exists():p.write_text(txt,encoding='utf-8')
        if p.read_text(encoding='utf-8')!=txt:raise RuntimeError('pdca history verification failed: '+str(p))
    OUT.write_text(txt,encoding='utf-8');STATUS.write_text(txt,encoding='utf-8');print(json.dumps(payload,ensure_ascii=False))
if __name__=='__main__':main()
