#!/usr/bin/env python3
"""Fail-closed completeness gate for Kochi 2026-11-21 race 11.

This is a retrospective audit, NOT a sealed pre-race prediction.
Do not invent missing starts, score scratches, or use market/result fields.
"""
import json,sys,re
from pathlib import Path

FORBIDDEN={"odds","popularity","market_rank","payout","return_amount","result","results","race_result","finish_after_target"}
# Normalize common naming variants before checking; this is defense in depth,
# not proof that every unknown market-derived feature is excluded.
def normalized_key(key):
    key=re.sub(r"(?<=[a-z0-9])(?=[A-Z])","_",str(key))
    return re.sub(r"[^a-z0-9]","",key.lower())
FORBIDDEN_NORMALIZED={normalized_key(k) for k in FORBIDDEN}
def guard(x,where="root"):
    if isinstance(x,dict):
        for k,v in x.items():
            if normalized_key(k) in FORBIDDEN_NORMALIZED:raise ValueError("leakage: "+where+"."+k)
            guard(v,where+"."+k)
    elif isinstance(x,list):
        for i,v in enumerate(x):guard(v,f"{where}[{i}]")
def audit(data):
    guard(data)
    horses=data.get("horses",[])
    if len(horses)!=11:raise ValueError(f"Kochi 11R expected 11 published entries, got {len(horses)}")
    names=[h["horse_name"] for h in horses]
    if len(set(names))!=11:raise ValueError("duplicate horse name")
    missing=[];valid=[]
    for h in horses:
        history=h.get("recent_starts",[])
        if not history:missing.append(h["horse_name"])
        else:
            for start in history:
                if start["race_date"]>="2026-11-21":raise ValueError("target-date leakage")
                if not isinstance(start.get("finish_position"),int) or start["finish_position"]<1:raise ValueError("invalid past finish")
            valid.append(h["horse_name"])
    return {"race_id":"202611213129100511","status":"BLOCKED_INCOMPLETE_HISTORY" if missing else "HISTORY_COMPLETE_RESEARCH_ONLY","entries":len(horses),"history_available":len(valid),"missing_history":missing,"market_and_result_fields":"REJECTED","pre_start_seal":"NOT_VERIFIED","formal_scores_generated":False,"formal_top3_probabilities_generated":False,"formal_tickets_generated":False}
if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("usage: audit_kochi11_completeness.py parsed.json audit.json")
    output=audit(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    Path(sys.argv[2]).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False))
