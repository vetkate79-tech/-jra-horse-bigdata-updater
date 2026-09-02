#!/usr/bin/env python3
"""Evaluate blind chronological predictions with anti-overfit, multi-horizon gates."""
import csv, json, statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCE=Path("data/model_predictions.csv")
OUT=Path("status/backtest_summary.json")
POLICY=Path("config/evolution-governance-v2.json")
REQUIRED=["race_date","race_id","model_version","bet_type","selection","stake_yen","payout_yen","is_hit"]

def f(x):
 try:return float(x)
 except (TypeError,ValueError):return 0.0

def b(x):return str(x).lower() in ("1","true","yes")
def week_key(s):
 d=datetime.strptime(s,"%Y-%m-%d").date();m=d.fromordinal(d.toordinal()-d.weekday());return m.isoformat()
def pct(n,d):return round(n/d*100,2) if d else 0.0

def main():
 if not SOURCE.exists():raise SystemExit("data/model_predictions.csv is missing")
 policy=json.loads(POLICY.read_text(encoding="utf-8")) if POLICY.exists() else {}
 big=policy.get("layers",{}).get("structural_big_data",{})
 evo=policy.get("evolution",{});promo=evo.get("promotion",{})
 min_races=int(big.get("minimum_unique_races_for_promotion",500));min_weeks=int(big.get("minimum_independent_weeks",8))
 catastrophic=float(promo.get("catastrophic_week_roi_floor_pct",35.0))
 with SOURCE.open(encoding="utf-8-sig",newline="") as fp:
  reader=csv.DictReader(fp);fields=reader.fieldnames or [];missing=[x for x in REQUIRED if x not in fields]
  if missing:raise SystemExit("Missing columns: "+",".join(missing))
  rows=list(reader)
 seen=set();duplicate=[];weeks=defaultdict(lambda:{"stake":0.0,"payout":0.0,"bets":0,"hits":0,"races":set(),"axis_n":0,"axis_ok":0,"cand_n":0,"cand_ok":0})
 for n,r in enumerate(rows,2):
  key=(r["race_id"],r["model_version"],r["bet_type"],r["selection"])
  if key in seen:duplicate.append({"row":n,"key":key})
  seen.add(key);a=weeks[(r["model_version"],week_key(r["race_date"]))]
  a["stake"]+=f(r["stake_yen"]);a["payout"]+=f(r["payout_yen"]);a["bets"]+=1;a["hits"]+=b(r["is_hit"]);a["races"].add(r["race_id"])
  if "axis_top3" in fields and str(r.get("axis_top3","")).strip()!="":a["axis_n"]+=1;a["axis_ok"]+=b(r.get("axis_top3"))
  if "candidate_complete" in fields and str(r.get("candidate_complete","")).strip()!="":a["cand_n"]+=1;a["cand_ok"]+=b(r.get("candidate_complete"))
 if duplicate:raise SystemExit(f"duplicate predictions: {len(duplicate)}")
 by_model=defaultdict(list)
 for (version,w),a in sorted(weeks.items()):
  item={"week":w,"unique_races":len(a["races"]),"bets":a["bets"],"hits":a["hits"],"stake":a["stake"],"payout":a["payout"],
        "roi_pct":pct(a["payout"],a["stake"]),"hit_rate_pct":pct(a["hits"],a["bets"])}
  if a["axis_n"]:item["axis_top3_pct"]=pct(a["axis_ok"],a["axis_n"])
  if a["cand_n"]:item["candidate_complete_pct"]=pct(a["cand_ok"],a["cand_n"])
  by_model[version].append(item)
 result={}
 for version,ws in by_model.items():
  stake=sum(x["stake"] for x in ws);payout=sum(x["payout"] for x in ws);unique_races=sum(x["unique_races"] for x in ws)
  rois=[x["roi_pct"] for x in ws];hit_rates=[x["hit_rate_pct"] for x in ws]
  axis=[x["axis_top3_pct"] for x in ws if "axis_top3_pct" in x];cand=[x["candidate_complete_pct"] for x in ws if "candidate_complete_pct" in x]
  big_data_gate=unique_races>=min_races and len(ws)>=min_weeks
  stability_gate=(sum(x>=80 for x in rois)/len(rois)>=0.5 if rois else False) and (min(rois)>=catastrophic if rois else False)
  promotion_gate=bool(big_data_gate and stability_gate)
  result[version]={"weeks":ws,"unique_races":unique_races,"independent_weeks":len(ws),"total_roi_pct":pct(payout,stake),
   "median_weekly_roi_pct":round(statistics.median(rois),2) if rois else 0.0,"median_weekly_hit_rate_pct":round(statistics.median(hit_rates),2) if hit_rates else 0.0,
   "worst_week_roi_pct":min(rois) if rois else 0.0,"axis_top3_median_pct":round(statistics.median(axis),2) if axis else None,
   "candidate_complete_median_pct":round(statistics.median(cand),2) if cand else None,
   "big_data_gate":big_data_gate,"stability_gate":stability_gate,"promotion_gate":promotion_gate,
   "promotion_reason":"PASS" if promotion_gate else "REJECT_SHORT_SAMPLE_OR_UNSTABLE",
   "short_term_note":"Recent-context signals may adjust ranking only within governance max weight; short-window ROI cannot override this gate."}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({"evaluation":"blind_chronological_multi_horizon","policy":str(POLICY),"models":result},ensure_ascii=False,indent=2),encoding="utf-8")
 print(OUT.read_text(encoding="utf-8"))

if __name__=="__main__":main()
