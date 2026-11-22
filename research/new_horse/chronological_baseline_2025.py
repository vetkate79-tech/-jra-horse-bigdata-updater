#!/usr/bin/env python3
"""2025 historical new-horse candidate chronological baseline (research only).

Important: historical race_name in this dataset is corrupted ('緊急情報').
Candidate = ALL runners aged 2 and first observed in this FULL calendar-year result
file. This is a proxy, NOT an official verified 新馬 classification. No production use.
Only jockey/trainer identities are predictors; all results are labels.
Holdout 2025-09-01 onward. Same-day results never enter that day's predictions.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

SOURCE = Path("data/race_results_html_2025.csv")
HOLDOUT = "2025-09-01"

def main():
    with SOURCE.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda x: (x["race_date"], x["race_id"]))
    seen = set()
    races = defaultdict(list)
    for row in rows:
        horse_id = row["horse_id"]
        row["_first_observed"] = horse_id not in seen
        seen.add(horse_id)
        races[row["race_id"]].append(row)
    candidate = [r for r in races.values()
                 if len(r) >= 6 and all(
                     x["_first_observed"] and str(x["sex_age"]).endswith("2")
                     for x in r)]
    days = defaultdict(list)
    for race in candidate:
        days[race[0]["race_date"]].append(race)
    prior = defaultdict(lambda: [0, 0])
    evaluated = []
    for day in sorted(days):
        for race in days[day]:
            def score(x):
                j = prior[("j", x["jockey"])]
                t = prior[("t", x["trainer"])]
                return .5 * (j[1] + 3) / (j[0] + 30) + .5 * (t[1] + 3) / (t[0] + 30)
            pick = max(race, key=score)
            if day >= HOLDOUT:
                evaluated.append({
                    "race_id": race[0]["race_id"], "date": day,
                    "horse_id": pick["horse_id"], "field_size": len(race),
                    "top3": int(pick["finish_position"]) <= 3,
                    "win": int(pick["finish_position"]) == 1,
                })
        # Update only after ALL races on this calendar day were predicted.
        for race in days[day]:
            for x in race:
                for key in (("j", x["jockey"]), ("t", x["trainer"])):
                    prior[key][0] += 1
                    prior[key][1] += int(x["finish_position"]) <= 3
    n = len(evaluated)
    result = {
        "source": str(SOURCE), "source_rows": len(rows),
        "source_races": len(races), "candidate_races_unverified": len(candidate),
        "holdout_start": HOLDOUT, "holdout_races": n,
        "top3_hits": sum(x["top3"] for x in evaluated),
        "top3_rate": sum(x["top3"] for x in evaluated)/n if n else None,
        "win_hits": sum(x["win"] for x in evaluated),
        "win_rate": sum(x["win"] for x in evaluated)/n if n else None,
        "random_top3_expected_hits": sum(3/x["field_size"] for x in evaluated),
        "predictors": ["historical jockey debut top3", "historical trainer debut top3"],
        "training_rule": "only earlier calendar dates; day-batched updates",
        "official_new_horse_verified": False,
        "v2_compared": False,
        "production_promoted": False,
        "warnings": [
            "race_name is corrupted; candidates are proxy only",
            "tie break follows source ordering; no odds used",
            "only 2025 data, cannot establish multi-year generalization",
            "historical debut features and model V2 predictions not yet reconstructed",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
