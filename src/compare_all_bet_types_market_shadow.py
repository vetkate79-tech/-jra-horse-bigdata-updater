#!/usr/bin/env python3
"""Nonblocking, read-only market comparison AFTER sealed probability calculation.

Only WIN odds currently exist in the verified market feed. Other markets remain
NO_QUOTE until their own timestamped official quotes are available.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path("shadow-artifacts/all_bet_types_shadow.json")
MARKET = Path("docs/data/current_market_odds.json")
OUT = Path("shadow-artifacts/all_bet_types_market_comparison.json")
TYPES = ("WIN", "PLACE", "WIDE", "QUINELLA", "EXACTA", "TRIO", "TRIFECTA")


def parse_time(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None


def compare(report, market, now=None):
    now = now or datetime.now(timezone.utc)
    seal = parse_time(report.get("source_generated_at"))
    quote_time = parse_time(market.get("captured_at"))
    # Do not compare quotes older than the seal or older than 10 minutes.
    valid_time = bool(seal and quote_time and seal <= quote_time <= now and
                      (now - quote_time).total_seconds() <= 600)
    by_race = {(r.get("date"), r.get("track"), int(r.get("race_no") or 0)): r
               for r in market.get("races") or []}
    result = {
        "mode": "RESEARCH_ONLY_MARKET_COMPARISON",
        "source_prediction_hash": report.get("source_prediction_hash"),
        "market_captured_at": market.get("captured_at"),
        "quote_time_valid": valid_time,
        "production_modified": False,
        "selection_status": "NO_PRODUCTION_OVERRIDE",
        "races": [],
    }
    for race in report.get("races") or []:
        key = (race.get("date"), race.get("track"), int(race.get("race_no") or 0))
        quote_race = by_race.get(key) or {}
        row = {"date": key[0], "track": key[1], "race_no": key[2],
               "status": "NO_QUOTE", "ticket_types": {t: {"status": "NO_QUOTE", "tickets": []} for t in TYPES}}
        if race.get("status") != "SHADOW_READY":
            row["reason"] = "PROBABILITY_NOT_READY"
        elif market.get("source") != "JRA_OFFICIAL" or market.get("odds_type") != "WIN":
            row["reason"] = "UNVERIFIED_MARKET_FEED"
        elif not valid_time:
            row["reason"] = "QUOTE_STALE_OR_PRE_SEAL"
        elif not quote_race:
            row["reason"] = "RACE_QUOTE_MISSING"
        elif not quote_race.get("source_url"):
            row["reason"] = "QUOTE_SOURCE_MISSING"
        else:
            p = race["ticket_probabilities"]["WIN"]
            quoted = []
            for h in quote_race.get("win_odds") or []:
                horse = str(h.get("horse_no") or "")
                if horse not in p:
                    continue
                try:
                    odds = float(h.get("win_odds"))
                    if odds < 1:
                        continue
                except (TypeError, ValueError):
                    continue
                probability = float(p[horse])
                quoted.append({"ticket": horse, "probability": probability,
                               "odds": odds, "gross_expected_return": round(probability * odds, 6),
                               "net_ev": round(probability * odds - 1, 6)})
            row["ticket_types"]["WIN"] = {
                "status": "QUOTED" if quoted else "NO_QUOTE",
                "tickets": sorted(quoted, key=lambda x: x["net_ev"], reverse=True),
                "source_url": quote_race["source_url"],
                "captured_at": market["captured_at"],
            }
            row["status"] = "PARTIAL_WIN_ONLY" if quoted else "NO_QUOTE"
            row["reason"] = "OTHER_TICKET_TYPES_NOT_IN_VERIFIED_FEED"
        result["races"].append(row)
    return result


def main():
    if not REPORT.exists():
        raise SystemExit("PROBABILITY_REPORT_MISSING")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    market = json.loads(MARKET.read_text(encoding="utf-8")) if MARKET.exists() else {}
    output = compare(report, market)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"race_count": len(output["races"]), "quote_time_valid": output["quote_time_valid"],
                      "win_quoted": sum(r["status"] == "PARTIAL_WIN_ONLY" for r in output["races"]) }))


if __name__ == "__main__":
    main()
