#!/usr/bin/env python3
"""Reprocess quarantined JRA PDFs; promote only independently confirmed race vectors."""
import csv, json, os, subprocess, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path

CONFIGS=[("400","6"),("500","6"),("600","6"),("500","4")]
CORE=("horse_name","time","body_weight","win_odds")
FIELDS=["source_pdf","race_date","course","meeting_no","meeting_day","race_no","finish_position",
        "horse_name","time","body_weight","win_odds","resolution_votes","resolution_configs","field_status_json","validation_status"]

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
  # Two independent reads are the minimum. Expensive fallbacks run only while
  # at least one race still lacks a two-way complete consensus.
  for config_index,(dpi,psm) in enumerate(CONFIGS):
   rows=attempt(pdf,root,dpi,psm)
   clean=defaultdict(list)
   for r in rows:
    if "row_mismatch" not in r.get("validation_reason",""):clean[r["race_no"]].append(r)
   attempts.append(((dpi,psm),clean))
   if config_index>=1:
    common=set(attempts[0][1]) & set(attempts[1][1])
    if len(common)==12:
     stable=True
     for race_no in common:
      first,second=attempts[0][1][race_no],attempts[1][1][race_no]
      if len(first)!=len(second) or len(first)<3:
       stable=False;break
      if not all(all(first[i].get(field)==second[i].get(field) for field in CORE) for i in range(len(first))):
       stable=False;break
     if stable:break
  race_ids=sorted(set(k for _,races in attempts for k in races),key=int)
  resolved=[];unresolved=[];unresolved_cells=[]
  for race_no in race_ids:
   candidates=[(cfg,rows[race_no]) for cfg,rows in attempts if race_no in rows]
   lengths=Counter(len(rows) for _,rows in candidates)
   expected=lengths.most_common(1)[0][0] if lengths else 0
   same_length=[(cfg,rows) for cfg,rows in candidates if len(rows)==expected]
   race_out=[];reason=""
   if expected<3 or len(same_length)<2:reason="INSUFFICIENT_COMPLETE_ATTEMPTS"
   else:
    for idx in range(expected):
     base=dict(same_length[0][1][idx]);confirmed={};votes=[];field_status={}
     for field in CORE:
      values=Counter(r[idx].get(field,"") for _,r in same_length if r[idx].get(field,"")!="")
      if not values or values.most_common(1)[0][1]<2:
       confirmed[field]="";field_status[field]="UNRESOLVED"
       unresolved_cells.append({"source_pdf":pdf.name,"race_no":race_no,"row":idx+1,"field":field,
                                "values":dict(values)})
      else:
       confirmed[field],count=values.most_common(1)[0];votes.append(count);field_status[field]=f"CONSENSUS_{count}"
     base.update(confirmed);base["resolution_votes"]=min(votes) if votes else 0
     base["resolution_configs"]=",".join(f"{d}dpi_psm{p}" for (d,p),_ in same_length)
     base["field_status_json"]=json.dumps(field_status,ensure_ascii=False,sort_keys=True)
     base["validation_status"]="RESOLVED_CONSENSUS" if all(v!="UNRESOLVED" for v in field_status.values()) else "RESOLVED_CONSENSUS_PARTIAL"
     race_out.append(base)
   if reason:
    unresolved.append({"source_pdf":pdf.name,"race_no":race_no,"reason":reason,
                       "attempts":len(candidates),"row_counts":[len(x) for _,x in candidates]})
   else:resolved.extend(race_out)
 out_dir.mkdir(parents=True,exist_ok=True)
 resolved_path=out_dir/(pdf.stem+"_resolved.csv")
 with resolved_path.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore");w.writeheader();w.writerows(resolved)
 report={"pdf":pdf.name,"resolved_rows":len(resolved),"unresolved_races":unresolved,"unresolved_cells":unresolved_cells,
         "configs":[{"dpi":d,"psm":p} for d,p in CONFIGS]}
 (out_dir/(pdf.stem+"_resolution.json")).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
 if len(sys.argv)<2:raise SystemExit("usage: resolve_quarantine.py PDF [OUT_DIR]")
 resolve(Path(sys.argv[1]),Path(sys.argv[2] if len(sys.argv)>2 else "data/quarantine_resolved"))
