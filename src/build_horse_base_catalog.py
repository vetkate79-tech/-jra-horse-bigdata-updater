#!/usr/bin/env python3
"""Build the lightweight public horse master from the internal catalog.

The internal catalog remains lossless for validation/backfill. The public base
catalog intentionally contains only stable identity/profile fields. Race-week
analytics live in weekly_runner_details.json instead.
"""
import json
from pathlib import Path

SRC=Path('docs/data/horses/catalog.json')
OUT=Path('docs/data/horses/base_catalog.json')

BASE_FIELDS=(
    'horse_name','horse_id','sex_age','trainer','sire','damsire',
    'current_class','current_class_label','active','latest_race_date','latest_finish',
    'unbeaten','wins'
)
KEEP_TAGS={'GRADED','OPEN','NEW','NEW_ENTRY'}

def compact(h):
    x={k:h.get(k) for k in BASE_FIELDS if h.get(k) not in (None,'')}
    tags=[t for t in (h.get('tags') or []) if t in KEEP_TAGS]
    if tags:x['tags']=sorted(set(tags))
    is_new=(h.get('current_class')=='NEW' or 'NEW' in tags or 'NEW_ENTRY' in tags)
    if is_new:
        p=h.get('pedigree_summary') or {}
        pedigree={k:p.get(k) for k in ('sire','damsire','dam') if p.get(k)}
        if pedigree:x['pedigree_summary']=pedigree
        if h.get('training_summary'):x['training_summary']=h['training_summary']
    return x

def main():
    doc=json.loads(SRC.read_text(encoding='utf-8')) if SRC.exists() else {'summary':{},'horses':[]}
    horses=[compact(h) for h in doc.get('horses',[]) if h.get('horse_id') and h.get('horse_name')]
    horses.sort(key=lambda h:h.get('horse_name',''))
    summary={
        'horse_count':len(horses),
        'source':'INTERNAL_HORSE_CATALOG',
        'mode':'LIGHTWEIGHT_BASE_MASTER',
        'detail_policy':'expand only horses on verified upcoming JRA racecards',
        'new_horse_policy':'keep light pedigree/training memo before debut',
        'ui_fields':['horse_name','sex_age','trainer','sire','damsire','current_class','active','latest_race_date','latest_finish']
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'summary':summary,'horses':horses},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
