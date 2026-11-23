#!/usr/bin/env python3
"""Deterministic, no-odds historical replay over strict formal JSONL.

Never creates new formal records. Only consumes an independently audited ledger.
All ticket combinations and stakes must have been frozen before race start.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def combo(value):
    if isinstance(value, str):
        parts = value.replace("－", "-").split("-")
    else:
        parts = value
    numbers = [int(v) for v in parts]
    if len(numbers) != 3 or len(set(numbers)) != 3:
        raise ValueError("invalid trio")
    return "-".join(map(str, sorted(numbers)))


def score(record):
    tickets = {combo(t) for t in record["trio_tickets"]}
    actual = combo(record["official_top3"])
    stake = record["stake_yen"]
    if record["decision"] != "BUY" and stake:
        raise ValueError("non-BUY with positive stake")
    if stake < 0 or (stake % 100) or stake != 100 * len(tickets):
        raise ValueError("ticket budget mismatch")
    payout_per_100 = record["official_trio_payout_per_100"]
    if not isinstance(payout_per_100, int) or payout_per_100 < 0:
        raise ValueError("invalid official payout")
    hit = actual in tickets and stake > 0
    ret = payout_per_100 if hit else 0
    if ret != record["return_yen"]:
        raise ValueError("return mismatch with official payout and frozen tickets")
    axis = record.get("axis_horse_no")
    return {**record, "hit": hit, "axis_top3": int(axis) in {int(x) for x in actual.split("-")} if axis else None,
            "computed_return_yen": ret}


def summarize(rows):
    stake = sum(r["stake_yen"] for r in rows)
    ret = sum(r["computed_return_yen"] for r in rows)
    largest = max((r["computed_return_yen"] for r in rows), default=0)
    bought = [r for r in rows if r["stake_yen"]]
    running = peak = max_dd = losses = max_losses = 0
    for r in rows:
        running += r["computed_return_yen"] - r["stake_yen"]
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
        if r["stake_yen"]:
            losses = 0 if r["hit"] else losses + 1
            max_losses = max(max_losses, losses)
    axis = [r["axis_top3"] for r in rows if r["axis_top3"] is not None]
    return {"races": len(rows), "buy": len(bought), "stake_yen": stake,
            "return_yen": ret, "roi_pct": round(100 * ret / stake, 2) if stake else None,
            "roi_ex_largest_pct": round(100 * (ret - largest) / stake, 2) if stake else None,
            "largest_return_yen": largest,
            "hit_rate_pct": round(100 * sum(r["hit"] for r in bought) / len(bought), 2) if bought else None,
            "axis_top3_pct": round(100 * sum(axis) / len(axis), 2) if axis else None,
            "max_drawdown_yen": max_dd, "max_losing_streak": max_losses,
            "high_payout_hits_10000_yen": sum(r["computed_return_yen"] >= 10000 for r in bought)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--formal", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    rows = []
    seen = set()
    for line in args.formal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        record = item["record"]
        key = item["canonical_key"]
        if key in seen:
            raise ValueError("duplicate formal race: " + key)
        seen.add(key)
        rows.append(score(record))
    rows.sort(key=lambda r: (r["date"], r["scheduled_start_time"], r["track"], r["race_no"]))
    by_model = defaultdict(list)
    for row in rows:
        by_model[row["model_version"]].append(row)
    result = {"overall": summarize(rows), "models": {}}
    for model, records in sorted(by_model.items()):
        result["models"][model] = {
            "overall": summarize(records),
            "fixed_36r": [summarize(records[i:i+36]) for i in range(0, len(records)-35, 36)],
            "fixed_100r": [summarize(records[i:i+100]) for i in range(0, len(records)-99, 100)],
        }
    for size in (300, 500, 1000):
        if len(rows) >= size:
            result[f"cumulative_{size}"] = summarize(rows[:size])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["overall"], ensure_ascii=False))


if __name__ == "__main__":
    main()
