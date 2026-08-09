#!/usr/bin/env python3
"""Checkpointed end-to-end PDF repair pipeline for all JRA result sheets."""
import argparse,json,subprocess,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path

def load(path,default):return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
def atomic(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(".tmp")
 tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8");tmp.replace(path)

def resolve_one(pdf,resolved_dir):
 report=resolved_dir/(pdf.stem+"_resolution.json")
 if report.exists():return pdf.name,load(report,{"status":"BROKEN_CHECKPOINT"}),"CACHED"
 p=subprocess.run([sys.executable,"src/resolve_quarantine.py",str(pdf),str(resolved_dir)],text=True,capture_output=True)
 if p.returncode:return pdf.name,{"error":p.stderr[-2000:] or p.stdout[-2000:]},"FAILED"
 return pdf.name,load(report,{}),"DONE"

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--pdf-dir",type=Path,required=True);ap.add_argument("--html",type=Path,required=True)
 ap.add_argument("--work-dir",type=Path,default=Path("work/pdf_repair"));ap.add_argument("--out",type=Path,required=True)
 ap.add_argument("--audit",type=Path,required=True);ap.add_argument("--workers",type=int,default=2);ap.add_argument("--limit",type=int)
 a=ap.parse_args();resolved=a.work_dir/"resolved";resolved.mkdir(parents=True,exist_ok=True)
 pdfs=sorted(a.pdf_dir.glob("*.pdf"));pdfs=pdfs[:a.limit] if a.limit else pdfs
 state_path=a.work_dir/"pipeline_state.json";state=load(state_path,{"schema_version":1,"files":{}})
 with ThreadPoolExecutor(max_workers=max(1,a.workers)) as ex:
  futures={ex.submit(resolve_one,p,resolved):p for p in pdfs}
  for f in as_completed(futures):
   name,report,status=f.result();state["files"][name]={"status":status,"resolved_rows":report.get("resolved_rows",0),
      "unresolved_races":len(report.get("unresolved_races",[])),"error":report.get("error")}
   state["updated_at"]=datetime.now(timezone.utc).isoformat();atomic(state_path,state)
 subprocess.run([sys.executable,"src/repair_html_with_pdf_consensus.py","--html",str(a.html),"--resolved-dir",str(resolved),
   "--out",str(a.out),"--audit",str(a.audit)],check=True)
 final=load(a.audit,{});final["pdf_inventory"]=len(pdfs);final["pdf_completed"]=sum(x["status"] in ("DONE","CACHED") for x in state["files"].values())
 final["pdf_failed"]=sum(x["status"]=="FAILED" for x in state["files"].values());atomic(a.audit,final)
 if final["pdf_failed"]:raise SystemExit("one or more PDFs failed; checkpoint retained")

if __name__=="__main__":main()
