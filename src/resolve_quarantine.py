#!/usr/bin/env python3
"""Reprocess quarantined JRA PDFs; promote only independently confirmed race vectors."""
import csv, json, os, subprocess, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path

CONFIGS=[("400","6"),("500","6"),("600","6"),("500","4")]
CORE=("horse_name","time","body_weight","win_odds")
FIELDS=["source_pdf","race_date","course","meeting_no","meeting_day","race_no","finish_position",
        "horse_name","time","body_weight","win_odds","resolution_votes","resolution_configs","validation_status"]

def read_csv(path):
 if not path.exists():return []
 with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def attempt(pdf,root,dpi,psm):
 out=root/f"attempt_{dpi}_{psm}.csv";env=os.environ.copy();env.update(OCR_DPI=dpi,OCR_PSM=psm)
 subprocess.run([sys.executable,"src/extract_jra_pdf_hybrid.py",str(pdf),"--out",str(out)],check=True,env=env)
 return read_csv(out)+read_csv(out.with_name(out.stem+"_quarantine.csv"))

def resolve(pdf,out_dir):
 attempts=[]
 with tempfile.TemporaryDirectory() as td:
  root=Path(td)
  for dpi,psm in CONFIGS:
   rows=attempt(pdf,root,dpi,psm)
   clean=defaultdict(list)
   for r in rows:
    if "row_mismatch" not in r.get("validation_reason",""):clean[r["race_no"]].append(r)
   attempts.append(((dpi,psm),clean))
  race_ids=sorted(set(k for _,races in attempts for k in races),key=int)
  resolved=[];unresolved=[]
  for race_no in race_ids:
   candidates=[(cfg,rows[race_no]) for cfg,rows in attempts if race_no in rows]
   lengths=Counter(len(rows) for _,rows in candidates)
   expected=lengths.most_common(1)[0][0] if lengths else 0
   same_length=[(cfg,rows) for cfg,rows in candidates if len(rows)==expected]
   race_out=[];reason=""
   if expected<3 or len(same_length)<2:reason="INSUFFICIENT_COMPLETE_ATTEMPTS"
   else:
    for idx in range(expected):
     base=dict(same_length[0][1][idx]);confirmed={};votes=[]
     for field in CORE:
      values=Counter(r[idx].get(field,"") for _,r in same_length if r[idx].get(field,"")!="")
      if not values or values.most_common(1)[0][1]<2:
       reason=f"NO_TWO_WAY_CONSENSUS:{field}:row{idx+1}";break
      confirmed[field],count=values.most_common(1)[0];votes.append(count)
     if reason:break
     base.update(confirmed);base["resolution_votes"]=min(votes)
     base["resolution_configs"]=",".join(f"{d}dpi_psm{p}" for (d,p),_ in same_length)
     base["validation_status"]="RESOLVED_CONSENSUS";race_out.append(base)
   if reason:
    unresolved.append({"source_pdf":pdf.name,"race_no":race_no,"reason":reason,
                       "attempts":len(candidates),"row_counts":[len(x) for _,x in candidates]})
   else:resolved.extend(race_out)
 out_dir.mkdir(parents=True,exist_ok=True)
 resolved_path=out_dir/(pdf.stem+"_resolved.csv")
 with resolved_path.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore");w.writeheader();w.writerows(resolved)
 report={"pdf":pdf.name,"resolved_rows":len(resolved),"unresolved_races":unresolved,
         "configs":[{"dpi":d,"psm":p} for d,p in CONFIGS]}
 (out_dir/(pdf.stem+"_resolution.json")).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
 if len(sys.argv)<2:raise SystemExit("usage: resolve_quarantine.py PDF [OUT_DIR]")
 resolve(Path(sys.argv[1]),Path(sys.argv[2] if len(sys.argv)>2 else "data/quarantine_resolved"))
