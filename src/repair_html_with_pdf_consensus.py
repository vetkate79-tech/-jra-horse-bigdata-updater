#!/usr/bin/env python3
"""Repair verified HTML rows using independently resolved official result-PDF values.

Only missing or semantically invalid cells are changed. Every change keeps its original
value and provenance; uncertain conflicts remain quarantined.
"""
import argparse,csv,json,re
from collections import defaultdict
from pathlib import Path

PATCHABLE={"time":"time","body_weight":"body_weight","win_odds":"win_odds"}

def rows(path):
 with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def norm_name(x):return re.sub(r"\s+","",x or "")
def valid_time(x):return bool(re.fullmatch(r"[0-3]:[0-5]\d\.\d",x or ""))
def valid_odds(x):
 try:return float(x)>0
 except (TypeError,ValueError):return False
def valid_body(x):
 try:return 300<=int(float(x))<=699
 except (TypeError,ValueError):return False

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--html",type=Path,required=True);ap.add_argument("--resolved-dir",type=Path,required=True)
 ap.add_argument("--out",type=Path,required=True);ap.add_argument("--audit",type=Path,required=True);a=ap.parse_args()
 base=rows(a.html);resolved=[]
 for p in sorted(a.resolved_dir.glob("*_resolved.csv")):resolved.extend(rows(p))
 idx=defaultdict(list)
 for r in resolved:
  if r.get("validation_status") not in ("RESOLVED_CONSENSUS","RESOLVED_CONSENSUS_PARTIAL"):continue
  key=(r.get("race_date"),r.get("course"),str(r.get("meeting_no","")).zfill(2),str(r.get("meeting_day","")).zfill(2),str(r.get("race_no","")).zfill(2),norm_name(r.get("horse_name")))
  idx[key].append(r)
 repaired=[];conflicts=[];unmatched=0
 for row in base:
  key=(row.get("race_date"),row.get("course"),str(row.get("meeting_no","")).zfill(2),str(row.get("meeting_day","")).zfill(2),str(row.get("race_no","")).zfill(2),norm_name(row.get("horse_name")))
  candidates=idx.get(key,[]);changes={};original={};sources=[]
  if len(candidates)==1:
   pdf=candidates[0];sources=[pdf.get("source_pdf","")]
   if not valid_time(row.get("time")) and valid_time(pdf.get("time")):
    original["time"]=row.get("time","");row["time"]=pdf["time"];changes["time"]="PDF_CONSENSUS"
   if not valid_body(row.get("body_weight")) and valid_body(pdf.get("body_weight")):
    original["body_weight"]=row.get("body_weight","");row["body_weight"]=pdf["body_weight"];changes["body_weight"]="PDF_CONSENSUS"
   if not valid_odds(row.get("win_odds")) and valid_odds(pdf.get("win_odds")):
    original["win_odds"]=row.get("win_odds","");row["win_odds"]=pdf["win_odds"];changes["win_odds"]="PDF_CONSENSUS"
  elif len(candidates)>1:conflicts.append({"key":key,"code":"MULTIPLE_PDF_MATCHES","count":len(candidates)})
  else:unmatched+=1
  row["repair_fields_json"]=json.dumps(changes,ensure_ascii=False,sort_keys=True)
  row["repair_original_json"]=json.dumps(original,ensure_ascii=False,sort_keys=True)
  row["repair_sources_json"]=json.dumps(sources,ensure_ascii=False)
  row["repair_status"]="REPAIRED_VERIFIED" if changes else ("CONFLICT" if len(candidates)>1 else "UNCHANGED")
  repaired.append(row)
 a.out.parent.mkdir(parents=True,exist_ok=True)
 fields=list(repaired[0]) if repaired else []
 with a.out.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(repaired)
 report={"status":"PASS" if not conflicts else "INCOMPLETE","source_rows":len(base),"resolved_pdf_rows":len(resolved),
  "repaired_rows":sum(r["repair_status"]=="REPAIRED_VERIFIED" for r in repaired),"unmatched_rows":unmatched,"conflicts":conflicts,
  "rules":{"overwrite_valid_html":False,"minimum_pdf_votes":2,"join_key":["race_date","course","meeting_no","meeting_day","race_no","horse_name"]}}
 a.audit.parent.mkdir(parents=True,exist_ok=True);a.audit.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":main()
