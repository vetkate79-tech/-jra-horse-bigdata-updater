#!/usr/bin/env python3
"""New-horse-only dataset audit. Research branch; does not change production predictions.

Input CSV: race_id,race_date,horse_id,is_debut,finish_position,feature_asof
Optional: surface,distance_m,track,model_win_prob,model_top2_prob,model_top3_prob
Results are LABELS only; feature_asof must predate the race.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REQUIRED = {"race_id", "race_date", "horse_id", "is_debut", "finish_position", "feature_asof"}
FORBIDDEN_FEATURE_TOKENS = (
    "result_", "final_odds", "final_popularity", "payout", "finish_",
    "post_race", "future_", "race_result", "closing_odds",
)
PROBS = ("model_win_prob", "model_top2_prob", "model_top3_prob")

def date_value(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()

def audit(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or ())
        missing = sorted(REQUIRED - fields)
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(missing))
        # Explicit result labels are allowed; they must never become training features.
        suspicious = sorted(c for c in fields - REQUIRED - set(PROBS)
                            if any(t in c.lower() for t in FORBIDDEN_FEATURE_TOKENS))
        if suspicious:
            raise ValueError("Potential leakage columns (not approved): " + ", ".join(suspicious))
        rows = list(reader)
    issues = []
    races = defaultdict(list)
    seen = set()
    for index, row in enumerate(rows, start=2):
        key = (row["race_id"], row["horse_id"])
        if key in seen:
            issues.append(f"row {index}: duplicate race_id+horse_id")
        seen.add(key)
        try:
            day = date_value(row["race_date"])
            asof = date_value(row["feature_asof"])
            if asof > day:
                issues.append(f"row {index}: feature timestamp after race date")
            finish = int(row["finish_position"])
            if finish < 1:
                issues.append(f"row {index}: invalid finish position")
            for name in PROBS:
                if row.get(name, "") != "":
                    p = float(row[name])
                    if not 0 <= p <= 1:
                        issues.append(f"row {index}: {name} outside [0,1]")
        except (ValueError, TypeError, OverflowError):
            issues.append(f"row {index}: invalid date, finish or probability")
        if str(row["is_debut"]).strip().lower() not in {"1", "true", "yes"}:
            issues.append(f"row {index}: non-debut horse in new-horse dataset")
        races[row["race_id"]].append(row)
    for race_id, entries in races.items():
        dates = {e["race_date"] for e in entries}
        if len(dates) != 1:
            issues.append(f"race {race_id}: inconsistent race dates")
        if len({e["finish_position"] for e in entries}) != len(entries):
            # Dead heats are possible; report for manual review rather than fail.
            issues.append(f"race {race_id}: tied/duplicate finish positions; manual review")
    days = sorted({r["race_date"] for r in rows})
    report = {
        "scope": "JRA_NEW_HORSE_ONLY",
        "source": str(path),
        "rows": len(rows),
        "unique_races": len(races),
        "unique_horses": len({r["horse_id"] for r in rows}),
        "date_min": days[0] if days else None,
        "date_max": days[-1] if days else None,
        "issues": issues[:200],
        "issue_count": len(issues),
        "ready_for_training": bool(rows) and not issues,
        "note": "No training or model promotion occurs in this audit. Chronological OOS and calibration are required separately.",
    }
    if not rows:
        report["issues"].append("No data rows")
        report["issue_count"] += 1
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.csv_path)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if result["ready_for_training"] else 2)

if __name__ == "__main__":
    main()
