#!/usr/bin/env python3
"""Build a NAR model snapshot from verified, normalized pre-race Oddspark history.

This is an adapter to the existing JRA_MULTI_HORIZON_STRICT_CUTOFF_V4
feature calculation, NOT a validated NAR-calibrated production model.
Never scrape implicitly or fill in missing history with synthetic races.
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from build_race_week_pre_race_features import (
    feature_for, people_rates, draw_priors, merge_history, dt, integer
)

FORBIDDEN_FIELDS = {"odds", "popularity", "market_rank", "payout", "return_amount", "result", "results", "race_result", "finish_after_target"}

def reject_forbidden(value, location="source"):
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_FIELDS:
                raise ValueError(f"market/result leakage at {location}.{key}")
            reject_forbidden(child, f"{location}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            reject_forbidden(child, f"{location}[{i}]")

def build(source):
    reject_forbidden(source)
    race=source.get("race") or {}
    cutoff=str(race.get("date") or "")
    if not dt(cutoff) or not race.get("race_id") or not race.get("track") or not race.get("race_no"):
        raise ValueError("race identity/date missing")
    runners=source.get("runners") or []
    if len(runners)<3:raise ValueError("insufficient runners")
    numbers=[str(r.get("horse_no") or "") for r in runners]
    if not all(numbers) or len(numbers)!=len(set(numbers)):
        raise ValueError("missing or duplicate horse numbers")
    if not source.get("source_url") or not source.get("captured_at"):
        raise ValueError("source URL and capture timestamp required")
    if source.get("source_name")!="ODDSPARK":
        raise ValueError("only verified Oddspark input is accepted")
    host=(urlparse(str(source["source_url"])).hostname or "").lower()
    if host not in ("oddspark.com","www.oddspark.com","sp.oddspark.com","api.sp.oddspark.com"):
        raise ValueError("source URL must be an Oddspark domain")
    try:
        captured=datetime.fromisoformat(str(source["captured_at"]))
        scheduled=datetime.fromisoformat(str(race["scheduled_at"]))
    except (ValueError,KeyError,TypeError):
        raise ValueError("timezone-aware capture and scheduled_at are required")
    if captured.tzinfo is None or scheduled.tzinfo is None:
        raise ValueError("timezone-aware timestamps required")
    if captured >= scheduled:
        raise ValueError("post-race capture cannot support sealed prediction")
    all_hist=[]
    for runner in runners:
        if not runner.get("horse_name"):raise ValueError("missing horse name")
        if not runner.get("recent_starts"):raise ValueError("missing history for "+runner["horse_name"])
        for h in runner["recent_starts"]:
            if not h.get("race_date") or str(h["race_date"])>=cutoff:
                raise ValueError("post-cutoff or undated history")
            if integer(h.get("finish_position")) is None:
                raise ValueError("history finish missing")
            all_hist.append({**h,"jockey":h.get("jockey") or "",
                             "trainer":h.get("trainer") or ""})
    rates=people_rates(all_hist,cutoff)
    draw=draw_priors(all_hist)
    field_sizes=defaultdict(int)
    for h in all_hist:
        if h.get("race_id"):field_sizes[h["race_id"]]+=1
    horses=[]
    for r in runners:
        normalized={"race":race,"jockey":r.get("jockey"),"trainer":r.get("trainer"),
                    "frame_no":r.get("frame_no")}
        hist=merge_history([],r["recent_starts"],cutoff)
        f=feature_for(normalized,hist,rates,field_sizes,draw)
        horses.append({
            "n":str(r["horse_no"]),"name":r["horse_name"],
            "score":f["pre_race_score"],
            "score_provenance":"JRA_V4_TRANSFER_PRE_RACE_UNCALIBRATED",
            "score_source":f["pre_race_score_source"]+"_NAR_UNCALIBRATED",
            "starts_before":f["starts_before"],
            "show_rate_prior":f["show_rate_prior"],"recent_form":f["recent_form"],
            "condition_fit":f["condition_fit"],"uncertainty":f["uncertainty"],
            "running_style":f["pre_race_running_style"],
            "carried_weight":r.get("carried_weight"),
            "draw_show_prior":f["draw_show_prior"],
        })
    return {"source_type":"NAR","race_id":race["race_id"],"date":cutoff,
            "track":race["track"],"race_no":race["race_no"],
            "source_url":source["source_url"],"captured_at":source["captured_at"],
            "model_calibration":"UNVALIDATED_NAR_TRANSFER","horses":horses}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    result=build(json.loads(Path(a.input).read_text(encoding="utf-8")))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"NAR_TRANSFER_SNAPSHOT_BUILT","horses":len(result["horses"]),
                      "calibration":result["model_calibration"]},ensure_ascii=False))
if __name__=="__main__":main()
