#!/usr/bin/env python3
"""Publish compact, verifiable, pre-race-only predictions for every current-JST race."""
import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path("docs/data")
SRC=ROOT/"live_predictions_sealed.json"
WEEKLY=ROOT/"horses/weekly_runner_details.json"
OUT=ROOT/"live_predictions_today_verified.json"

def main():
    today=datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    seal=json.loads(SRC.read_text(encoding="utf-8"))
    weekly=json.loads(WEEKLY.read_text(encoding="utf-8"))
    expected={}
    for row in weekly.get("runners") or []:
        race=row.get("race") or {}
        if str(race.get("date") or "")!=today:continue
        key=(str(race.get("track") or ""),int(race.get("race_no") or 0))
        expected.setdefault(key,set())
        no=str(row.get("horse_no") or "").strip()
        if no:expected[key].add(no)
    published={}
    for race in seal.get("races") or []:
        if race.get("date")!=today:continue
        key=(str(race.get("track") or ""),int(race.get("race_no") or 0))
        if key in published:raise RuntimeError(f"duplicate sealed race: {key}")
        ranked=race.get("ranked_snapshot") or []
        if not ranked:raise RuntimeError(f"empty ranking: {key}")
        nums=[str(h.get("n") or "").strip() for h in ranked]
        if any(not n for n in nums) or len(set(nums))!=len(nums):
            raise RuntimeError(f"invalid runner numbers: {key}")
        if key not in expected or not expected[key] or set(nums)!=expected[key]:
            raise RuntimeError(f"weekly runner mismatch: {key}")
        sim=race.get("simulation_finalizer") or {}
        if int(sim.get("runs") or 0)<10000 or sim.get("market_isolation")!="NO_ODDS_OR_POPULARITY_OR_RESULTS_USED":
            raise RuntimeError(f"simulation or market firewall failed: {key}")
        a=race.get("analysis") or {}
        if "新馬" in str(race.get("race_name") or "") or "メイクデビュー" in str(race.get("race_name") or ""):
            if not str(a.get("model_version") or "").startswith("NEW_HORSE_DEDICATED_V2"):
                raise RuntimeError(f"wrong debut model: {key}")
        # Mandatory JRA answer contract: fail closed rather than publish incomplete projections.
        required_sim=("final_rank","win_rate","place_rate","top3_rate","scenario_stability","scenario_top3")
        ranks=[]
        for h in ranked:
            hs=h.get("simulation") or {}
            if h.get("score") is None or not math.isfinite(float(h["score"])):
                raise RuntimeError(f"missing/nonfinite ability score: {key} horse={h.get('n')}")
            if any(hs.get(k) is None for k in required_sim):
                raise RuntimeError(f"incomplete horse simulation: {key} horse={h.get('n')}")
            if set(hs["scenario_top3"])!={"SLOW_FRONT","AVERAGE","FAST_BALANCED","FAST_CLOSER","EXTREME_COLLAPSE"}:
                raise RuntimeError(f"incomplete scenarios: {key} horse={h.get('n')}")
            if any(not math.isfinite(float(hs[k])) or not 0<=float(hs[k])<=1 for k in ("win_rate","place_rate","top3_rate","scenario_stability")):
                raise RuntimeError(f"invalid simulation probability: {key} horse={h.get('n')}")
            if any(not math.isfinite(float(v)) or not 0<=float(v)<=1 for v in hs["scenario_top3"].values()):
                raise RuntimeError(f"invalid simulation probability: {key} horse={h.get('n')}")
            if not (hs["win_rate"]<=hs["place_rate"]<=hs["top3_rate"]):
                raise RuntimeError(f"probability order failed: {key} horse={h.get('n')}")
            ranks.append(int(hs["final_rank"]))
        if ranks!=list(range(1,len(ranked)+1)):
            raise RuntimeError(f"invalid final ranks: {key}")
        if any(a.get(k) is None for k in ("axis","axis_durability","pre_market_decision","classification","formation_columns","trio_tickets")):
            raise RuntimeError(f"incomplete race analysis: {key}")
        if a["pre_market_decision"] not in ("BUY","CAUTION","PASS"):
            raise RuntimeError(f"invalid purchase decision: {key}")
        if str((a["axis"] or {}).get("horse_no") or "") not in set(nums):
            raise RuntimeError(f"axis not in runners: {key}")
        if len(a["trio_tickets"])!=len(set(a["trio_tickets"])):
            raise RuntimeError(f"duplicate trio tickets: {key}")
        for ticket in a["trio_tickets"]:
            parts=str(ticket).split("-")
            if len(parts)!=3 or len(set(parts))!=3 or not set(parts).issubset(set(nums)):
                raise RuntimeError(f"invalid trio ticket: {key} {ticket}")
        published[key]={
            "date":today,"track":key[0],"race_no":key[1],
            "race_name":race.get("race_name"),"model_version":a.get("model_version"),
            "horses":[{"horse_no":h.get("n"),"horse_name":h.get("name"),"score":h.get("score"),"final_rank":(h.get("simulation") or {}).get("final_rank"),"win_rate":(h.get("simulation") or {}).get("win_rate"),"place_rate":(h.get("simulation") or {}).get("place_rate"),"top3_rate":(h.get("simulation") or {}).get("top3_rate"),"scenario_stability":(h.get("simulation") or {}).get("scenario_stability"),"scenario_top3":(h.get("simulation") or {}).get("scenario_top3")} for h in ranked],
            "axis":a.get("axis"),"trio_tickets":a.get("trio_tickets") or [],
            "simulation_runs":sim.get("runs"),"axis_durability":a.get("axis_durability"),"pre_market_decision":a.get("pre_market_decision"),"classification":a.get("classification"),"formation_columns":a.get("formation_columns"),"failure_scenarios":a.get("failure_scenarios"),"scenario_weights":sim.get("scenario_weights")
        }
    missing=set(expected)-set(published)
    if missing:raise RuntimeError(f"unpublished today races: {sorted(missing)}")
    if not published:raise RuntimeError(f"no races sealed for today {today}")
    payload={"schema_version":2,"required_probability_fields_verified":True,"date":today,"status":"VERIFIED","race_count":len(published),
             "source_prediction_hash":seal.get("prediction_hash_sha256"),
             "source_generated_at":seal.get("generated_at"),
             "races":[published[k] for k in sorted(published)]}
    # Publish only a complete, self-describing snapshot; never expose a partial write.
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=OUT.parent,prefix=".live_predictions_verified_",suffix=".tmp",delete=False) as temp:
        temp.write(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
        temp.flush()
        os.fsync(temp.fileno())
        temporary_path=Path(temp.name)
    os.replace(temporary_path,OUT)
    print(f"TODAY_ALL_RACES_VERIFIED date={today} count={len(published)} path={OUT}")

if __name__=="__main__":
    main()
