#!/usr/bin/env python3
import json
from pathlib import Path

BASE=Path('docs/data/horses')
CATALOG=BASE/'catalog.json'
ELITE=BASE/'active_elite.json'
OUT=CATALOG


def load(path,default):
    if not path.exists():return default
    return json.loads(path.read_text(encoding='utf-8'))


def merge_one(base,elite):
    # Preserve weekend/result-derived metrics, overlay authoritative current JRA profile fields.
    base=dict(base or {})
    profile_map={
      'horse_name':'horse_name','horse_id':'horse_id','active':'active','deregistered_at':'deregistered_at',
      'sex':'sex','age':'age','trainer':'trainer','owner':'owner','sire':'sire','dam':'dam','damsire':'damsire',
      'birth_date':'birth_date','breeder':'breeder','coat':'coat','birthplace':'birthplace',
      'flat_acquired_prize_yen':'flat_acquired_prize_yen','obstacle_acquired_prize_yen':'obstacle_acquired_prize_yen',
      'profile_url':'profile_url','profile_race_rows':'profile_race_rows'
    }
    for src,dst in profile_map.items():
        v=elite.get(src)
        if v not in (None,''):base[dst]=v
    if elite.get('sex') or elite.get('age'):
        base['sex_age']=''.join(str(x) for x in (elite.get('sex',''),elite.get('age','')) if x)
    if elite.get('graded_starts'):
        base['graded_starts']=elite['graded_starts']
        base['graded_experience']=elite.get('graded_experience',[])
    base['open_or_higher_history']=elite.get('open_or_higher_history',base.get('open_or_higher_history',[]))
    tags=set(base.get('tags') or [])
    if elite.get('graded_starts'):tags.add('GRADED')
    if elite.get('current_flat_class')=='OPEN':
        tags.add('OPEN');base['current_class']='OPEN';base['current_class_label']='オープンクラス'
    base['tags']=sorted(tags)
    return base


def main():
    cat=load(CATALOG,{'summary':{},'horses':[]})
    elite_doc=load(ELITE,{'summary':{},'horses':[]})
    by_id={}
    by_name={}
    for h in cat.get('horses',[]):
        if h.get('horse_id'):by_id[h['horse_id']]=h
        if h.get('horse_name'):by_name[h['horse_name']]=h
    added=0;updated=0
    for e in elite_doc.get('horses',[]):
        base=by_id.get(e.get('horse_id')) or by_name.get(e.get('horse_name'))
        if base is None:
            base={'horse_name':e.get('horse_name',''),'horse_id':e.get('horse_id',''),'target_starts':[],
                  'win_rate':None,'quinella_rate':None,'show_rate':None,'tags':[]}
            cat['horses'].append(base);added+=1
        else:updated+=1
        merged=merge_one(base,e)
        base.clear();base.update(merged)
        if base.get('horse_id'):by_id[base['horse_id']]=base
        if base.get('horse_name'):by_name[base['horse_name']]=base
    cat['horses'].sort(key=lambda x:x.get('horse_name',''))
    summary=dict(cat.get('summary') or {})
    summary.update({
      'unified_horse_count':len(cat['horses']),
      'active_graded_count':sum(bool(h.get('active') and h.get('graded_starts')) for h in cat['horses']),
      'active_open_count':sum(bool(h.get('active') and h.get('current_class')=='OPEN') for h in cat['horses']),
      'elite_added_to_weekend_master':added,'elite_updated_in_weekend_master':updated,
      'elite_source_summary':elite_doc.get('summary',{}),
      'master_policy':'horse_id primary; JRA current profile overlays race-result history'
    })
    cat['summary']=summary
    OUT.write_text(json.dumps(cat,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('unified_horse_count','active_graded_count','active_open_count','elite_added_to_weekend_master','elite_updated_in_weekend_master')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
