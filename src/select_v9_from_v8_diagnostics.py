#!/usr/bin/env python3
from pathlib import Path
import json

DIAG=Path('status/oral-v8-improvement-diagnostic.json')
OUT=Path('status/oral-v9-selection-plan.json')

def main():
    OUT.parent.mkdir(exist_ok=True)
    if not DIAG.exists():
        plan={
          'status':'WAITING_FOR_V8_DIAGNOSTIC',
          'source':'V8 change diagnostic only',
          'candidate_action':'WAIT',
          'rule':'Do not advance V9 until the V8 diagnostic exists. Missing upstream data is a normal waiting state, not a workflow error.'
        }
        OUT.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
        print(json.dumps(plan,ensure_ascii=False));return
    d=json.loads(DIAG.read_text())
    new_hits=int(d.get('new_hits',0) or 0);lost_hits=int(d.get('lost_hits',0) or 0)
    plan={
      'status':'READY',
      'source':'V8 change diagnostic only',
      'rule':'Do not tune on individual race identities. Prefer general role-selection changes only when they create hits without losing prior hits and preserve golden-case parity.',
      'changed_races':d.get('changed_races'),
      'new_hits':new_hits,
      'lost_hits':lost_hits,
      'new_hit_races':d.get('new_hit_races',[]),
      'lost_hit_races':d.get('lost_hit_races',[]),
      'candidate_action':'KEEP_V8_ROLE_DIVERSITY' if new_hits>lost_hits else 'REJECT_OR_REVISE_V8_ROLE_DIVERSITY'
    }
    OUT.write_text(json.dumps(plan,ensure_ascii=False,indent=2));print(json.dumps(plan,ensure_ascii=False))
if __name__=='__main__':main()
