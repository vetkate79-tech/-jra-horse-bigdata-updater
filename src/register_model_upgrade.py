#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LOG=Path("docs/data/model_upgrade_log.json")
TZ=ZoneInfo("Asia/Tokyo")
REQUIRED={
  "from_model","to_model","reason_for_change","validation_path","change_summary",
  "promotion_gate","comparison_at_promotion"
}

def load(path,default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(path)

def main():
    ap=argparse.ArgumentParser(description="Register a complete production model upgrade with evidence.")
    ap.add_argument("--manifest",required=True,help="JSON file containing the promotion evidence")
    a=ap.parse_args()
    m=load(Path(a.manifest),{})
    missing=sorted(k for k in REQUIRED if not m.get(k))
    if missing:
        raise SystemExit("missing required upgrade evidence: "+",".join(missing))
    if m["from_model"]==m["to_model"]:
        raise SystemExit("from_model and to_model must differ for a complete upgrade")
    d=load(LOG,{"schema_version":1,"upgrades":[]})
    upgrades=d.setdefault("upgrades",[])
    if any(x.get("to_model")==m["to_model"] for x in upgrades):
        raise SystemExit("upgrade already registered for "+str(m["to_model"]))
    now=datetime.now(TZ).isoformat(timespec="seconds")
    payload={
      "promoted_at":m.get("promoted_at") or now,
      "from_model":m["from_model"],
      "to_model":m["to_model"],
      "reason_for_change":m["reason_for_change"],
      "validation_path":m["validation_path"],
      "change_summary":m["change_summary"],
      "promotion_gate":m["promotion_gate"],
      "comparison_at_promotion":m["comparison_at_promotion"],
      "post_upgrade_health":{
        "status":"AWAITING_LIVE_SAMPLE",
        "last_checked_at":None,
        "current_model_metrics":None,
        "vs_previous_model":None,
        "note":"実運用結果が接続されるたび管理ERP側で更新する"
      }
    }
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    payload["upgrade_id"]="UPG-"+hashlib.sha256(raw.encode()).hexdigest()[:12]
    upgrades.append(payload)
    atomic(LOG,d)
    print(json.dumps({"status":"REGISTERED","upgrade_id":payload["upgrade_id"],"to_model":payload["to_model"]},ensure_ascii=False))

if __name__=="__main__":
    main()
