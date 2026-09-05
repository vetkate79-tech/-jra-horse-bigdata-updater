#!/usr/bin/env python3
from __future__ import annotations

def _f(v,d=0.0):
    try:return float(v)
    except:return d

def select_low_rank_intrusion(race, ranked_snapshot):
    """
    August PDCA-derived, research-only opponent intrusion flag.
    Never changes ability ranking. It only identifies a 7th-10th ranked horse
    that may deserve one-for-one ticket substitution in volatile/CAUTION races.
    """
    q=list(ranked_snapshot or [])
    dist=_f((race or {}).get("distance_m"),0)
    if len(q)<7 or dist>=1400:
        return {"status":"NO_FLAG","reason":"scope_gate","production_override_applied":False}
    best=None
    for i,h in enumerate(q[6:10],start=7):
        score=(
            .5*_f(h.get("score"))+
            40*_f(h.get("recent_form"),.35)+
            15*(1-_f(h.get("uncertainty"),1))+
            5*min(_f(h.get("starts_before"),0),6)/6-
            1*(i-7)
        )
        row={
            "horse_no":str(h.get("n") or ""),
            "horse_name":h.get("name") or "",
            "rank":i,
            "intrusion_score":round(score,3),
            "recent_form":_f(h.get("recent_form"),.35),
            "uncertainty":_f(h.get("uncertainty"),1),
            "starts_before":_f(h.get("starts_before"),0),
        }
        if best is None or row["intrusion_score"]>best["intrusion_score"]:
            best=row
    if not best or best["intrusion_score"]<30:
        return {"status":"NO_FLAG","reason":"score_gate","production_override_applied":False}
    return {
        "status":"FLAG",
        "architecture":"OPPONENT_INTRUSION_SHADOW_V1_CAUTION_SHORT",
        "candidate":best,
        "activation_gate":{
            "classification":"CAUTION_ONLY",
            "distance_m":"<1400",
            "point_policy":"ONE_FOR_ONE_REPLACEMENT_ONLY",
            "buy_rule":"BUY races are never altered by this shadow",
        },
        "purpose":"点数を増やさず、短距離の荒れ側で7〜10位からの3着侵入を監査",
        "production_override_applied":False,
        "market_isolation":"NO_ODDS_OR_POPULARITY_USED",
    }
