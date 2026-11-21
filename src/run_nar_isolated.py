#!/usr/bin/env python3
"""Isolated NAR prediction runner. Never modifies JRA seals or datasets.

Input is a pre-race JSON race snapshot with externally verified ability scores.
A missing score is an error, never replaced by SP index or fabricated values.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from axis_survival_shadow import select_survival_axis
from monte_carlo_finalizer import finalize_ranking


def run(snapshot):
    if snapshot.get("source_type") != "NAR":
        raise ValueError("source_type must be NAR")
    required = ("race_id", "date", "track", "race_no", "horses")
    if any(not snapshot.get(k) for k in required):
        raise ValueError("race metadata incomplete")
    horses = snapshot["horses"]
    if len(horses) < 3:
        raise ValueError("at least 3 runners required")
    numbers = []
    for horse in horses:
        for key in ("n", "name", "score", "score_provenance", "running_style",
                    "show_rate_prior", "recent_form", "condition_fit",
                    "uncertainty", "starts_before"):
            if horse.get(key) is None or horse.get(key) == "":
                raise ValueError(f"runner {horse.get('n', '?')}: missing {key}")
        if horse["score_provenance"] != "ORAL_VERIFIED_PRE_RACE":
            raise ValueError("unverified ability score; cannot claim formal model output")
        for key in ("score", "show_rate_prior", "recent_form", "condition_fit", "uncertainty", "starts_before"):
            if not math.isfinite(float(horse[key])):
                raise ValueError(f"nonfinite {key}")
        numbers.append(str(horse["n"]))
    if len(numbers) != len(set(numbers)):
        raise ValueError("duplicate horse numbers")
    if any(k in snapshot for k in ("results", "payouts")):
        raise ValueError("post-race results are forbidden")
    ranked, simulation = finalize_ranking(snapshot, horses)
    axis = select_survival_axis(ranked)
    return {
        "status": "RESEARCH_NAR_UNCALIBRATED" if snapshot.get("model_calibration") == "UNVALIDATED_NAR_TRANSFER" else "COMPUTED_NAR_ISOLATED",
        "model_calibration": snapshot.get("model_calibration", "UNVERIFIED"),
        "source_type": "NAR",
        "race_id": snapshot["race_id"],
        "date": snapshot["date"],
        "track": snapshot["track"],
        "race_no": snapshot["race_no"],
        "market_isolation": "NO_ODDS_OR_POPULARITY_OR_RESULTS_USED",
        "ability_score_origin": "JRA_MULTI_HORIZON_TRANSFER_UNCALIBRATED" if snapshot.get("model_calibration") == "UNVALIDATED_NAR_TRANSFER" else "EXTERNAL_VERIFIED_PRE_RACE",
        "ability_ranked": sorted(
            [{"horse_no": str(h["n"]), "name": h["name"], "score": round(float(h["score"]), 3)}
             for h in horses], key=lambda h: (-h["score"], int(h["horse_no"]))),
        "axis_shadow": axis,
        "simulation": simulation,
        "ticket_status": "NOT_GENERATED_UNTIL_VALIDATED_NAR_TICKET_ADAPTER",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = run(snapshot)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "race_id": result["race_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
