#!/usr/bin/env python3
"""Generic fail-closed NAR research entry point.

Accepts a verified normalized source JSON for any track/race. No fabricated
runners, scores, missing history, odds, or post-start sealed predictions.
This does not perform discovery/scraping; that is a separate adapter stage.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_nar_pre_race_snapshot import build
from run_nar_isolated import run


def execute(source, expected_track=None, expected_race_no=None, expected_date=None):
    race = source.get("race") or {}
    if expected_track is not None and str(race.get("track")) != str(expected_track):
        raise ValueError("requested track differs from verified source")
    if expected_race_no is not None and str(race.get("race_no")) != str(expected_race_no):
        raise ValueError("requested race number differs from verified source")
    if expected_date is not None and str(race.get("date")) != str(expected_date):
        raise ValueError("requested date differs from verified source")
    track = str(race.get("track") or "")
    if any(x in track for x in ("帯広", "ばんえい", "BANEI")):
        raise ValueError("BANEI_REQUIRES_SEPARATE_MODEL")
    snapshot = build(source)
    prediction = run(snapshot)
    if prediction.get("status") != "RESEARCH_NAR_UNCALIBRATED":
        raise ValueError("unexpected research status")
    return {"snapshot": snapshot, "prediction": prediction}


def main():
    p = argparse.ArgumentParser(description="Run verified NAR research snapshot for any flat-racing track")
    p.add_argument("--source", required=True, help="Verified normalized pre-start source JSON")
    p.add_argument("--output", required=True, help="Output JSON with snapshot and prediction")
    p.add_argument("--track", help="Optional exact track identity check")
    p.add_argument("--race-no", help="Optional exact race number identity check")
    p.add_argument("--date", help="Optional YYYY-MM-DD identity check")
    a = p.parse_args()
    source = json.loads(Path(a.source).read_text(encoding="utf-8"))
    result = execute(source, a.track, a.race_no, a.date)
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["prediction"]["status"],
                      "race_id": result["prediction"]["race_id"],
                      "ticket_status": result["prediction"]["ticket_status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
