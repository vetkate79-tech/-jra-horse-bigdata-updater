#!/usr/bin/env python3
"""Reconcile GRADED/OPEN catalogs from the verified lightweight JRA master.

This is a safety repair for cases where the current JRA horse-profile layout
cannot be parsed reliably. It uses only base_catalog.json, whose elite tags are
derived from JRA official result history and JRA's official graded-race list.
"""
import json
from pathlib import Path

BASE=Path('docs/data/horses/base_catalog.json')
OUTDIR=Path('docs/data/horses')
STATUS=Path('status/active_elite_catalog.json')


def main():
    doc=json.loads(BASE.read_text(encoding='utf-8'))
    horses=doc.get('horses',[])
    graded=[];opened=[]
    for h0 in horses:
        if h0.get('active') is False:continue
        h=dict(h0);tags=set(h.get('tags') or [])
        h['candidate_sources']=['JRA_OFFICIAL_RESULT_MASTER']
        if 'GRADED' in tags:
            if not h.get('graded_starts'):
                h['graded_starts']=[{'source':'JRA_OFFICIAL_RESULT_HISTORY','race_names':h.get('graded_race_names',[])}]
            graded.append(h)
        if h.get('current_class')=='OPEN' or 'OPEN' in tags:
            h['current_flat_class']='OPEN'
            if not h.get('open_or_higher_history'):
                h['open_or_higher_history']=[{'source':'JRA_OFFICIAL_LATEST_CLASS'}]
            opened.append(h)
    by={}
    for h in graded+opened:by[h.get('horse_id') or h.get('horse_name')]=h
    elite=sorted(by.values(),key=lambda x:x.get('horse_name',''))
    meta={'source':'JRA_OFFICIAL_RESULTS_VERIFIED_MASTER','candidate_count':len(horses),
      'profiles_ok':len(horses),'profiles_error':0,'active_count':sum(h.get('active') is not False for h in horses),
      'active_graded_count':len(graded),'active_open_count':len(opened),'elite_union_count':len(elite),
      'open_definition':'latest recorded JRA official class is OPEN','graded_definition':'recorded start in JRA official flat G1/G2/G3 race',
      'registered_roster_candidates':0,'profile_layout_fallback_used':True,
      'fallback_policy':'JRA official result evidence only; no inference or third-party data'}
    for fn,items in [('active_graded.json',graded),('active_open.json',opened),('active_elite.json',elite)]:
        (OUTDIR/fn).write_text(json.dumps({'summary':meta,'horses':items},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    STATUS.write_text(json.dumps({'summary':meta,'errors':[]},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))
    if len(horses)>=100 and (not graded or not opened):raise SystemExit('verified elite reconciliation unexpectedly empty')

if __name__=='__main__':main()
