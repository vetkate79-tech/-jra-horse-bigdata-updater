#!/usr/bin/env python3
from pathlib import Path
import json

SRC=Path("docs/data/live_predictions_sealed.json")
OUT=Path("docs/analysis/live-seal.js")

def main():
    data=json.loads(SRC.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(data,ensure_ascii=False,separators=(",",":"))
    OUT.write_text("window.__JRA_LIVE_SEAL__="+payload+";\n",encoding="utf-8")
    print(json.dumps({
        "status":"PASS",
        "output":str(OUT),
        "race_count":len(data.get("races") or []),
        "pending_count":len(data.get("pending") or []),
        "generated_at":data.get("generated_at")
    },ensure_ascii=False))

if __name__=="__main__":
    main()
