#!/usr/bin/env python3
from __future__ import annotations

def _f(v,d=0.0):
    try:return float(v)
    except:return d

def score_low_rank_intrusion(ranked_snapshot, surface=None, distance_m=None):
    q=list(ranked_snapshot or [])
    if len(q)<7:
        return {"status":"NO_DATA","candidate":None}
    try: dist=int(float(distance_m or 0))
    except: dist=0
    if dist>=1400:
        return {
            "status":"RESEARCH_ONLY",
            "candidate":None,
            "reason":"August PDCA: low-rank intrusion replacement is not enabled outside sprint races",
            "production_override_applied":False,
        }
    best=None
    for i,h in enumerate(q[6:10],start=7):
        s=(.5*_f(h.get("score"))+
           40*_f(h.get("recent_form"),.35)+
           25*(1-_f(h.get("uncertainty"),1))+
           5*min(_f(h.get("starts_before"),0),6)/6-
           1*(i-7))
        row={
            "horse_no":str(h.get("n") or ""),
            "horse_name":h.get("name") or "",
            "rank":i,
            "intrusion_score":round(s,3),
        }
        if best is None or row["intrusion_score"]>best["intrusion_score"]:
            best=row
    if best and best["intrusion_score"]>=25:
        return {
            "status":"RESEARCH_ONLY",
            "candidate":best,
            "eligible_for_ticket_swap":True,
            "scope":"CAUTION_ONLY",
            "rule":"BUYは崩さない。CAUTIONかつ1400m未満で強い7〜10位侵入候補が出た時だけ、点数据え置きの1点入替候補にする。",
            "production_override_applied":False,
            "market_isolation":"NO_ODDS_OR_POPULARITY_USED",
        }
    return {
        "status":"RESEARCH_ONLY",
        "candidate":best,
        "eligible_for_ticket_swap":False,
        "scope":"CAUTION_ONLY",
        "production_override_applied":False,
        "market_isolation":"NO_ODDS_OR_POPULARITY_USED",
    }
