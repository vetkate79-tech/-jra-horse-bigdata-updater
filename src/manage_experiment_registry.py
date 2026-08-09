#!/usr/bin/env python3
"""Store immutable validation runs separately from model-improvement decisions."""
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path("experiments"); RUNS=ROOT/"runs"; IMPROVEMENTS=ROOT/"improvements"; INDEX=ROOT/"index.json"

def load(path,default): return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8");tmp.replace(path)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--summary",required=True);ap.add_argument("--model-version",required=True)
    ap.add_argument("--parent-run");ap.add_argument("--change-note",default="baseline evaluation; no model change")
    a=ap.parse_args(); summary=load(Path(a.summary),{})
    now=datetime.now(timezone.utc).isoformat(); payload={"created_at":now,"model_version":a.model_version,"parent_run":a.parent_run,
      "input_manifest":"data/validation_input_manifest.json","summary":summary}
    run_id=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:16];payload["run_id"]=run_id
    run_path=RUNS/f"{run_id}.json"
    if run_path.exists(): raise SystemExit("immutable run already exists: "+run_id)
    atomic(run_path,payload)
    improvement={"run_id":run_id,"parent_run":a.parent_run,"model_version":a.model_version,"change_note":a.change_note,
                 "decision":"PENDING_REVIEW","created_at":now}
    atomic(IMPROVEMENTS/f"{run_id}.json",improvement)
    index=load(INDEX,{"schema_version":1,"runs":[]});index["runs"].append({"run_id":run_id,"model_version":a.model_version,"created_at":now,"status":summary.get("status","UNKNOWN")})
    atomic(INDEX,index);print(json.dumps({"run_id":run_id,"run":str(run_path),"improvement":str(IMPROVEMENTS/f'{run_id}.json')},ensure_ascii=False))

if __name__=="__main__":main()
