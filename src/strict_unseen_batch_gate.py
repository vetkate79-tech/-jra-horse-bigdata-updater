#!/usr/bin/env python3
"""Fail-closed, idempotent batch classification of independently sourced race evidence.

Input JSONL: one record per candidate; no network or result scraping. This is an
evidence gate, NOT an assertion that supplied evidence is independently authentic.
"""
import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def timestamp(value):
    if not isinstance(value, str) or not value:
        raise ValueError("missing timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp missing timezone")
    return parsed


def canonical(record):
    date = record["date"]
    track = str(record["track"]).replace("競馬場", "").strip()
    number = int(record["race_no"])
    if not track or not 1 <= number <= 12:
        raise ValueError("invalid track/race number")
    return f"{date}|{track}|{number:02d}"


def classify(record):
    reasons = []
    try:
        key = canonical(record)
    except (KeyError, ValueError, TypeError):
        return None, ["INVALID_RACE_KEY"]
    for field in ("race_id", "seal_commit_sha", "prediction_sha256",
                  "model_version", "official_result_source", "official_payout_source"):
        if not record.get(field):
            reasons.append("MISSING_" + field.upper())
    try:
        sealed = timestamp(record["seal_commit_time"])
        generated = timestamp(record["prediction_generated_time"])
        started = timestamp(record["scheduled_start_time"])
        if sealed >= started or generated >= started:
            reasons.append("POST_START_SEAL")
        if generated > sealed:
            reasons.append("GENERATED_AFTER_COMMIT")
        for value in record.get("feature_source_times", []):
            if timestamp(value) >= started:
                reasons.append("FEATURE_TIME_LEAK")
                break
    except (KeyError, ValueError, TypeError):
        reasons.append("UNVERIFIED_TIME_LINEAGE")
    if record.get("entry_count") is None or record.get("sealed_entry_count") != record.get("entry_count"):
        reasons.append("INCOMPLETE_FIELD")
    # Self-reported flags cannot independently prove that an archive predates a race.
    # A candidate must be externally certified before joining the formal ledger.
    if record.get("independent_seal_evidence") is not True:
        reasons.append("NO_INDEPENDENT_SEAL_EVIDENCE")
    if record.get("upstream_lineage_verified") is not True:
        reasons.append("UNVERIFIED_UPSTREAM_LINEAGE")
    if record.get("official_result_verified") is not True or record.get("official_payout_verified") is not True:
        reasons.append("UNVERIFIED_OFFICIAL_RESULT")
    tickets = record.get("trio_tickets")
    if not isinstance(tickets, list) or not all(isinstance(t, str) for t in tickets):
        reasons.append("INVALID_TICKETS")
    if record.get("decision") not in ("BUY", "CAUTION", "PASS"):
        reasons.append("INVALID_DECISION")
    if not isinstance(record.get("stake_yen"), int) or record["stake_yen"] < 0:
        reasons.append("INVALID_STAKE")
    if not isinstance(record.get("return_yen"), int) or record["return_yen"] < 0:
        reasons.append("INVALID_RETURN")
    return key, sorted(set(reasons))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--formal-out", required=True, type=Path)
    parser.add_argument("--diagnostic-out", required=True, type=Path)
    parser.add_argument("--summary-out", required=True, type=Path)
    args = parser.parse_args()
    seen_keys, seen_ids = set(), set()
    formal, diagnostic = [], []
    with args.input.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("not a JSON object")
                key, reasons = classify(record)
                race_id = str(record.get("race_id") or "")
                if (key and key in seen_keys) or (race_id and race_id in seen_ids):
                    reasons.append("DUPLICATE_RACE")
                if key:
                    seen_keys.add(key)
                if race_id:
                    seen_ids.add(race_id)
                item = {"canonical_key": key, "record": record}
                if reasons:
                    diagnostic.append({**item, "reasons": sorted(set(reasons))})
                else:
                    formal.append(item)
            except (ValueError, TypeError) as error:
                diagnostic.append({"line_number": line_number, "reasons": ["INVALID_JSON"], "detail": str(error)})
    for path, items in ((args.formal_out, formal), (args.diagnostic_out, diagnostic)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in items), encoding="utf-8")
    stakes = sum(x["record"]["stake_yen"] for x in formal)
    returns = sum(x["record"]["return_yen"] for x in formal)
    reasons = Counter(reason for item in diagnostic for reason in item["reasons"])
    summary = {
        "formal_count": len(formal), "diagnostic_count": len(diagnostic),
        "stake_yen": stakes, "return_yen": returns,
        "roi_pct": round(returns * 100 / stakes, 2) if stakes else None,
        "reason_counts": dict(sorted(reasons.items())),
        "note": "Eligibility is conditional on independently verified provenance; input boolean flags alone are not evidence."
    }
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
