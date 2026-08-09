#!/usr/bin/env python3
"""Audit every prerequisite before any operational backtest is allowed to run."""
import csv, json, re
from collections import Counter
from pathlib import Path

CONFIG = Path("config/validation_prerequisites.json")
OUT = Path("status/validation_prerequisite_audit.json")
MANIFEST = Path("data/validation_input_manifest.json")

def inspect_csv(path, required):
    result = {"path": str(path), "exists": path.exists(), "rows": 0, "columns": [], "missing_columns": [], "duplicate_rows": 0}
    if not path.exists():
        result["status"] = "MISSING"
        return result
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        result["columns"] = reader.fieldnames or []
        result["missing_columns"] = sorted(set(required) - set(result["columns"]))
        seen = set()
        for row in reader:
            result["rows"] += 1
            fingerprint = tuple(row.get(c, "") for c in result["columns"])
            result["duplicate_rows"] += fingerprint in seen
            seen.add(fingerprint)
    result["status"] = "PASS" if result["rows"] and not result["missing_columns"] and not result["duplicate_rows"] else "INCOMPLETE"
    return result

def semantic_race_audit(path, gates):
    out = {"rows": 0, "races": 0, "bad_race_name_rows": 0, "missing_values": {}, "invalid_values": {},
           "special_finish_rows": 0, "missing_time_rows": 0, "missing_last3f_rows": 0,
           "missing_popularity_rows": 0, "missing_body_weight_rows": 0, "duplicate_runner_keys": 0}
    if not path.exists(): return out
    required_values = ["race_id", "race_date", "horse_id", "horse_name", "horse_no", "finish_position", "surface", "distance_m"]
    missing = Counter(); invalid = Counter(); races=set(); keys=set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out["rows"] += 1; races.add(r.get("race_id", ""))
            for c in required_values:
                if not str(r.get(c, "")).strip(): missing[c] += 1
            if r.get("race_name", "").strip() in gates["forbidden_race_names"]: out["bad_race_name_rows"] += 1
            if not re.fullmatch(r"\d+(?:\.0)?", r.get("finish_position", "")): out["special_finish_rows"] += 1
            if not r.get("time", "").strip(): out["missing_time_rows"] += 1
            if not r.get("last3f", "").strip(): out["missing_last3f_rows"] += 1
            if not r.get("popularity", "").strip(): out["missing_popularity_rows"] += 1
            if not r.get("body_weight_delta", "").strip(): out["missing_body_weight_rows"] += 1
            if r.get("surface") not in gates["allowed_surfaces"]: invalid["surface"] += 1
            try:
                d=int(float(r.get("distance_m", "")))
                if not gates["min_distance_m"] <= d <= gates["max_distance_m"]: invalid["distance_m"] += 1
            except ValueError: invalid["distance_m"] += 1
            key=(r.get("race_id"),r.get("horse_id"))
            if key in keys: out["duplicate_runner_keys"] += 1
            keys.add(key)
    out["races"] = len(races); out["missing_values"] = dict(missing); out["invalid_values"] = dict(invalid)
    out["status"] = "PASS" if not out["bad_race_name_rows"] and not missing and not invalid and not out["duplicate_runner_keys"] else "INCOMPLETE"
    return out

def main():
    cfg=json.loads(CONFIG.read_text(encoding="utf-8")); sources={}
    for name,spec in cfg["required_sources"].items():
        sources[name]=inspect_csv(Path(spec["path"]),spec["required_columns"])
    semantic=semantic_race_audit(Path(cfg["required_sources"]["race_results"]["path"]),cfg["semantic_gates"])
    blocking=[name for name,x in sources.items() if x["status"]!="PASS" and cfg["required_sources"][name].get("blocking",True)]
    if semantic.get("status")!="PASS": blocking.append("race_results_semantics")
    audit={"schema_version":1,"status":"READY" if not blocking else "BLOCKED","blocking_prerequisites":blocking,
           "sources":sources,"race_results_semantics":semantic,
           "next_action":"build_validation_dataset" if not blocking else "collect_or_repair_blocking_sources"}
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest={"schema_version":1,"ready_for_validation":not blocking,"approved_inputs":[x["path"] for x in sources.values() if x["status"]=="PASS"],
              "blocked_inputs":[x["path"] for x in sources.values() if x["status"]!="PASS"],"quality_report":str(OUT)}
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False))

if __name__=="__main__": main()
