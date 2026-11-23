#!/usr/bin/env python3
"""Discover immutable archived prediction dates for resumable historical audit.

This tool produces candidates only, never certifies formal unseen races.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

PATTERN = re.compile(r"^prediction-archive-(\d{4}-\d{2}-\d{2})\.json$")


def discover(root: Path):
    seen = {}
    for path in sorted(root.glob("prediction-archive-*.json")):
        match = PATTERN.fullmatch(path.name)
        if not match:
            continue
        day = match.group(1)
        raw = path.read_bytes()
        item = {
            "date": day,
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "status": "CANDIDATE_ONLY",
            "reasons": [],
            "race_count": 0,
            "pending_count": 0,
        }
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("archive is not object")
            if payload.get("date") != day:
                item["reasons"].append("ARCHIVE_DATE_MISMATCH")
            if payload.get("mode") != "IMMUTABLE_PREDICTION_ARCHIVE":
                item["reasons"].append("UNEXPECTED_ARCHIVE_MODE")
            races = payload.get("races") or []
            pending = payload.get("pending") or []
            if not isinstance(races, list) or not isinstance(pending, list):
                raise ValueError("races or pending not array")
            item["race_count"] = len(races)
            item["pending_count"] = len(pending)
            for row in races + pending:
                if not isinstance(row, dict) or row.get("date") != day:
                    item["reasons"].append("CROSS_DATE_RACE_ENTRY")
                    break
            if not races and not pending:
                item["reasons"].append("EMPTY_ARCHIVE")
            item["model_version"] = payload.get("model_version")
            item["prediction_hash_sha256"] = payload.get("prediction_hash_sha256")
            item["sealed_generated_at"] = payload.get("sealed_generated_at")
        except (ValueError, TypeError, UnicodeError) as error:
            item["reasons"].append("INVALID_ARCHIVE_JSON")
            item["detail"] = str(error)
        if day in seen:
            item["reasons"].append("DUPLICATE_ARCHIVE_DATE")
        seen[day] = item
        yield item


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-dir", type=Path, default=Path("docs/data"))
    parser.add_argument("--manifest-out", required=True, type=Path)
    args = parser.parse_args()
    rows = list(discover(args.archive_dir))
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows), encoding="utf-8")
    print(json.dumps({"archives": len(rows), "candidate_races": sum(x["race_count"] for x in rows),
                      "archive_errors": sum(bool(x["reasons"]) for x in rows),
                      "formal_certified": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
