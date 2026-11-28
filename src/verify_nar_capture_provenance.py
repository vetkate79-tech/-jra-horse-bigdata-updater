#!/usr/bin/env python3
"""Fail-closed cross-check of raw capture and parsed card provenance.

Never interpret a post-start capture as a pre-start sealed prediction.
"""
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path

def verify(raw_path,audit_path,parsed_path,expected_race_id,expected_count):
    raw=Path(raw_path).read_bytes()
    audit=json.loads(Path(audit_path).read_text(encoding="utf-8"))
    parsed=json.loads(Path(parsed_path).read_text(encoding="utf-8"))
    expected_url="https://keiba.rakuten.co.jp/race_card/list/RACEID/"+expected_race_id
    if audit.get("source_url")!=expected_url:raise ValueError("wrong race source URL")
    if hashlib.sha256(raw).hexdigest()!=audit.get("sha256"):raise ValueError("raw evidence SHA mismatch")
    if len(raw)!=audit.get("bytes"):raise ValueError("raw evidence byte length mismatch")
    names=audit.get("found_runners")
    horses=parsed.get("horses")
    if not isinstance(horses,list) or not isinstance(names,list):raise ValueError("missing runner lists")
    if len(horses)!=expected_count or len(names)!=expected_count or audit.get("found_count")!=expected_count:
        raise ValueError("runner count mismatch")
    if [h.get("horse_name") for h in horses]!=names:raise ValueError("parsed runners differ from captured card")
    ids=[h.get("horse_id") for h in horses]
    if any(not x for x in ids) or len(set(ids))!=len(ids):raise ValueError("horse identifiers missing/duplicated")
    captured=datetime.fromisoformat(audit["retrieved_at"])
    if captured.tzinfo is None:raise ValueError("capture timestamp lacks timezone")
    target_date=datetime.strptime(expected_race_id[:8],"%Y%m%d").date()
    if captured.astimezone(timezone.utc).date()<target_date:
        raise ValueError("unexpected historical capture timestamp")
    if parsed.get("status")!="UNSEALED_RESEARCH_ONLY" or audit.get("status")!="RAW_EVIDENCE_ONLY_NOT_PRE_RACE_SEALED":
        raise ValueError("provenance status mismatch")
    return {"status":"PASS_RAW_TO_PARSED_IDENTITY_RESEARCH_ONLY","race_id":expected_race_id,"runners":expected_count,"sha256":audit["sha256"],"pre_start_seal":"NOT_VERIFIED"}

if __name__=="__main__":
    if len(sys.argv)!=6:raise SystemExit("usage: verify_nar_capture_provenance.py raw.html capture.json parsed.json race_id count")
    print(json.dumps(verify(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5])),ensure_ascii=False))
