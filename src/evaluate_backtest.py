#!/usr/bin/env python3
"""Evaluate blind chronological predictions with anti-overfit, multi-horizon and repeatability gates."""
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
def sd(xs):return round(statistics.pstdev(xs),2) if len(xs)>1 else 0.0
def cv(xs):
 if len(xs)<2:return 0.0
 mean=statistics.mean(xs)
 return round(statistics.pstdev(xs)/abs(mean),3) if mean else 999.0

def main():
 if not SOURCE.exists():raise SystemExit("data/model_predictions.csv is missing")
 policy=json.loads(POLICY.read_text(encoding="utf-8")) if POLICY.exists() else {}
 layers=policy.get("layers",{});big=layers.get("structural_big_data",{})
 evo=policy.get("evolution",{});promo=evo.get("promotion",{});rep=evo.get("repeatability",{})
 min_races=int(big.get("minimum_unique_races_for_promotion",500));min_weeks=int(big.get("minimum_independent_weeks",8))
 catastrophic=float(promo.get("catastrophic_week_roi_floor_pct",35.0))
 min_rounds=int(rep.get("minimum_independent_validation_rounds",3));positive_floor=float(rep.get("positive_round_roi_floor_pct",80.0))
 min_positive=float(rep.get("minimum_positive_round_ratio",.67));max_axis_sd=float(rep.get("maximum_axis_top3_stddev_pct_points",10.0))
 max_cand_sd=float(rep.get("maximum_candidate_complete_stddev_pct_points",12.0));max_roi_cv=float(rep.get("maximum_roi_coefficient_of_variation",1.25))
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
  stability_gate=(sum(x>=positive_floor for x in rois)/len(rois)>=0.5 if rois else False) and (min(rois)>=catastrophic if rois else False)
  rounds=len(ws);positive_rounds=sum(x>=positive_floor for x in rois);positive_ratio=(positive_rounds/rounds if rounds else 0.0)
  axis_sd=sd(axis);cand_sd=sd(cand);roi_cv=cv(rois)
  axis_stable=(not axis) or axis_sd<=max_axis_sd;cand_stable=(not cand) or cand_sd<=max_cand_sd;roi_stable=roi_cv<=max_roi_cv
  repeatability_gate=bool(rounds>=min_rounds and positive_ratio>=min_positive and axis_stable and cand_stable and roi_stable)
  axis_quality=min((statistics.median(axis)/70.0),1.0) if axis else .5
  cand_quality=min((statistics.median(cand)/75.0),1.0) if cand else .5
  axis_consistency=max(0.0,1-axis_sd/max(max_axis_sd*2,1)) if axis else .5
  cand_consistency=max(0.0,1-cand_sd/max(max_cand_sd*2,1)) if cand else .5
  roi_consistency=max(0.0,1-min(roi_cv,2)/2)
  repeatability_score=round(100*(.30*axis_quality*axis_consistency+.30*cand_quality*cand_consistency+.20*positive_ratio+.20*roi_consistency),1)
  grade='A' if repeatability_score>=80 else ('B' if repeatability_score>=65 else ('C' if repeatability_score>=50 else 'D'))
  promotion_gate=bool(big_data_gate and stability_gate and repeatability_gate)
  result[version]={"weeks":ws,"unique_races":unique_races,"independent_weeks":len(ws),"total_roi_pct":pct(payout,stake),
   "median_weekly_roi_pct":round(statistics.median(rois),2) if rois else 0.0,"median_weekly_hit_rate_pct":round(statistics.median(hit_rates),2) if hit_rates else 0.0,
   "worst_week_roi_pct":min(rois) if rois else 0.0,"axis_top3_median_pct":round(statistics.median(axis),2) if axis else None,
   "candidate_complete_median_pct":round(statistics.median(cand),2) if cand else None,
   "repeatability":{"independent_rounds":rounds,"positive_rounds":positive_rounds,"positive_round_ratio":round(positive_ratio,3),
      "axis_top3_stddev_pct_points":axis_sd if axis else None,"candidate_complete_stddev_pct_points":cand_sd if cand else None,
      "roi_coefficient_of_variation":roi_cv,"score":repeatability_score,"grade":grade,"gate":repeatability_gate,
      "note":"Same 36R block reruns do not count as independent replication; different weeks/conditions are required."},
   "retest_required":bool((pct(payout,stake)>=100 or (axis and statistics.median(axis)>=60) or (cand and statistics.median(cand)>=65)) and not repeatability_gate),
   "big_data_gate":big_data_gate,"stability_gate":stability_gate,"repeatability_gate":repeatability_gate,"promotion_gate":promotion_gate,
   "promotion_reason":"PASS" if promotion_gate else "REJECT_SHORT_SAMPLE_UNSTABLE_OR_NOT_REPLICATED",
   "short_term_note":"Recent-context signals may adjust ranking only within governance max weight; short-window ROI cannot override repeatability or big-data gates."}
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({"evaluation":"blind_chronological_multi_horizon_repeatability","policy":str(POLICY),"models":result},ensure_ascii=False,indent=2),encoding="utf-8")
 print(OUT.read_text(encoding="utf-8"))

if __name__=="__main__":main()
