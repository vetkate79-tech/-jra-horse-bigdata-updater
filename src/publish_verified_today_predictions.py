#!/usr/bin/env python3
"""Publish compact, verifiable, pre-race-only predictions for every current-JST race."""
import json
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
        if key not in expected or (expected[key] and set(nums)!=expected[key]):
            raise RuntimeError(f"weekly runner mismatch: {key}")
        sim=race.get("simulation_finalizer") or {}
        if int(sim.get("runs") or 0)<10000 or sim.get("market_isolation")!="NO_ODDS_OR_POPULARITY_OR_RESULTS_USED":
            raise RuntimeError(f"simulation or market firewall failed: {key}")
        a=race.get("analysis") or {}
        if "新馬" in str(race.get("race_name") or "") or "メイクデビュー" in str(race.get("race_name") or ""):
            if not str(a.get("model_version") or "").startswith("NEW_HORSE_DEDICATED_V2"):
                raise RuntimeError(f"wrong debut model: {key}")
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
    payload={"date":today,"status":"VERIFIED","race_count":len(published),
             "source_prediction_hash":seal.get("prediction_hash_sha256"),
             "races":[published[k] for k in sorted(published)]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"TODAY_ALL_RACES_VERIFIED date={today} count={len(published)} path={OUT}")

if __name__=="__main__":
    main()
