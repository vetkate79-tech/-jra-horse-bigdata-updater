#!/usr/bin/env python3
"""Build all-horse profiles from verified structured JRA HTML rows."""
import csv, json
from collections import Counter, defaultdict
from pathlib import Path

YEAR=2025
SOURCE=Path(f"data/race_results_html_{YEAR}.csv")
OUT=Path(f"data/horse_profiles_{YEAR}.csv")
REPORT=Path(f"status/horse_profile_quality_{YEAR}.json")

def n(v):
 try:return float(v)
 except (TypeError,ValueError):return None

def main():
 with SOURCE.open(encoding="utf-8-sig",newline="") as f:rows=[r for r in csv.DictReader(f) if r["data_status"]=="PASS_HTML"]
 grouped=defaultdict(list)
 for r in rows:grouped[r["horse_name"]].append(r)
 profiles=[];errors=[]
 for name,starts in grouped.items():
  starts.sort(key=lambda x:(x["race_date"],x["race_id"]))
  positions=[int(float(r["finish_position"])) for r in starts if n(r.get("finish_position")) and n(r["finish_position"])>0]
  total=len(positions);wins=sum(x==1 for x in positions);top2=sum(x<=2 for x in positions);top3=sum(x<=3 for x in positions)
  last3f=[n(r.get("last3f")) for r in starts if n(r.get("last3f")) is not None]
  by_condition=Counter((r.get("course",""),r.get("surface",""),r.get("distance_m","")) for r in starts)
  ids={r.get("horse_id","") for r in starts if r.get("horse_id","")}
  if len(ids)>1:errors.append({"horse_name":name,"code":"MULTIPLE_HORSE_IDS","ids":sorted(ids)})
  profiles.append({"horse_name":name,"horse_id":next(iter(ids),""),
   "sex_age_latest":starts[-1].get("sex_age",""),"starts":total,"wins":wins,"top2":top2,"top3":top3,
   "win_rate":round(wins/total,6) if total else "","quinella_rate":round(top2/total,6) if total else "",
   "show_rate":round(top3/total,6) if total else "",
   "avg_finish":round(sum(positions)/total,4) if total else "",
   "avg_last3f":round(sum(last3f)/len(last3f),4) if last3f else "",
   "best_last3f":min(last3f) if last3f else "",
   "first_race_date":starts[0]["race_date"],"latest_race_date":starts[-1]["race_date"],
   "latest_course":starts[-1].get("course",""),"latest_surface":starts[-1].get("surface",""),
   "latest_distance_m":starts[-1].get("distance_m",""),"latest_finish":starts[-1].get("finish_position",""),
   "condition_starts_json":json.dumps({"|".join(k):v for k,v in by_condition.items()},ensure_ascii=False,sort_keys=True)})
 profiles.sort(key=lambda x:x["horse_name"])
 fields=list(profiles[0]) if profiles else [];tmp=OUT.with_suffix(".tmp")
 with tmp.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(profiles)
 tmp.replace(OUT)
 missing_id=sum(not x["horse_id"] for x in profiles)
 report={"source_rows":len(rows),"profiles":len(profiles),"missing_horse_id":missing_id,
  "identity_errors":errors,"status":"PASS" if len(profiles)>7000 and missing_id==0 and not errors else "INCOMPLETE"}
 REPORT.parent.mkdir(exist_ok=True);REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({k:v for k,v in report.items() if k!="identity_errors"},ensure_ascii=False))
 if report["status"]!="PASS":raise SystemExit("profile quality gate failed")

if __name__=="__main__":main()
