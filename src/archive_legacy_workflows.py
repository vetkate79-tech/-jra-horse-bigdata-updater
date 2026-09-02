#!/usr/bin/env python3
from pathlib import Path
import json,shutil

ACTIVE=Path('.github/workflows')
ARCH=Path('.github/workflow-archive')
ARCH.mkdir(parents=True,exist_ok=True)

NAMES=[
'audit-golden-class-shortlist.yml','audit-oral-golden-v4.yml','audit-oral-system-parity.yml','audit-site-terms.yml',
'backfill-2025-html.yml','build-active-elite-catalog.yml','build-audit-oral-rich-v2.yml','build-blind-replay-20260829-30.yml',
'build-lightweight-horse-master.yml','build-oral-role-ticket-v5.yml','build-oral-role-ticket-v6.yml','build-pretarget-class-cache-72.yml',
'build-pretarget-class-shortlist-72.yml','build-pretarget-corner-cache.yml','build-pretarget-feature-cache-72.yml','build-public-horse-catalog.yml',
'build-replay-axis-results.yml','build-v8-improvement-diagnostic.yml','calibrate-replay-v03.yml','calibrate-replay-v04.yml','calibrate-replay-v05.yml',
'diagnose-full-field-roles-v5.yml','diagnose-golden-anchor-features.yml','diagnose-golden-running-styles.yml','diagnose-jra-corner-result-page.yml',
'diagnose-oral-profile-fields.yml','diagnose-profile-race-links.yml','diagnose-v10-failures.yml','diagnose-v12-current-class.yml',
'diagnose-v12-trio-failures.yml','diagnose-v12-v6-disagreement.yml','diagnose-v9-failures.yml','evaluate-v8-improvement.yml',
'inspect-2025-rolling-validation.yml','inspect-target-race-class.yml','merge-full-replay-archive.yml','oral-integrated-shadow-v1.yml',
'refresh-horse-categories.yml','rescore-publish-aug-replay.yml','rolling-validate-axis-2025.yml','run-oral-golden-fast-v2.yml',
'run-oral-golden-fast-v3.yml','run-oral-golden-fast-v4.yml','run-oral-v6-72-sealed-replay.yml','run-oral-v7-72-style-sealed-replay.yml',
'run-oral-v8-72-fullstyle.yml','run-oral-v9-72-confidence-style.yml','run-oral-v10-72-connected-durability.yml','run-oral-v11-holdout-gate.yml',
'run-oral-v12-rank-consensus.yml','run-v13-anchor-consensus.yml','select-v9-plan.yml','test-active-elite-parser.yml','update-jra-data.yml'
]

def main():
    moved=[];missing=[]
    for name in NAMES:
        src=ACTIVE/name
        if not src.exists():
            missing.append(name);continue
        dst=ARCH/name
        if dst.exists():dst.unlink()
        shutil.move(str(src),str(dst));moved.append(name)
    report={'moved_count':len(moved),'moved':moved,'not_present':missing,'policy':'Historical experiments are preserved but cannot trigger GitHub Actions from .github/workflow-archive.'}
    Path('status/workflow_cleanup.json').parent.mkdir(exist_ok=True)
    Path('status/workflow_cleanup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
