#!/usr/bin/env python3
"""Inventory existing daily replays, never promote them to formal evidence.

Replay JSON includes predictions/results but is post-race material; Git pre-start
seal ancestry must be checked independently before any formal certification.
"""
import argparse
import json
from pathlib import Path


def inventory(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("races") or []
    date = data.get("date")
    if not isinstance(rows, list):
        raise ValueError("races must be a list")
    seen = set()
    issues = []
    sealed = result = 0
    for index, row in enumerate(rows):
        key = (row.get("date"), str(row.get("track", "")).replace("競馬場", ""), row.get("race_no"))
        if key in seen:
            issues.append({"index": index, "reason": "DUPLICATE_RACE_KEY", "key": key})
        seen.add(key)
        if key[0] != date:
            issues.append({"index": index, "reason": "CROSS_DATE"})
        if (row.get("prediction") or {}).get("sealed") is True:
            sealed += 1
        if (row.get("result") or {}).get("top3"):
            result += 1
    summary = data.get("summary") or {}
    if summary.get("races") != len(rows):
        issues.append({"reason": "SUMMARY_COUNT_MISMATCH"})
    return {"date": date, "source": str(path), "rows": len(rows),
            "claimed_sealed": sealed, "with_result": result,
            "issues": issues, "formal_certified": 0,
            "status": "DIAGNOSTIC_ONLY_UNTIL_INDEPENDENT_PRESTART_GIT_SEAL_VERIFIED"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path, default=Path("docs/data"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reports = []
    for path in sorted(args.replay_dir.glob("replay-????-??-??.json")):
        try:
            reports.append(inventory(path))
        except (ValueError, TypeError, UnicodeError) as error:
            reports.append({"source": str(path), "status": "INVALID_REPLAY", "error": str(error), "formal_certified": 0})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"replay_files": len(reports), "diagnostic_races": sum(r.get("rows", 0) for r in reports),
                      "formal_certified": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
