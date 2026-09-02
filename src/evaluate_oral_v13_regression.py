#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

from oral_operational_layer_v13 import analyze_race, MODEL_VERSION

HOLDOUT = Path('docs/data/replay-holdout-2026-08-22-23.json')
REPLAY = Path('docs/data/replay-demo-2026-08-29-30.json')
OUT = Path('status/oral-v13-regression.json')


def norm_combo(v):
    try:
        xs = [int(x) for x in str(v).split('-') if str(x).strip()]
        return '-'.join(map(str, sorted(xs))) if len(xs) == 3 else ''
    except Exception:
        return ''


def evaluate(rows, label):
    s = {
        'dataset': label,
        'races': 0,
        'buy_races': 0,
        'caution_races': 0,
        'pass_races': 0,
        'axis_top3': 0,
        'candidate_top3_complete': 0,
        'trio_hits_buy': 0,
        'stake_buy': 0,
        'return_buy': 0,
    }
    details = []
    for r in rows:
        ranked = r.get('ranked_snapshot') or []
        top3 = r.get('result_top3') or []
        if not ranked or len(top3) < 3:
            continue
        race_input = {
            'date': r.get('date'),
            'track': r.get('track'),
            'race_no': r.get('race_no'),
            'race_name': r.get('race_name'),
            'surface': r.get('surface'),
            'distance_m': r.get('distance_m'),
            'ranked_snapshot': ranked,
        }
        a = analyze_race(race_input)
        actual = {str(x).split()[0] for x in top3 if str(x).split()}
        axis = str(a.get('axis', {}).get('horse_no', ''))
        cand = {str(x.get('n')) for x in ranked[:6]}
        trio = norm_combo(r.get('trio_result'))
        tickets = {norm_combo(x) for x in a.get('trio_tickets', [])}
        hit = bool(trio and trio in tickets)
        buy = a.get('pre_market_decision') == 'BUY'
        caution = a.get('pre_market_decision') == 'CAUTION'
        payout = int(r.get('trio_payout') or 0)

        s['races'] += 1
        s['buy_races'] += int(buy)
        s['caution_races'] += int(caution)
        s['pass_races'] += int(not buy and not caution)
        s['axis_top3'] += int(axis in actual)
        s['candidate_top3_complete'] += int(actual.issubset(cand))
        if buy:
            s['stake_buy'] += 100 * len(tickets)
            if hit:
                s['trio_hits_buy'] += 1
                s['return_buy'] += payout
        details.append({
            'date': r.get('date'), 'track': r.get('track'), 'race_no': r.get('race_no'),
            'classification': a.get('classification'), 'decision': a.get('pre_market_decision'),
            'axis': axis, 'axis_top3': axis in actual,
            'candidate_top3_complete': actual.issubset(cand),
            'ticket_count': len(tickets), 'trio_hit': hit,
            'race_structure': a.get('race_structure'),
        })

    s['axis_top3_rate_pct'] = round(100 * s['axis_top3'] / s['races'], 2) if s['races'] else 0
    s['candidate_top3_complete_pct'] = round(100 * s['candidate_top3_complete'] / s['races'], 2) if s['races'] else 0
    s['buy_hit_rate_pct'] = round(100 * s['trio_hits_buy'] / s['buy_races'], 2) if s['buy_races'] else 0
    s['buy_roi_pct'] = round(100 * s['return_buy'] / s['stake_buy'], 2) if s['stake_buy'] else 0
    return s, details


def main():
    h = json.loads(HOLDOUT.read_text(encoding='utf-8'))
    r = json.loads(REPLAY.read_text(encoding='utf-8'))
    rows_h = [x for x in h.get('races', []) if x.get('date') in ('2026-08-22', '2026-08-23')]
    rows_r = [x for x in r.get('races', []) if x.get('date') in ('2026-08-29', '2026-08-30')]
    sh, dh = evaluate(rows_h, '2026-08-22-23_seen_regression')
    sr, dr = evaluate(rows_r, '2026-08-29-30_development_regression')
    out = {
        'model_version': MODEL_VERSION,
        'policy': 'No odds/popularity/result fields are passed into analyze_race. These weekends are regression sets only; V1.3 still requires a future unseen holdout before promotion.',
        'summary': [sh, sr],
        'details': {'2026-08-22-23': dh, '2026-08-29-30': dr},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
