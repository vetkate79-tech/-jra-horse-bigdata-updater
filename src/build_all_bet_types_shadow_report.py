#!/usr/bin/env python3
"""Read-only all-ticket-type shadow report from an already sealed prediction.

No odds, purchases, ERP writes, or changes to the existing trio selection.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from all_bet_types_shadow import ticket_probabilities

SOURCE = Path("docs/data/live_predictions_sealed.json")
OUTPUT = Path("shadow-artifacts/all_bet_types_shadow.json")
KINDS = ("WIN", "PLACE", "WIDE", "QUINELLA", "EXACTA", "TRIO", "TRIFECTA")


def build(source: dict) -> dict:
    report = {
        "mode": "RESEARCH_ONLY_NO_PRODUCTION_OVERRIDE",
        "source_prediction_hash": source.get("prediction_hash_sha256"),
        "source_generated_at": source.get("generated_at"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "odds_used": False,
        "market_ev_available": False,
        "production_modified": False,
        "races": [],
    }
    for race in source.get("races") or []:
        sim = race.get("simulation_finalizer") or {}
        counts = sim.get("joint_top3_ordered_counts") or {}
        runs = int(sim.get("joint_top3_runs") or 0)
        horses = race.get("ranked_snapshot") or []
        runners = [str(h.get("n") or "") for h in horses]
        row = {
            "date": race.get("date"), "track": race.get("track"),
            "race_no": race.get("race_no"), "race_id": race.get("race_id"),
            "runner_count": len(runners),
            "status": "DATA_PENDING", "reason": None,
        }
        if len(runners) < 4 or not all(x.isdigit() for x in runners) or len(set(runners)) != len(runners):
            row["reason"] = "INVALID_OR_UNSUPPORTED_RUNNER_SET"
        elif runs < 10000 or not counts:
            row["reason"] = "JOINT_SIMULATION_NOT_AVAILABLE"
        else:
            try:
                for key in counts:
                    finish = key.split("-")
                    if len(finish) != 3 or any(n not in runners for n in finish):
                        raise ValueError("OUTCOME_CONTAINS_UNKNOWN_RUNNER")
                place_positions = 2 if len(runners) <= 7 else 3
                probabilities = ticket_probabilities(counts, runs, place_positions)
                if any(not probabilities[k] for k in KINDS):
                    raise ValueError("MISSING_TICKET_DISTRIBUTION")
                row.update({
                    "status": "SHADOW_READY", "reason": None,
                    "simulation_runs": runs,
                    "place_positions": place_positions,
                    "ticket_probabilities": probabilities,
                    "market_status": "NO_QUOTE",
                    "selection_status": "NOT_AUTHORIZED_WITHOUT_MARKET_AND_VALIDATION",
                })
            except (ValueError, TypeError) as exc:
                row["reason"] = str(exc)
        report["races"].append(row)
    report["ready_count"] = sum(r["status"] == "SHADOW_READY" for r in report["races"])
    report["pending_count"] = len(report["races"]) - report["ready_count"]
    return report


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit("SEALED_SOURCE_MISSING: production untouched")
    report = build(json.loads(SOURCE.read_text(encoding="utf-8")))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("mode", "ready_count", "pending_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
