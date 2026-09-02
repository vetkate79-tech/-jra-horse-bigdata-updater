#!/usr/bin/env python3
from __future__ import annotations

from oral_operational_layer import (
    _axis_durability,
    _data_quality,
    _intrusion,
    _rank,
    _roles,
    _scenarios,
    _tickets,
)

MODEL_VERSION = 'ORAL_INTEGRATED_V1_3_SHADOW'


def _f(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def _structure(q):
    if not q:
        return {
            'axis_gap': 0.0,
            'top3_boundary_gap': 0.0,
            'top6_spread': 0.0,
            'avg_unc_top3': 1.0,
            'evidence_starts_top5': 0.0,
            'compressed_field': True,
        }
    s = [_f(x.get('score')) for x in q]
    axis_gap = s[0] - s[1] if len(s) > 1 else 0.0
    top3_boundary_gap = s[2] - s[3] if len(s) > 3 else 0.0
    top6_spread = s[0] - s[min(5, len(s) - 1)]
    avg_unc = sum(_f(x.get('uncertainty'), 1.0) for x in q[:3]) / max(1, min(3, len(q)))
    starts = sum(_f(x.get('starts_before')) for x in q[:5])
    compressed = top6_spread < 4.0 or (len(q) > 3 and top3_boundary_gap < 0.30)
    return {
        'axis_gap': round(axis_gap, 3),
        'top3_boundary_gap': round(top3_boundary_gap, 3),
        'top6_spread': round(top6_spread, 3),
        'avg_unc_top3': round(avg_unc, 4),
        'evidence_starts_top5': round(starts, 1),
        'compressed_field': compressed,
    }


def _classification_v13(dur, data_quality, st):
    # V1.3 separates "axis quality" from "race is actually bettable".
    # LOW evidence is never promoted by apparent score spread alone.
    if data_quality == 'LOW':
        return 'PASS'

    gap = st['axis_gap']
    boundary = st['top3_boundary_gap']
    spread = st['top6_spread']
    unc = st['avg_unc_top3']
    starts = st['evidence_starts_top5']

    if dur.get('status') == 'HIGH':
        if data_quality == 'HIGH' and gap >= 2.2 and spread >= 5.0 and boundary >= 0.35 and unc <= 0.45 and starts >= 20:
            return 'A'
        if gap >= 1.5 and spread >= 4.2 and boundary >= 0.30 and unc <= 0.55 and starts >= 15:
            return 'B'
        return 'PASS'

    # MID is audit/caution only. It needs a clearly separated upper group;
    # otherwise the race is too compressed for a trifecta formation.
    if dur.get('status') == 'MID' and spread >= 5.0 and boundary >= 0.45 and unc <= 0.55 and starts >= 18:
        return 'C'
    return 'PASS'


def _trim_tickets(tickets, cls):
    # Keep stake disciplined. Candidate quality must improve before adding combinations.
    cap = 7 if cls in ('A', 'B') else 6
    return list(dict.fromkeys(tickets))[:cap]


def analyze_race(race):
    q = _rank(race)
    axis = q[0] if q else {}
    data_quality = _data_quality(q)
    dur = _axis_durability(q)
    roles = _roles(q)
    intrusion = _intrusion(q, roles)
    scenarios = _scenarios(axis, roles, intrusion)
    st = _structure(q)
    cls = _classification_v13(dur, data_quality, st)

    shape, tickets = _tickets(q, dur, roles, intrusion)
    if cls == 'PASS':
        shape, tickets = 'PASS', []
    else:
        tickets = _trim_tickets(tickets, cls)
        if not tickets:
            cls, shape = 'PASS', 'PASS'

    return {
        'model_version': MODEL_VERSION,
        'axis': {'horse_no': str(axis.get('n', '')), 'horse_name': axis.get('name', '')},
        'axis_durability': dur,
        'race_structure': st,
        'partner_roles': roles,
        'third_place_intrusion': intrusion,
        'failure_scenarios': scenarios,
        'ticket_shape': shape,
        'trio_tickets': tickets,
        'ticket_count': len(tickets),
        'classification': cls,
        'pre_market_decision': 'BUY' if cls in ('A', 'B') else ('CAUTION' if cls == 'C' else 'PASS'),
        'data_quality': data_quality,
        'market_isolation': 'NO_ODDS_OR_POPULARITY_USED',
        'implementation_note': 'V1.3 shadow: conservative race-selection gate separates axis strength from race bettability; compressed fields are passed and ticket count is capped.'
    }
