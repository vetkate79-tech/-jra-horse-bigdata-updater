#!/usr/bin/env python3
import json
from pathlib import Path
OLD=Path('docs/data/replay-demo-2026-08-29-30.json')
FULL=Path('docs/data/replay-2026-08-29-30-full.json')

def main():
    old=json.loads(OLD.read_text(encoding='utf-8')) if OLD.exists() else {'races':[]}
    full=json.loads(FULL.read_text(encoding='utf-8'))
    by={}
    for r in old.get('races',[]):
        by[(r.get('date'),r.get('track'),int(r.get('race_no') or 0))]=r
    for r in full.get('races',[]):
        by[(r.get('date'),r.get('track'),int(r.get('race_no') or 0))]=r
    races=sorted(by.values(),key=lambda r:(r.get('date',''),r.get('track',''),int(r.get('race_no') or 0)))
    out={
      'mode':'PRE_RACE_ARCHIVE_WITH_BLIND_RECONSTRUCTION',
      'excluded_from_official_metrics':True,
      'note':'実際の発走前会話ログが残るレースはその記録を使用。それ以外の2026-08-29/30は、結果・人気・オッズを予想入力から遮断した再現予想。再現分を当時の実予想として扱わない。',
      'dates':sorted({r.get('date') for r in races if r.get('date')}),
      'replay_evaluation_summary':full.get('evaluation_summary',{}),
      'prediction_hash_sha256':full.get('prediction_hash_sha256'),
      'races':races,
    }
    OLD.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    target=[r for r in races if r.get('date') in ('2026-08-29','2026-08-30')]
    assert len(target)==72, len(target)
    print(json.dumps({'archive_races':len(races),'target_72':len(target),'summary':out['replay_evaluation_summary']},ensure_ascii=False))
if __name__=='__main__':main()
