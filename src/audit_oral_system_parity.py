#!/usr/bin/env python3
from __future__ import annotations
import copy, hashlib, json, re, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, 'src')
from oral_operational_layer import analyze_race, MODEL_VERSION

ARCHIVE = Path('docs/data/replay-demo-2026-08-29-30.json')
BASE = Path('docs/data/replay-2026-08-29-30-sealed.json')
SYSTEM = Path('docs/data/oral-integrated-v1-shadow-sealed.json')
OUT = Path('docs/data/oral-system-parity-audit.json')
STATUS = Path('status/oral-system-parity-audit.json')


def key(r):
    return (str(r.get('date') or ''), str(r.get('track') or ''), int(r.get('race_no') or 0))


def horse_no(v):
    m = re.match(r'\s*(\d+)', str(v or ''))
    return m.group(1) if m else ''


def horse_nos(values):
    return [horse_no(x) for x in (values or []) if horse_no(x)]


def stable(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def actual_decision(r):
    if r.get('decision') in ('BUY', 'CAUTION', 'PASS'):
        return r['decision']
    if '見送り' in str(r.get('type_label') or ''):
        return 'PASS'
    return None


def infer_actual_shape(r):
    txt = ' '.join(str(r.get(x) or '') for x in ('formation', 'pre_note', 'type_label'))
    if r.get('decision') == 'PASS' or '見送り' in txt:
        return 'PASS'
    if '1頭軸' in txt:
        return 'AXIS'
    if '2頭' in txt or '2軸' in txt:
        return 'DUAL'
    if '上位群' in txt or 'BOX' in txt or 'ボックス' in txt:
        return 'GROUP'
    return None


def main():
    archive = json.loads(ARCHIVE.read_text())
    base = json.loads(BASE.read_text())
    system = json.loads(SYSTEM.read_text())

    actual_rows = [r for r in archive.get('races', []) if str(r.get('prediction_source', '')).startswith('PRE_RACE_CONVERSATION_LOG')]
    system_by_key = {key(r): r for r in system.get('races', [])}
    base_by_key = {key(r): r for r in base.get('races', [])}

    comparisons = []
    for a in actual_rows:
        k = key(a)
        srow = system_by_key.get(k)
        sysa = (srow or {}).get('analysis') or {}
        aa = horse_no(a.get('axis'))
        sa = str((sysa.get('axis') or {}).get('horse_no') or '')
        ap = horse_nos(a.get('partners'))
        sp = [str(x.get('horse_no') or '') for x in (sysa.get('partner_roles') or [])[:5]]
        actual_tickets = sorted(set(str(x) for x in (a.get('tickets') or [])))
        system_tickets = sorted(set(str(x) for x in (sysa.get('trio_tickets') or [])))
        ad = actual_decision(a)
        sd = sysa.get('pre_market_decision') if srow else None
        ash = infer_actual_shape(a)
        ssh = sysa.get('ticket_shape') if srow else None
        partner_overlap = len(set(ap) & set(sp))
        partner_recall = round(partner_overlap / len(set(ap)), 4) if ap else None
        ticket_exact = (actual_tickets == system_tickets) if actual_tickets else None
        row = {
            'date': k[0], 'track': k[1], 'race_no': k[2], 'race_name': a.get('race_name'),
            'source': a.get('prediction_source'), 'system_available': bool(srow),
            'axis': {'actual': aa, 'system': sa or None, 'match': bool(srow and aa and aa == sa)},
            'decision': {'actual': ad, 'system': sd, 'match': (ad == sd) if (srow and ad is not None) else None},
            'ticket_shape': {'actual': ash, 'system': ssh, 'match': (ash == ssh) if (srow and ash is not None) else None},
            'partners': {'actual': ap, 'system_top5': sp, 'overlap': partner_overlap, 'recall': partner_recall},
            'tickets': {'actual_count': len(actual_tickets), 'system_count': len(system_tickets), 'exact_match': ticket_exact},
            'archive_has_enough_for_full_parity': bool(aa and ad is not None and ash is not None and actual_tickets),
        }
        comparisons.append(row)

    # Determinism: identical input must produce byte-identical analysis on repeated calls.
    repeat_failures = []
    result_leak_failures = []
    market_leak_failures = []
    shape_counts = Counter()
    classification_counts = Counter()
    for r in base.get('races', []):
        a1 = analyze_race(copy.deepcopy(r))
        a2 = analyze_race(copy.deepcopy(r))
        if stable(a1) != stable(a2):
            repeat_failures.append(key(r))
        shape_counts[a1.get('ticket_shape', 'UNKNOWN')] += 1
        classification_counts[a1.get('classification', 'UNKNOWN')] += 1

        # Inject outcome fields that must never alter pre-race output.
        mutated = copy.deepcopy(r)
        mutated.update({'result_top3': ['99 X', '98 Y', '97 Z'], 'trio_result': '97-98-99', 'trio_payout': 999999, 'hit': True, 'return_amount': 999999})
        if stable(a1) != stable(analyze_race(mutated)):
            result_leak_failures.append(key(r))

        # Inject/overwrite market fields that must never alter the pure pre-market output.
        market = copy.deepcopy(r)
        market.update({'odds': 1.1, 'popularity': 1, 'market_rank': 1})
        for i, h in enumerate(market.get('ranked_snapshot') or []):
            h['odds'] = 1.1 + i
            h['popularity'] = i + 1
            h['market_rank'] = i + 1
        if stable(a1) != stable(analyze_race(market)):
            market_leak_failures.append(key(r))

    joinable = [x for x in comparisons if x['system_available']]
    axis_comparable = [x for x in joinable if x['axis']['actual']]
    axis_matches = sum(1 for x in axis_comparable if x['axis']['match'])
    decision_comparable = [x for x in joinable if x['decision']['actual'] is not None]
    decision_matches = sum(1 for x in decision_comparable if x['decision']['match'])
    shape_comparable = [x for x in joinable if x['ticket_shape']['actual'] is not None]
    shape_matches = sum(1 for x in shape_comparable if x['ticket_shape']['match'])
    ticket_comparable = [x for x in joinable if x['tickets']['actual_count'] > 0]
    ticket_matches = sum(1 for x in ticket_comparable if x['tickets']['exact_match'])

    total_actual = len(actual_rows)
    coverage = round(len(joinable) / total_actual, 4) if total_actual else 0
    axis_rate = round(axis_matches / len(axis_comparable), 4) if axis_comparable else None
    decision_rate = round(decision_matches / len(decision_comparable), 4) if decision_comparable else None
    shape_rate = round(shape_matches / len(shape_comparable), 4) if shape_comparable else None
    ticket_rate = round(ticket_matches / len(ticket_comparable), 4) if ticket_comparable else None

    blockers = []
    if coverage < 1:
        blockers.append('保存済み実会話予想の全日付を現行Shadow入力で再実行できていない')
    if axis_rate is not None and axis_rate < 1:
        blockers.append('実会話予想とシステムの軸が完全一致していない')
    if decision_rate is not None and decision_rate < 1:
        blockers.append('BUY/CAUTION/PASSが実会話予想と完全一致していない')
    if shape_rate is not None and shape_rate < 1:
        blockers.append('券型が実会話予想と完全一致していない')
    if ticket_rate is not None and ticket_rate < 1:
        blockers.append('最終買い目が実会話予想と完全一致していない')
    if repeat_failures:
        blockers.append('同一入力で出力が再現しないケースがある')
    if result_leak_failures:
        blockers.append('結果フィールド混入で事前分析が変化する')
    if market_leak_failures:
        blockers.append('オッズ/人気混入で純予想が変化する')

    complete = not blockers and total_actual > 0
    out = {
        'audit_version': 'ORAL_SYSTEM_PARITY_AUDIT_V1',
        'system_model_version': MODEL_VERSION,
        'verdict': 'COMPLETE_PARITY' if complete else 'NOT_COMPLETE',
        'systemization_complete': complete,
        'historical_chat_parity': {
            'actual_pre_race_logs': total_actual,
            'system_joinable_logs': len(joinable),
            'coverage_rate': coverage,
            'axis': {'comparable': len(axis_comparable), 'matches': axis_matches, 'match_rate': axis_rate},
            'decision': {'comparable': len(decision_comparable), 'matches': decision_matches, 'match_rate': decision_rate},
            'ticket_shape': {'comparable': len(shape_comparable), 'matches': shape_matches, 'match_rate': shape_rate},
            'tickets': {'comparable': len(ticket_comparable), 'matches': ticket_matches, 'match_rate': ticket_rate},
        },
        'invariant_tests': {
            'race_count': len(base.get('races', [])),
            'same_input_repeat': {'passed': not repeat_failures, 'failures': repeat_failures},
            'result_isolation': {'passed': not result_leak_failures, 'failures': result_leak_failures},
            'odds_popularity_isolation': {'passed': not market_leak_failures, 'failures': market_leak_failures},
            'ticket_shape_coverage': dict(shape_counts),
            'classification_coverage': dict(classification_counts),
        },
        'blockers': blockers,
        'comparisons': comparisons,
        'audit_note': '実会話ログで保存されていない相手・除外・買い目は一致判定不能とし、推測で補完しない。再現予想は実会話とのパリティ母集団に含めない。',
    }
    raw = json.dumps(out, ensure_ascii=False, indent=2)
    OUT.write_text(raw)
    STATUS.parent.mkdir(exist_ok=True)
    STATUS.write_text(raw)
    print(raw)


if __name__ == '__main__':
    main()
