#!/usr/bin/env python3
"""Enrich every discovered catalog horse from its JRA official horse profile.

This pass deliberately does not invent a class when JRA evidence is insufficient.
It fills authoritative active/deregistered state, pedigree/profile fields, flat
acquired prize, current flat class, graded/open history and NEW pedigree fields.
"""
from __future__ import annotations
import json,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile,parse_profile

CAT=Path('docs/data/horses/catalog.json')
STATUS=Path('status/all_catalog_profile_enrichment.json')
WORKERS=4
LABELS={'OPEN':'オープンクラス','3WIN':'3勝クラス','2WIN':'2勝クラス','1WIN':'1勝クラス'}


def main():
    doc=json.loads(CAT.read_text(encoding='utf-8'))
    horses=doc.get('horses',[])
    targets=[h for h in horses if h.get('horse_id')]
    by_id={h.get('horse_id'):h for h in targets}
    errors=[];ok=0

    def one(h):
        hid=h['horse_id']
        p=parse_profile({'horse_id':hid,'horse_name':h.get('horse_name',''),'candidate_sources':{'PUBLIC_CATALOG'}},request_profile(hid))
        return hid,p

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(one,h):h for h in targets}
        for fut in as_completed(futs):
            h=futs[fut]
            try:
                hid,p=fut.result();base=by_id[hid]
                for k in ('horse_name','active','deregistered_at','sex','age','trainer','owner','sire','dam','damsire','birth_date','breeder','coat','birthplace','flat_acquired_prize_yen','obstacle_acquired_prize_yen','profile_url','profile_race_rows'):
                    v=p.get(k)
                    if v not in (None,''): base[k]=v
                if p.get('sex') or p.get('age'):
                    base['sex_age']=''.join(str(x) for x in (p.get('sex',''),p.get('age','')) if x)
                if p.get('graded_starts'):
                    base['graded_starts']=p['graded_starts'];base['graded_experience']=p.get('graded_experience',[])
                    tags=set(base.get('tags') or []);tags.add('GRADED');base['tags']=sorted(tags)
                if p.get('open_or_higher_history'):
                    base['open_or_higher_history']=p['open_or_higher_history']
                flat_class=p.get('current_flat_class')
                if flat_class in LABELS:
                    base['current_class']=flat_class;base['current_class_label']=LABELS[flat_class]
                    base['class_source']='JRA_OFFICIAL_ACQUIRED_PRIZE'
                    tags=set(base.get('tags') or []);tags.add(flat_class);base['tags']=sorted(tags)
                if base.get('current_class')=='NEW' or 'NEW_ENTRY' in (base.get('tags') or []) or 'NEW' in (base.get('tags') or []):
                    base['pedigree_summary']={'sire':p.get('sire') or None,'damsire':p.get('damsire') or None,'dam':p.get('dam') or None}
                ok+=1
            except Exception as e:
                errors.append({'horse_id':h.get('horse_id'),'horse_name':h.get('horse_name'),'error':repr(e)})

    s=dict(doc.get('summary') or {})
    s['all_profile_enrichment_ok']=ok;s['all_profile_enrichment_errors']=len(errors)
    s['all_profile_enrichment_policy']='JRA official horse profile only; current flat class comes from official acquired prize thresholds; unresolved zero-prize state is resolved by verified race evidence'
    doc['summary']=s
    CAT.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    STATUS.parent.mkdir(exist_ok=True)
    STATUS.write_text(json.dumps({'summary':{'target_count':len(targets),'ok':ok,'errors':len(errors)},'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'target_count':len(targets),'ok':ok,'errors':len(errors)},ensure_ascii=False))
    if errors: raise SystemExit(f'profile enrichment incomplete: {len(errors)} errors')

if __name__=='__main__': main()
