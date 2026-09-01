#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

PARITY=Path('docs/data/oral-system-parity-audit.json')
CASES=Path('docs/data/oral-parity-case-details.json')
SHADOW=Path('docs/data/oral-integrated-v1-shadow-sealed.json')
OUT=Path('docs/data/oral-system-final-audit.json')
STATUS=Path('status/oral-system-final-audit.json')

def main():
    p=json.loads(PARITY.read_text())
    c=json.loads(CASES.read_text())
    s=json.loads(SHADOW.read_text())
    compact=[]
    for x in c.get('cases',[]):
        a=x.get('actual',{}); y=x.get('system',{})
        actual_axis=str(a.get('axis') or '').split()[0]
        system_axis=str((y.get('axis') or {}).get('horse_no') or '')
        actual_dec=a.get('decision')
        system_dec=y.get('decision')
        actual_tickets=sorted(a.get('tickets') or [])
        system_tickets=sorted(y.get('tickets') or [])
        compact.append({
            'date':x.get('date'),'track':x.get('track'),'race_no':x.get('race_no'),'race_name':x.get('race_name'),
            'axis_actual':actual_axis,'axis_system':system_axis,'axis_match':actual_axis==system_axis,
            'decision_actual':actual_dec,'decision_system':system_dec,'decision_match':actual_dec==system_dec,
            'ticket_count_actual':len(actual_tickets),'ticket_count_system':len(system_tickets),
            'tickets_exact_match':bool(actual_tickets and actual_tickets==system_tickets),
            'partner_actual':[str(v).split()[0] for v in a.get('partners',[])],
            'partner_system':[str(v.get('horse_no')) for v in (y.get('partner_roles') or [])[:5]],
        })
    inv=p['invariant_tests']; hp=p['historical_chat_parity']
    tests=[
        {'id':'T01_REPEATABILITY_72R','passed':inv['same_input_repeat']['passed'],'detail':'72Rを同一入力で2回実行して完全同一出力'},
        {'id':'T02_RESULT_ISOLATION_72R','passed':inv['result_isolation']['passed'],'detail':'結果・払戻を注入しても事前予想が変化しない'},
        {'id':'T03_MARKET_ISOLATION_72R','passed':inv['odds_popularity_isolation']['passed'],'detail':'人気・オッズを注入しても純予想が変化しない'},
        {'id':'T04_AXIS_BRANCH','passed':inv['ticket_shape_coverage'].get('AXIS',0)>0,'detail':f"AXISケース {inv['ticket_shape_coverage'].get('AXIS',0)}R"},
        {'id':'T05_DUAL_BRANCH','passed':inv['ticket_shape_coverage'].get('DUAL',0)>0,'detail':f"DUALケース {inv['ticket_shape_coverage'].get('DUAL',0)}R"},
        {'id':'T06_PASS_BRANCH','passed':inv['ticket_shape_coverage'].get('PASS',0)>0,'detail':f"PASSケース {inv['ticket_shape_coverage'].get('PASS',0)}R"},
        {'id':'T07_ARCHIVE_COVERAGE','passed':hp['coverage_rate']==1,'detail':f"実会話ログ {hp['system_joinable_logs']}/{hp['actual_pre_race_logs']}Rを同条件比較可能"},
        {'id':'T08_AXIS_PARITY','passed':hp['axis']['match_rate']==1,'detail':f"軸一致 {hp['axis']['matches']}/{hp['axis']['comparable']}"},
        {'id':'T09_DECISION_PARITY','passed':hp['decision']['match_rate']==1,'detail':f"判断一致 {hp['decision']['matches']}/{hp['decision']['comparable']}"},
        {'id':'T10_TICKET_PARITY','passed':hp['tickets']['match_rate']==1,'detail':f"買い目完全一致 {hp['tickets']['matches']}/{hp['tickets']['comparable']}"},
    ]
    hard=[x for x in tests if x['id'] in ('T07_ARCHIVE_COVERAGE','T08_AXIS_PARITY','T09_DECISION_PARITY','T10_TICKET_PARITY')]
    verdict='COMPLETE' if all(x['passed'] for x in tests) else 'NOT_COMPLETE'
    out={
        'audit_version':'ORAL_SYSTEM_FINAL_AUDIT_V1',
        'system_model_version':s.get('version'),
        'verdict':verdict,
        'systemization_complete':verdict=='COMPLETE',
        'tests':tests,
        'historical_case_comparisons':compact,
        'hard_blockers':[x for x in hard if not x['passed']],
        'interpretation':{
            'engine_stability':'PASS' if all(x['passed'] for x in tests[:6]) else 'FAIL',
            'oral_output_parity':'PASS' if all(x['passed'] for x in hard) else 'FAIL',
            'rule':'システム化完了は、安定稼働だけでなく保存済み実会話出力との完全パリティを必須とする。検証不能ケースを一致扱いしない。'
        }
    }
    txt=json.dumps(out,ensure_ascii=False,indent=2)
    OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(txt)
    print(txt)
if __name__=='__main__':main()
