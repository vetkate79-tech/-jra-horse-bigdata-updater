#!/usr/bin/env python3
"""Create a leakage-safe validation ledger only after every prerequisite passes."""
import csv, json
from datetime import datetime
from pathlib import Path

AUDIT=Path("status/validation_prerequisite_audit.json")
OUT=Path("data/validation_bets.csv")
REPORT=Path("status/validation_dataset_quality.json")

def read(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def main():
    audit=json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit["status"]!="READY":
        REPORT.write_text(json.dumps({"status":"BLOCKED","blocking_prerequisites":audit["blocking_prerequisites"]},ensure_ascii=False,indent=2),encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8")); return
    predictions=read("data/model_predictions.csv"); payouts=read("data/race_payouts_2025.csv")
    payout_index={(r["race_id"],r["bet_type"],r["winning_selection"]):r for r in payouts}
    rows=[]; errors=[]; seen=set()
    for p in predictions:
        key=(p["race_id"],p["model_version"],p["bet_type"],p["selection"])
        if key in seen: errors.append({"prediction_id":p["prediction_id"],"code":"DUPLICATE_PREDICTION"}); continue
        seen.add(key)
        try:
            cutoff=datetime.fromisoformat(p["feature_cutoff_at"].replace("Z","+00:00"))
            generated=datetime.fromisoformat(p["generated_at"].replace("Z","+00:00"))
            if generated>cutoff: errors.append({"prediction_id":p["prediction_id"],"code":"GENERATED_AFTER_CUTOFF"}); continue
        except ValueError: errors.append({"prediction_id":p["prediction_id"],"code":"BAD_TIMESTAMP"}); continue
        hit=payout_index.get((p["race_id"],p["bet_type"],p["selection"]))
        payout=float(hit["payout_per_100_yen"])*float(p["stake_yen"])/100 if hit else 0.0
        rows.append({**p,"payout_yen":round(payout,2),"is_hit":bool(hit),"result_join_status":"PASS"})
    if errors: status="INCOMPLETE"
    else: status="PASS"
    if rows:
        with OUT.open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    REPORT.write_text(json.dumps({"status":status,"rows":len(rows),"errors":errors},ensure_ascii=False,indent=2),encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))

if __name__=="__main__":main()
