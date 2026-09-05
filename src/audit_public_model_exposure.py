#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PUBLIC_ROOT = Path("docs")
STATUS = Path("status/public_model_exposure_audit.json")

# Files that belong to the prediction engine and must never be published by GitHub Pages.
FORBIDDEN_BASENAMES = {
    "oral_operational_layer.py",
    "build_live_sealed_predictions.py",
    "score_live_sealed_predictions.py",
    "build_live_pdca.py",
    "build_management_erp.py",
}
FORBIDDEN_SUFFIXES = {".py", ".pyc", ".pyo", ".pyd", ".so", ".map"}

# Distinct implementation markers. Public result JSON may contain model names or hashes,
# but it must not contain executable implementation text.
FORBIDDEN_CODE_MARKERS = (
    "def analyze_race(",
    "def build_live",
    "class Oral",
    "FORBIDDEN_KEYS",
    "ability_rank(",
)

def main():
    violations=[]
    if not PUBLIC_ROOT.exists():
        violations.append("public root docs/ is missing")
    else:
        for p in PUBLIC_ROOT.rglob("*"):
            if not p.is_file():
                continue
            rel=str(p.relative_to(PUBLIC_ROOT))
            if p.name in FORBIDDEN_BASENAMES:
                violations.append(f"forbidden model source file: {rel}")
            if p.suffix.lower() in FORBIDDEN_SUFFIXES:
                violations.append(f"forbidden executable/source artifact: {rel}")
            # Only inspect text-like assets to avoid false binary handling.
            if p.suffix.lower() in {".html",".js",".json",".txt",".md",".css"}:
                try:
                    txt=p.read_text(encoding="utf-8")
                except Exception:
                    continue
                for marker in FORBIDDEN_CODE_MARKERS:
                    if marker in txt:
                        violations.append(f"model implementation marker {marker!r}: {rel}")
    report={
        "status":"PASS" if not violations else "BLOCKED",
        "public_root":"docs",
        "model_source_served_by_pages":False if not violations else None,
        "violations":violations,
        "rule":"Prediction model implementation must never be included in GitHub Pages artifacts. Public outputs may contain predictions/results only.",
    }
    STATUS.parent.mkdir(parents=True,exist_ok=True)
    STATUS.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if violations:
        raise SystemExit(2)

if __name__=="__main__":
    main()
