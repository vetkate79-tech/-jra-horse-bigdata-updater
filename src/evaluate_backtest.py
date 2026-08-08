#!/usr/bin/env python3
"""Evaluate blind, chronological betting predictions without using future results."""
import csv, json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCE=Path("data/model_predictions.csv")
OUT=Path("status/backtest_summary.json")
REQUIRED=["race_date","race_id","model_version","bet_type","selection","stake_yen","payout_yen","is_hit"]

def f(x):
 try:return float(x)
 except (TypeError,ValueError):return 0.0

def week_key(s):
 d=datetime.strptime(s,"%Y-%m-%d").date()
 monday=d.fromordinal(d.toordinal()-d.weekday())
 return monday.isoformat()

def main():
 if not SOURCE.exists():raise SystemExit("data/model_predictions.csv is missing")
 with SOURCE.open(encoding="utf-8-sig",newline="") as fp:
  reader=csv.DictReader(fp);missing=[x for x in REQUIRED if x not in (reader.fieldnames or [])]
  if missing:raise SystemExit("Missing columns: "+",".join(missing))
  rows=list(reader)
 duplicate=[];seen=set();agg=defaultdict(lambda:{"stake":0.0,"payout":0.0,"bets":0,"hits":0})
 for n,r in enumerate(rows,2):
  key=(r["race_id"],r["model_version"],r["bet_type"],r["selection"])
  if key in seen:duplicate.append({"row":n,"key":key})
  seen.add(key)
  a=agg[(r["model_version"],week_key(r["race_date"]))]
  a["stake"]+=f(r["stake_yen"]);a["payout"]+=f(r["payout_yen"]);a["bets"]+=1
  a["hits"]+=str(r["is_hit"]).lower() in ("1","true","yes")
 if duplicate:raise SystemExit(f"duplicate predictions: {len(duplicate)}")
 versions=defaultdict(list)
 for (version,week),a in sorted(agg.items()):
  a["week"]=week;a["roi_pct"]=round(a["payout"]/a["stake"]*100,2) if a["stake"] else 0
  a["hit_rate_pct"]=round(a["hits"]/a["bets"]*100,2) if a["bets"] else 0
  versions[version].append(a)
 result={}
 for version,weeks in versions.items():
  streak=best=0
  for w in weeks:
   streak=streak+1 if w["roi_pct"]>=130 else 0;best=max(best,streak)
  stake=sum(w["stake"] for w in weeks);payout=sum(w["payout"] for w in weeks)
  result[version]={"weeks":weeks,"total_roi_pct":round(payout/stake*100,2) if stake else 0,
                   "best_130pct_streak":best,"completion_gate":best>=3}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({"evaluation":"blind_chronological","models":result},ensure_ascii=False,indent=2),encoding="utf-8")
 print(OUT.read_text(encoding="utf-8"))

if __name__=="__main__":main()
