#!/usr/bin/env python3
from pathlib import Path
import json

DIAG=Path('status/oral-v8-improvement-diagnostic.json')
OUT=Path('status/oral-v9-selection-plan.json')

def main():
    if not DIAG.exists():
        print('V8 diagnostic not ready');return
    d=json.loads(DIAG.read_text())
    plan={
      'source':'V8 change diagnostic only',
      'rule':'Do not tune on individual race identities. Prefer general role-selection changes only when they create hits without losing prior hits and preserve golden-case parity.',
      'changed_races':d.get('changed_races'),
      'new_hits':d.get('new_hits'),
      'lost_hits':d.get('lost_hits'),
      'candidate_action':'KEEP_V8_ROLE_DIVERSITY' if d.get('new_hits',0)>d.get('lost_hits',0) else 'REJECT_OR_REVISE_V8_ROLE_DIVERSITY'
    }
    OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(plan,ensure_ascii=False,indent=2));print(json.dumps(plan,ensure_ascii=False))
if __name__=='__main__':main()
