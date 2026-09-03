#!/usr/bin/env python3
"""Fail closed when horse-master or race-week identity duplicates exist.

Identity policy:
- persistent horse master primary key = canonical JRA horse_id
- accessD pw01dud00... and profile/history pw01dud10... are the same canonical id
- race-week runner uniqueness = (race_id, canonical horse_id)
- pre-race feature uniqueness = (race_id, canonical horse_id)
- per-horse upcoming starts uniqueness = race_id

We intentionally do not merge records by horse name: names are useful for recovery/search,
but are not a safe primary key for persistent identity.
"""
from __future__ import annotations
import json,re,sys
from collections import Counter
from pathlib import Path

CAT=Path('docs/data/horses/catalog.json')
BASE=Path('docs/data/horses/base_catalog.json')
WEEKLY=Path('docs/data/horses/weekly_runner_details.json')
PRE=Path('docs/data/horses/pre_race_features.json')
STATUS=Path('status/horse_identity_uniqueness.json')
ID_RE=re.compile(r'^pw01dud(?:00|10)\d{12}/[A-Fa-f0-9]{2}$')

def canon(v):
    s=str(v or '').strip()
    if s.startswith('pw01dud00'):s='pw01dud10'+s[len('pw01dud00'):]
    return s.upper()

def load(path,default):
    if not path.exists() or path.stat().st_size==0:return default
    return json.loads(path.read_text(encoding='utf-8'))

def dup_values(values):
    c=Counter(x for x in values if x)
    return sorted(k for k,v in c.items() if v>1)

def main():
    problems=[];report={}
    for label,path in (('catalog',CAT),('base_catalog',BASE)):
        d=load(path,{'horses':[]});horses=d.get('horses') or []
        ids=[canon(h.get('horse_id')) for h in horses]
        duplicates=dup_values(ids)
        malformed=sorted({str(h.get('horse_id') or '') for h in horses if h.get('horse_id') and not ID_RE.match(str(h.get('horse_id')).strip())})
        start_dups=[]
        for h in horses:
            rid=[str(x.get('race_id') or '') for x in (h.get('upcoming_starts') or []) if isinstance(x,dict)]
            ds=dup_values(rid)
            if ds:start_dups.append({'horse_id':canon(h.get('horse_id')),'race_ids':ds})
        report[label]={'horse_count':len(horses),'duplicate_horse_id_count':len(duplicates),'duplicate_horse_ids':duplicates[:100],'malformed_horse_id_count':len(malformed),'malformed_horse_ids':malformed[:100],'duplicate_upcoming_start_horse_count':len(start_dups),'duplicate_upcoming_starts':start_dups[:100]}
        if duplicates:problems.append(f'{label}: duplicate canonical horse_id={len(duplicates)}')
        if start_dups:problems.append(f'{label}: duplicate upcoming_starts={len(start_dups)} horses')
    weekly=load(WEEKLY,{'runners':[]});runners=weekly.get('runners') or []
    wk=[]
    for x in runners:
        race=x.get('race') or {};wk.append((str(race.get('race_id') or ''),canon(x.get('horse_id'))))
    wk_dups=dup_values(['|'.join(x) for x in wk if all(x)])
    report['weekly']={'runner_count':len(runners),'duplicate_race_horse_count':len(wk_dups),'duplicate_race_horses':wk_dups[:100]}
    if wk_dups:problems.append(f'weekly: duplicate race_id+horse_id={len(wk_dups)}')
    pre=load(PRE,{'features':[]});features=pre.get('features') or []
    pf=[(str(x.get('race_id') or ''),canon(x.get('horse_id'))) for x in features]
    pf_dups=dup_values(['|'.join(x) for x in pf if all(x)])
    report['pre_race_features']={'feature_count':len(features),'duplicate_race_horse_count':len(pf_dups),'duplicate_race_horses':pf_dups[:100]}
    if pf_dups:problems.append(f'pre_race_features: duplicate race_id+horse_id={len(pf_dups)}')
    report['status']='FAIL' if problems else 'PASS';report['problems']=problems;report['identity_policy']='CANONICAL_JRA_HORSE_ID_ONLY_NO_NAME_BASED_PERSISTENT_MERGE'
    STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if problems:sys.exit(1)

if __name__=='__main__':main()
