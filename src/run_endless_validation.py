#!/usr/bin/env python3
"""Leakage-safe walk-forward model selection. Resumes until 3 unseen weeks exceed 130% ROI."""
import csv, json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCE=Path("data/candidate_predictions.csv")
STATE=Path("status/endless_validation_state.json")
TARGET_ROI=130.0
TARGET_STREAK=3
MIN_TRAIN_WEEKS=4
MIN_TRAIN_BETS=20

def num(x):
 try:return float(x)
 except (TypeError,ValueError):return 0.0

def load_state():
 if STATE.exists():return json.loads(STATE.read_text(encoding="utf-8"))
 return {"status":"WAITING_DATA","evaluated_weeks":[],"current_streak":0,"completed":False}

def save(state):
 STATE.parent.mkdir(parents=True,exist_ok=True)
 state["updated_at"]=datetime.utcnow().isoformat()+"Z"
 STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
 state=load_state()
 if not SOURCE.exists():
  state.update(status="BLOCKED_NO_CONFIRMED_PREDICTIONS",message="No fabricated backtest was run")
  save(state);print(json.dumps(state,ensure_ascii=False));return
 with SOURCE.open(encoding="utf-8-sig",newline="") as f:
  rows=list(csv.DictReader(f))
 required={"week","race_id","model_version","stake_yen","payout_yen","is_hit","data_status"}
 missing=required-set(rows[0] if rows else [])
 if missing:
  state.update(status="BLOCKED_BAD_SCHEMA",missing=sorted(missing));save(state);return
 # Only rows produced from fully validated source data may enter evaluation.
 rows=[r for r in rows if r["data_status"] in ("PASS","RESOLVED_CONSENSUS")]
 weeks=sorted(set(r["week"] for r in rows))
 done=set(x["week"] for x in state.get("evaluated_weeks",[]))
 for test_index in range(MIN_TRAIN_WEEKS,len(weeks)):
  test_week=weeks[test_index]
  if test_week in done:continue
  train_weeks=set(weeks[:test_index]);stats=defaultdict(lambda:{"stake":0.0,"payout":0.0,"bets":0})
  for r in rows:
   if r["week"] in train_weeks:
    s=stats[r["model_version"]];s["stake"]+=num(r["stake_yen"]);s["payout"]+=num(r["payout_yen"]);s["bets"]+=1
  eligible=[]
  for model,s in stats.items():
   if s["bets"]>=MIN_TRAIN_BETS and s["stake"]>0:
    roi=s["payout"]/s["stake"]*100
    # ROI is primary; hit rate is never used to inflate stake or leak test outcomes.
    eligible.append((roi,model))
  if not eligible:continue
  _,chosen=max(eligible)
  test=[r for r in rows if r["week"]==test_week and r["model_version"]==chosen]
  stake=sum(num(r["stake_yen"]) for r in test);payout=sum(num(r["payout_yen"]) for r in test)
  bets=len(test);hits=sum(str(r["is_hit"]).lower() in ("1","true","yes") for r in test)
  roi=payout/stake*100 if stake else 0.0;hit=hits/bets*100 if bets else 0.0
  state["current_streak"]=state.get("current_streak",0)+1 if roi>=TARGET_ROI else 0
  state.setdefault("evaluated_weeks",[]).append({"week":test_week,"chosen_model":chosen,
   "roi_pct":round(roi,2),"hit_rate_pct":round(hit,2),"bets":bets,
   "passed_130":roi>=TARGET_ROI,"streak":state["current_streak"]})
  if state["current_streak"]>=TARGET_STREAK:
   state.update(status="COMPLETED_THREE_UNSEEN_WEEKS",completed=True,winning_model=chosen);break
 if not state.get("completed"):
  state["status"]="RUNNING_WAITING_NEXT_UNSEEN_WEEK" if weeks else "BLOCKED_NO_CONFIRMED_ROWS"
 save(state);print(json.dumps(state,ensure_ascii=False))

if __name__=="__main__":main()
