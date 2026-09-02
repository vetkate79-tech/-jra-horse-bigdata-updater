#!/usr/bin/env python3
"""Build leakage-safe pre-race features for verified upcoming JRA runners.

The cutoff is the earliest upcoming race date. Results on/after that cutoff are
never read into feature calculation, so Saturday results cannot leak into a
Sunday prediction sealed earlier in the week.
"""
from __future__ import annotations
import csv, json, re
from collections import defaultdict
from pathlib import Path

WEEKLY = Path('docs/data/horses/weekly_runner_details.json')
OUT = Path('docs/data/horses/pre_race_features.json')
STATUS = Path('status/pre_race_features.json')
RESULT_SOURCES = (Path('data/race_results_html_2025.csv'), Path('data/race_results_html_2026.csv'))


def num(v, d=None):
    try: return float(str(v).replace(',', ''))
    except Exception: return d


def integer(v, d=None):
    m = re.search(r'\d+', str(v or ''))
    return int(m.group()) if m else d


def load_rows():
    out = []
    for p in RESULT_SOURCES:
        if not p.exists() or p.stat().st_size == 0: continue
        with p.open(encoding='utf-8-sig', newline='') as f:
            out.extend(csv.DictReader(f))
    return out


def norm_surface(v):
    s = str(v or '')
    if '芝' in s: return '芝'
    if 'ダ' in s: return 'ダート'
    return ''


def parse_corners(v):
    return [int(x) for x in re.findall(r'\d+', str(v or ''))]


def style_from_history(hist, field_sizes):
    samples = []
    for r in hist:
        rid = r.get('race_id') or ''
        corners = parse_corners(r.get('corner_positions'))
        n = field_sizes.get(rid, 0)
        if not corners or n < 3: continue
        first, last = corners[0], corners[-1]
        a = max(0.0, min(1.0, (first - 1) / max(1, n - 1)))
        b = max(0.0, min(1.0, (last - 1) / max(1, n - 1)))
        samples.append((first, a, b))
    if not samples: return 'UNKNOWN', 0
    escape = sum(1 for first, _, _ in samples if first == 1) / len(samples)
    avg = sum((a + b) / 2 for _, a, b in samples) / len(samples)
    if escape >= .5 or avg <= .07: return 'ESCAPE', len(samples)
    if avg <= .28: return 'FRONT', len(samples)
    if avg <= .45: return 'STALK', len(samples)
    if avg <= .70: return 'CLOSER', len(samples)
    return 'DEEP_CLOSER', len(samples)


def trainer_rates(rows):
    b = defaultdict(lambda: [0, 0])
    for r in rows:
        finish = integer(r.get('finish_position'))
        trainer = str(r.get('trainer') or '').strip()
        if finish is None or not trainer: continue
        b[trainer][0] += 1
        b[trainer][1] += int(finish <= 3)
    def rate(name):
        n, x = b.get(str(name or '').strip(), [0, 0])
        return (x + 2) / (n + 8) if n else .25
    return rate


def feature_for(runner, hist, tr_rate, field_sizes):
    race = runner.get('race') or {}
    starts = len(hist)
    top3 = sum(integer(x.get('finish_position'), 99) <= 3 for x in hist)
    show = (top3 + 1.5) / (starts + 5) if starts else .30

    recent = hist[:5]
    if recent:
        ws = [5, 4, 3, 2, 1][:len(recent)]
        rec = sum(w * (1 / max(1, min(18, integer(x.get('finish_position'), 18)))) for w, x in zip(ws, recent)) / sum(ws)
        rec = min(1.0, rec * 3.2)
    else:
        rec = .35

    target_surface = norm_surface(race.get('surface'))
    target_distance = integer(race.get('distance_m'))
    matches = []
    if target_surface and target_distance:
        for x in hist:
            surface = norm_surface(x.get('surface'))
            distance = integer(x.get('distance_m'))
            if surface == target_surface and distance and abs(distance - target_distance) <= 300:
                matches.append(x)
    cond = (sum(integer(x.get('finish_position'), 99) <= 3 for x in matches) + 1) / (len(matches) + 3) if matches else show

    last3f = [num(x.get('last3f')) for x in recent]
    last3f = [x for x in last3f if x is not None]
    l3 = .5 if not last3f else max(0.0, min(1.0, (40 - min(last3f)) / 8))
    uncertainty = 1 - min(1.0, starts / 5)
    trainer = runner.get('trainer') or ''
    tr = tr_rate(trainer)
    style, style_starts = style_from_history(hist, field_sizes)

    score = 45 * show + 25 * rec + 10 * cond + 7 * tr + 5 * l3 - 8 * uncertainty
    return {
        'starts_before': starts,
        'show_rate_prior': round(show, 4),
        'recent_form': round(rec, 4),
        'condition_fit': round(cond, 4),
        'uncertainty': round(uncertainty, 4),
        'trainer_show_prior': round(tr, 4),
        'last3f_signal': round(l3, 4),
        'pre_race_running_style': style,
        'running_style_sample_starts': style_starts,
        'pre_race_score': round(score, 3),
        'pre_race_score_source': 'JRA_STORED_HISTORY_STRICT_CUTOFF_V1',
    }


def main():
    weekly = json.loads(WEEKLY.read_text(encoding='utf-8')) if WEEKLY.exists() else {'runners': []}
    runners = weekly.get('runners') or []
    dates = sorted({str((x.get('race') or {}).get('date') or '') for x in runners if (x.get('race') or {}).get('date')})
    if not dates:
        payload = {'summary': {'status': 'NO_UPCOMING_RACECARDS', 'runner_count': 0}, 'features': []}
        OUT.parent.mkdir(parents=True, exist_ok=True); STATUS.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        STATUS.write_text(json.dumps(payload['summary'], ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(payload['summary'], ensure_ascii=False)); return

    cutoff = dates[0]
    rows = [r for r in load_rows() if str(r.get('race_date') or '') and str(r.get('race_date')) < cutoff]
    rows.sort(key=lambda r: str(r.get('race_date') or ''), reverse=True)
    by_horse = defaultdict(list); field_sizes = defaultdict(int)
    for r in rows:
        hid = str(r.get('horse_id') or '')
        rid = str(r.get('race_id') or '')
        if hid: by_horse[hid].append(r)
        if hid and rid: field_sizes[rid] += 1
    tr_rate = trainer_rates(rows)

    feats = []
    for x in runners:
        race = x.get('race') or {}
        hid = str(x.get('horse_id') or '')
        f = feature_for(x, by_horse.get(hid, []), tr_rate, field_sizes)
        feats.append({
            'race_id': race.get('race_id'), 'date': race.get('date'), 'track': race.get('track'),
            'race_no': race.get('race_no'), 'horse_id': hid, 'horse_name': x.get('horse_name'),
            'horse_no': x.get('horse_no'), **f,
        })

    evidence = sum(1 for x in feats if x['starts_before'] > 0)
    summary = {
        'status': 'READY', 'cutoff_date': cutoff, 'runner_count': len(feats),
        'history_rows_before_cutoff': len(rows), 'runners_with_history': evidence,
        'runners_without_history': len(feats) - evidence,
        'results_on_or_after_cutoff_used': False,
        'odds_popularity_used': False,
    }
    payload = {'summary': summary, 'features': feats}
    OUT.parent.mkdir(parents=True, exist_ok=True); STATUS.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    STATUS.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__': main()
