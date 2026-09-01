#!/usr/bin/env python3
"""Enrich horses marked NEW_ENTRY/NEW with light pedigree and training notes.

Pedigree comes from JRA horse profile when a horse_id exists.
Training notes are only attached from a verified optional JSON input; nothing is inferred.
"""
import json
from pathlib import Path
import sys
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile,parse_profile

BASE=Path('docs/data/horses')
CAT=BASE/'catalog.json'
TRAIN=Path('data/new_horse_training.json')

def load(path,default):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding='utf-8'))

def main():
    doc=load(CAT,{'summary':{},'horses':[]})
    training=load(TRAIN,{'horses':[]})
    by_id={x.get('horse_id'):x for x in training.get('horses',[]) if x.get('horse_id')}
    by_name={x.get('horse_name'):x for x in training.get('horses',[]) if x.get('horse_name')}
    touched=0;errors=[]
    for h in doc.get('horses',[]):
        tags=set(h.get('tags') or [])
        if h.get('current_class')!='NEW' and 'NEW_ENTRY' not in tags and 'NEW' not in tags: continue
        hid=h.get('horse_id')
        if hid:
            try:
                p=parse_profile({'horse_id':hid,'horse_name':h.get('horse_name',''),'candidate_sources':{'NEW_ENTRY'}},request_profile(hid))
                h['pedigree_summary']={
                    'sire':p.get('sire') or None,
                    'damsire':p.get('damsire') or None,
                    'dam':p.get('dam') or None
                }
                for k in ('birth_date','breeder','trainer','owner','coat'):
                    if p.get(k): h[k]=p[k]
            except Exception as e: errors.append({'horse_id':hid,'horse_name':h.get('horse_name'),'error':repr(e)})
        t=by_id.get(hid) or by_name.get(h.get('horse_name'))
        if t:
            h['training_summary']={
                'note':t.get('note') or '',
                'source':t.get('source') or '',
                'updated_at':t.get('updated_at') or '',
                'verified':bool(t.get('verified'))
            }
        elif 'training_summary' not in h:
            h['training_summary']=None
        touched+=1
    s=dict(doc.get('summary') or {})
    s['new_horse_enriched_count']=touched
    s['new_horse_training_policy']='display verified training notes only; do not infer or fabricate'
    s['new_horse_profile_policy']='register before debut when upcoming JRA entry is available; pedigree from JRA horse profile'
    doc['summary']=s
    CAT.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'new_horse_enriched_count':touched,'errors':len(errors)},ensure_ascii=False))
    if errors: print(json.dumps(errors[:20],ensure_ascii=False,indent=2))
if __name__=='__main__': main()
