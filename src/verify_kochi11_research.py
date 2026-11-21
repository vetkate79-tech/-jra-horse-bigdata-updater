#!/usr/bin/env python3
"""Fail-closed checks for retrospective Kochi research artifact.

A successful research run must never be mistaken for a sealed prediction.
"""
import json,sys,math
from pathlib import Path

def check(a):
    if a.get("formal_prediction_status")!="BLOCKED_NO_VERIFIED_PRE_START_SEAL_AND_HORSE_NUMBER_MAPPING":
        raise ValueError("formal status not blocked")
    if a.get("source_provenance")!="RAKUTEN_KEIBA_POST_START_FETCH_RETROSPECTIVE_ONLY":
        raise ValueError("post-start provenance missing")
    if a.get("model_calibration")!="UNVALIDATED_NAR_TRANSFER":
        raise ValueError("unvalidated calibration not declared")
    if a.get("research_ticket_status")!="BLOCKED_UNVERIFIED_HORSE_NUMBERS_NO_BETTABLE_TICKETS":
        raise ValueError("ticket gate failed")
    if a.get("research_trifecta_box_selections") or a.get("research_row_index_combinations"):
        raise ValueError("unverified tickets leaked")
    counts=a["research_input_coverage"]["history_counts"]
    if len(counts)!=11 or any(not isinstance(v,int) or v<1 for v in counts.values()):
        raise ValueError("history incomplete")
    scores=a["ability_ranked"]
    probs=a["simulation"]["horse_probabilities"]
    if len(scores)!=11 or len(probs)!=11:raise ValueError("11-runner output incomplete")
    if a["simulation"]["runs"]!=100000:raise ValueError("not 100000 simulations")
    if set(x["name"] for x in scores)!=set(x["horse_name"] for x in probs):
        raise ValueError("score/probability horse identities mismatch")
    for x in scores:
        if x.get("horse_no") is not None or not math.isfinite(float(x["score"])):
            raise ValueError("unverified number or invalid score")
    for x in probs:
        if x.get("horse_no") is not None:raise ValueError("unverified simulation horse number")
        for k in ("win_rate","place_rate","top3_rate"):
            v=float(x[k])
            if not 0<=v<=1:raise ValueError("invalid probability")
        if not x["win_rate"]<=x["place_rate"]<=x["top3_rate"]:
            raise ValueError("probability monotonicity violated")
    if abs(sum(float(x["top3_rate"]) for x in probs)-3)>0.005:
        raise ValueError("top3 probabilities must sum to three")
    if abs(sum(float(x["win_rate"]) for x in probs)-1)>0.005:
        raise ValueError("win probabilities must sum to one")
    def check_numbers(obj):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k=="horse_no" and v is not None:raise ValueError("unverified number leaked")
                check_numbers(v)
        elif isinstance(obj,list):
            for v in obj:check_numbers(v)
    check_numbers(a["axis_shadow"])
    return {"status":"PASS_RESEARCH_ONLY_FORMAL_BLOCKED","runners":11,"simulations":100000,
            "top3_probability_sum":round(sum(float(x["top3_rate"]) for x in probs),6),
            "formal_prediction":"NOT_AVAILABLE","bettable_tickets":"BLOCKED"}

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: verify_kochi11_research.py output.json")
    print(json.dumps(check(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))),ensure_ascii=False))
