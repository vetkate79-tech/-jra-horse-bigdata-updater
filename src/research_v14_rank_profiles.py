#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

SETS = {
    '2026-08-22-23': Path('docs/data/replay-holdout-2026-08-22-23.json'),
    '2026-08-29-30': Path('docs/data/replay-demo-2026-08-29-30.json'),
}
OUT = Path('status/oral-v14-rank-profile-research.json')

PROFILES = {
    'baseline_original': None,
    'balanced': {'show': .35, 'recent': .30, 'cond': .20, 'reliability': .10, 'starts': .00, 'original': .05},
    'recent_condition': {'show': .25, 'recent': .35, 'cond': .25, 'reliability': .10, 'starts': .00, 'original': .05},
    'stable_condition': {'show': .40, 'recent': .20, 'cond': .25, 'reliability': .10, 'starts': .00, 'original': .05},
    'evidence_balanced': {'show': .30, 'recent': .25, 'cond': .20, 'reliability': .15, 'starts': .05, 'original': .05},
    'recent_reliable': {'show': .30, 'recent': .35, 'cond': .15, 'reliability': .15, 'starts': .00, 'original': .05},
    'condition_reliable': {'show': .30, 'recent': .20, 'cond': .30, 'reliability': .15, 'starts': .00, 'original': .05},
}


def f(v, d=0.0):
    try: return float(v)
    except Exception: return d


def actual_top3(r):
    return {str(x).split()[0] for x in (r.get('result_top3') or []) if str(x).split()}


def can_rescore(q):
    if len(q) < 6: return False
    evidence = sum(1 for h in q if f(h.get('starts_before')) >= 1)
    vals = []
    for h in q:
        vals.extend([f(h.get('show_rate_prior'), .3), f(h.get('recent_form'), .35), f(h.get('condition_fit'), .3)])
    return evidence >= 4 and (max(vals) - min(vals) >= .08 if vals else False)


def rerank(q, w):
    if not w or not can_rescore(q): return list(q), False
    scores = [f(h.get('score')) for h in q]
    lo, hi = min(scores), max(scores)
    def orig_norm(h):
        x = f(h.get('score'))
        return .5 if hi <= lo else (x - lo) / (hi - lo)
    def score(h):
        show = max(0.0, min(1.0, f(h.get('show_rate_prior'), .3)))
        recent = max(0.0, min(1.0, f(h.get('recent_form'), .35)))
        cond = max(0.0, min(1.0, f(h.get('condition_fit'), .3)))
        unc = max(0.0, min(1.0, f(h.get('uncertainty'), 1.0)))
        starts = min(1.0, f(h.get('starts_before')) / 8.0)
        return (
            w['show'] * show + w['recent'] * recent + w['cond'] * cond +
            w['reliability'] * (1.0 - unc) + w['starts'] * starts +
            w['original'] * orig_norm(h)
        )
    out = [dict(h, v14_research_score=round(score(h), 6)) for h in q]
    out.sort(key=lambda h: (-h['v14_research_score'], int(str(h.get('n'))) if str(h.get('n')).isdigit() else 999))
    return out, True


def evaluate(rows, w):
    s = {'races': 0, 'rescored_races': 0, 'axis_top3': 0, 'top3_in_top6': 0, 'top3_in_top5': 0}
    for r in rows:
        q = r.get('ranked_snapshot') or []
        actual = actual_top3(r)
        if len(q) < 3 or len(actual) < 3: continue
        qq, changed = rerank(q, w)
        s['races'] += 1
        s['rescored_races'] += int(changed)
        s['axis_top3'] += int(str(qq[0].get('n')) in actual)
        s['top3_in_top6'] += int(actual.issubset({str(x.get('n')) for x in qq[:6]}))
        s['top3_in_top5'] += int(actual.issubset({str(x.get('n')) for x in qq[:5]}))
    n = s['races'] or 1
    for key in ('axis_top3', 'top3_in_top6', 'top3_in_top5'):
        s[key + '_pct'] = round(100 * s[key] / n, 2)
    return s


def load_rows(label, path):
    d = json.loads(path.read_text(encoding='utf-8'))
    if label == '2026-08-22-23':
        allowed = {'2026-08-22', '2026-08-23'}
    else:
        allowed = {'2026-08-29', '2026-08-30'}
    return [r for r in d.get('races', []) if r.get('date') in allowed and r.get('ranked_snapshot') and r.get('result_top3')]


def main():
    datasets = {label: load_rows(label, path) for label, path in SETS.items()}
    results = {}
    for name, w in PROFILES.items():
        results[name] = {label: evaluate(rows, w) for label, rows in datasets.items()}
    # Cross-week score rewards improvements that repeat on both weekends, not a single-week peak.
    baseline = results['baseline_original']
    consistency = []
    for name, byset in results.items():
        if name == 'baseline_original': continue
        deltas = {}
        worst = 999.0
        total = 0.0
        for label in datasets:
            a = byset[label]; b = baseline[label]
            axis_delta = a['axis_top3_pct'] - b['axis_top3_pct']
            cover_delta = a['top3_in_top6_pct'] - b['top3_in_top6_pct']
            deltas[label] = {'axis_delta_pct': round(axis_delta, 2), 'top6_cover_delta_pct': round(cover_delta, 2)}
            composite = axis_delta + cover_delta
            worst = min(worst, composite)
            total += composite
        consistency.append({'profile': name, 'worst_week_composite_delta': round(worst, 2), 'sum_composite_delta': round(total, 2), 'deltas': deltas})
    consistency.sort(key=lambda x: (-x['worst_week_composite_delta'], -x['sum_composite_delta'], x['profile']))
    out = {
        'mode': 'V1.4_RANK_PROFILE_RESEARCH',
        'leakage_note': 'Only already-sealed pre-race feature snapshots are rescored. Results are used solely by this research evaluator after scoring. These are no longer pristine holdouts; a future unseen weekend is required before promotion.',
        'results': results,
        'cross_week_consistency': consistency,
        'recommended_shadow_profile': consistency[0]['profile'] if consistency else None,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'recommended': out['recommended_shadow_profile'], 'consistency': consistency, 'results': results}, ensure_ascii=False))


if __name__ == '__main__': main()
