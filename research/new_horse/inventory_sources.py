#!/usr/bin/env python3
"""Read-only inventory of available historical datasets for new-horse research.

Does not train, predict, publish or change any existing model.
"""
import csv
import json
from pathlib import Path

SOURCES = (
    "data/race_results_html_2025.csv",
    "data/race_results_html_2026.csv",
    "data/horse_profiles_2025.csv",
    "data/horse_ids_2025.csv",
)
TOKENS = ("新馬", "メイクデビュー", "debut", "maiden")

def inspect(path):
    p = Path(path)
    if not p.exists():
        return {"path": path, "exists": False}
    with p.open(encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        rows = 0
        keyword_rows = 0
        missing = {k: 0 for k in fields}
        for row in reader:
            rows += 1
            if any(token in str(value).lower() for value in row.values() for token in TOKENS):
                keyword_rows += 1
            for k in fields:
                if not str(row.get(k) or "").strip():
                    missing[k] += 1
    return {
        "path": path, "exists": True, "rows": rows, "columns": fields,
        "keyword_rows_not_confirmed_new_horse": keyword_rows,
        "missing_by_column": missing,
        "warning": "Keyword hits are NOT confirmed debut races; join on race ID and validate before training.",
    }

def main():
    result = {
        "purpose": "new-horse historical source inventory",
        "sources": [inspect(p) for p in SOURCES],
        "training_performed": False,
        "prediction_changed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
