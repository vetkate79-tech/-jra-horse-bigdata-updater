#!/usr/bin/env python3
"""Validate normalized race history and build leakage-safe horse profiles."""
import csv, json, math
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

DATA=Path("data")
RESULTS=DATA/"race_results.csv"
PROFILES=DATA/"horse_profiles.csv"
REPORT=Path("status")/"data_quality.json"
REQUIRED=["race_id","race_date","course","race_no","race_class","surface","distance_m",
"going","weather","horse_name","sex","age","frame_no","horse_no","carried_weight",
"jockey","trainer","body_weight","body_weight_delta","finish_position","time_seconds",
"margin","last3f","corner_positions","win_odds","popularity","prize_yen","source_url"]
NUMERIC=["race_no","distance_m","age","frame_no","horse_no","carried_weight","body_weight",
"body_weight_delta","finish_position","time_seconds","margin","last3f","win_odds",
"popularity","prize_yen"]

def number(value):
 try:return float(value)
 except (TypeError,ValueError):return None

def validate(rows):
 errors=[];warnings=[];seen=set();races=defaultdict(list)
 today=date.today()
 for n,row in enumerate(rows,2):
  key=(row["race_id"],row["horse_name"])
  if key in seen:errors.append({"row":n,"code":"DUPLICATE_START","key":key})
  seen.add(key);races[row["race_id"]].append(row)
  try:d=datetime.strptime(row["race_date"],"%Y-%m-%d").date()
  except ValueError:errors.append({"row":n,"code":"BAD_DATE"});continue
  if d>today:errors.append({"row":n,"code":"FUTURE_DATE"})
  for col in NUMERIC:
   if row.get(col)!="" and number(row.get(col)) is None:errors.append({"row":n,"code":"NON_NUMERIC","column":col})
  pos=number(row.get("finish_position"));dist=number(row.get("distance_m"));tm=number(row.get("time_seconds"))
  if pos is not None and pos<0:errors.append({"row":n,"code":"BAD_FINISH"})
  if dist is not None and not 800<=dist<=4300:warnings.append({"row":n,"code":"DISTANCE_OUTLIER"})
  if tm is not None and not 40<=tm<=400:errors.append({"row":n,"code":"TIME_OUTLIER"})
 for race_id,items in races.items():
  horses=[number(x.get("horse_no")) for x in items if number(x.get("horse_no")) is not None]
  if len(horses)!=len(set(horses)):errors.append({"race_id":race_id,"code":"DUPLICATE_HORSE_NO"})
  winners=sum(number(x.get("finish_position"))==1 for x in items)
  if winners!=1:errors.append({"race_id":race_id,"code":"WINNER_COUNT","actual":winners})
 return errors,warnings

def build(rows):
 grouped=defaultdict(list)
 for r in rows:grouped[r["horse_name"]].append(r)
 out=[]
 for horse,starts in grouped.items():
  starts.sort(key=lambda r:(r["race_date"],r["race_id"]))
  valid=[r for r in starts if number(r.get("finish_position")) and number(r["finish_position"])>0]
  n=len(valid);wins=sum(number(r["finish_position"])==1 for r in valid)
  top2=sum(number(r["finish_position"])<=2 for r in valid);top3=sum(number(r["finish_position"])<=3 for r in valid)
  turf=[r for r in valid if r["surface"]=="芝"];dirt=[r for r in valid if r["surface"]=="ダート"]
  avg=lambda vals:round(sum(vals)/len(vals),4) if vals else ""
  out.append({
   "horse_name":horse,"sex":starts[-1]["sex"],"age":starts[-1]["age"],
   "starts":n,"wins":wins,"top2":top2,"top3":top3,
   "win_rate":avg([wins/n]) if n else "","quinella_rate":avg([top2/n]) if n else "",
   "show_rate":avg([top3/n]) if n else "",
   "avg_finish":avg([number(r["finish_position"]) for r in valid]),
   "avg_last3f":avg([number(r["last3f"]) for r in valid if number(r.get("last3f")) is not None]),
   "turf_starts":len(turf),"dirt_starts":len(dirt),
   "latest_race_date":starts[-1]["race_date"],"latest_course":starts[-1]["course"],
   "latest_distance_m":starts[-1]["distance_m"],"latest_finish":starts[-1]["finish_position"],
   "history_rows":len(starts)
  })
 return sorted(out,key=lambda x:x["horse_name"])

def main():
 REPORT.parent.mkdir(parents=True,exist_ok=True)
 if not RESULTS.exists():raise SystemExit("data/race_results.csv is missing; no profile was fabricated")
 with RESULTS.open(encoding="utf-8-sig",newline="") as f:
  reader=csv.DictReader(f);missing=[x for x in REQUIRED if x not in (reader.fieldnames or [])]
  if missing:raise SystemExit("Missing columns: "+",".join(missing))
  rows=list(reader)
 errors,warnings=validate(rows)
 report={"rows":len(rows),"races":len(set(r["race_id"] for r in rows)),"errors":errors[:500],
         "error_count":len(errors),"warning_count":len(warnings),"status":"PASS" if not errors else "FAIL"}
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 if errors:raise SystemExit(f"quality validation failed: {len(errors)} errors")
 profiles=build(rows)
 fields=list(profiles[0]) if profiles else []
 tmp=PROFILES.with_suffix(".tmp")
 with tmp.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(profiles)
 tmp.replace(PROFILES)
 print(json.dumps({"profiles":len(profiles),"quality":"PASS"},ensure_ascii=False))

if __name__=="__main__":main()
