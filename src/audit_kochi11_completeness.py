#!/usr/bin/env python3
"""Fail-closed completeness gate for Kochi 2026-11-21 race 11.

This is a retrospective audit, NOT a sealed pre-race prediction.
Do not invent missing starts, score scratches, or use market/result fields.
"""
import json,sys,re
from datetime import date
from pathlib import Path

FORBIDDEN={"odds","popularity","market_rank","payout","return_amount","result","results","race_result","finish_after_target"}
# Normalize common naming variants before checking; this is defense in depth,
# not proof that every unknown market-derived feature is excluded.
def normalized_key(key):
    key=re.sub(r"(?<=[a-z0-9])(?=[A-Z])","_",str(key))
    return re.sub(r"[^a-z0-9]","",key.lower())
FORBIDDEN_NORMALIZED={normalized_key(k) for k in FORBIDDEN}
# Reject common suffix/prefix variants too (e.g. odds_value, popularityRank).
# This is a denylist only: formal release still requires a schema allowlist.
MARKET_PREFIXES=("odds","popularity","marketrank","payout","returnamount","raceresult","finishaftertarget")
def forbidden_key(key):
    normalized=normalized_key(key)
    return normalized in FORBIDDEN_NORMALIZED or normalized.startswith(MARKET_PREFIXES)
def guard(x,where="root"):
    if isinstance(x,dict):
        for k,v in x.items():
            if forbidden_key(k):raise ValueError("leakage: "+where+"."+str(k))
            guard(v,where+"."+str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x):guard(v,f"{where}[{i}]")
# Strict parser-output schema: reject unknown fields before research features are built.
# This does not establish a pre-start seal or validate source authenticity.
ALLOWED_ROOT={"status","horse_count","horses"}
ALLOWED_HORSE={"horse_name","horse_id","recent_starts"}
ALLOWED_START={"race_date","finish_position","surface","distance_m","course","corner_positions","last3f"}
def check_allowed(obj,allowed,where):
    if not isinstance(obj,dict):raise ValueError("invalid schema: "+where)
    extra=set(obj)-allowed
    if extra:raise ValueError("unapproved field: "+where+"."+",".join(sorted(extra)))
def audit(data):
    guard(data)
    check_allowed(data,ALLOWED_ROOT,"root")
    for i,h in enumerate(data.get("horses",[])):
        check_allowed(h,ALLOWED_HORSE,f"horses[{i}]")
        if not isinstance(h.get("recent_starts",[]),list):raise ValueError("invalid history list")
        for j,start in enumerate(h["recent_starts"]):
            check_allowed(start,ALLOWED_START,f"horses[{i}].recent_starts[{j}]")
    horses=data.get("horses",[])
    if len(horses)!=11:raise ValueError(f"Kochi 11R expected 11 published entries, got {len(horses)}")
    names=[h["horse_name"] for h in horses]
    if len(set(names))!=11:raise ValueError("duplicate horse name")
    missing=[];valid=[]
    for h in horses:
        history=h.get("recent_starts",[])
        if not history:missing.append(h["horse_name"])
        else:
            seen_starts=set()
            for start in history:
                raw_date=start.get("race_date")
                if not isinstance(raw_date,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",raw_date):
                    raise ValueError("invalid historical race_date format")
                try: parsed_date=date.fromisoformat(raw_date)
                except ValueError as exc: raise ValueError("invalid historical race_date") from exc
                if parsed_date>=date(2026,11,21):raise ValueError("target-date leakage")
                # A duplicated date alone is not a reliable unique race ID; flag it
                # rather than silently double-weighting the same horse history.
                if raw_date in seen_starts:raise ValueError("duplicate historical race date for "+h["horse_name"])
                seen_starts.add(raw_date)
                if not isinstance(start.get("finish_position"),int) or start["finish_position"]<1:raise ValueError("invalid past finish")
            valid.append(h["horse_name"])
    return {"race_id":"202611213129100511","status":"BLOCKED_INCOMPLETE_HISTORY" if missing else "HISTORY_COMPLETE_RESEARCH_ONLY","entries":len(horses),"history_available":len(valid),"missing_history":missing,"market_and_result_fields":"REJECTED","pre_start_seal":"NOT_VERIFIED","formal_scores_generated":False,"formal_top3_probabilities_generated":False,"formal_tickets_generated":False}
if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("usage: audit_kochi11_completeness.py parsed.json audit.json")
    output=audit(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    Path(sys.argv[2]).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False))
