#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

CAT=Path('docs/data/horses/catalog.json')
BASE=Path('docs/data/horses/base_catalog.json')
ELITE=Path('docs/data/horses/active_elite.json')
OUT=Path('status/horse_master_completion.json')
PRIORITY=('GRADED','OPEN','3WIN','2WIN','1WIN','MAIDEN','NEW')


def category(h):
    tags=set(h.get('tags') or [])
    cls=h.get('current_class') or ''
    if 'GRADED' in tags:return 'GRADED'
    if cls=='OPEN' or 'OPEN' in tags:return 'OPEN'
    if cls in PRIORITY:return cls
    return 'UNKNOWN'


def main():
    if not CAT.exists():raise SystemExit('catalog missing')
    doc=json.loads(CAT.read_text(encoding='utf-8'));horses=doc.get('horses',[])
    issues=[];missing=Counter();cats=Counter(category(h) for h in horses)
    for h in horses:
        name=h.get('horse_name') or '';hid=h.get('horse_id') or '';cls=h.get('current_class') or '';tags=set(h.get('tags') or []);miss=[]
        if not hid:miss.append('horse_id')
        if not name:miss.append('horse_name')
        if not cls and not (tags & {'GRADED','OPEN'}):miss.append('category')
        if h.get('active') is None:miss.append('active_status')
        if cls=='NEW' or 'NEW' in tags:
            if not h.get('sire'):miss.append('new_sire')
            if not h.get('damsire'):miss.append('new_damsire')
        if 'GRADED' in tags and not (h.get('graded_starts') or h.get('graded_race_names')):miss.append('graded_evidence')
        if cls=='OPEN' or 'OPEN' in tags:
            if h.get('flat_acquired_prize_yen') is None and not h.get('open_or_higher_history') and not h.get('latest_recorded_class')=='オープン':
                # The base/public master can carry verified OPEN tagging from the latest official JRA class.
                if 'OPEN' not in tags:miss.append('open_evidence')
        if not h.get('target_starts') and not h.get('latest_race_date') and cls!='NEW':miss.append('race_history')
        if miss:
            issues.append({'horse_id':hid,'horse_name':name,'missing':miss})
            for x in miss:missing[x]+=1
    structural=[]
    base_summary={}
    if BASE.exists():
        b=json.loads(BASE.read_text(encoding='utf-8'));base_summary=b.get('summary',{})
        if int(base_summary.get('horse_count') or 0)!=len(horses):structural.append('base_catalog_horse_count_mismatch')
        # Zero GRADED/OPEN across a populated master is a structural failure, not a valid completion.
        if len(horses)>=100 and int(base_summary.get('graded_count') or 0)==0:structural.append('graded_catalog_structurally_empty')
        if len(horses)>=100 and int(base_summary.get('open_count') or 0)==0:structural.append('open_catalog_structurally_empty')
    elite_summary={}
    if ELITE.exists():
        e=json.loads(ELITE.read_text(encoding='utf-8'));elite_summary=e.get('summary',{})
        if len(horses)>=100 and int(elite_summary.get('elite_union_count') or 0)==0:structural.append('active_elite_structurally_empty')
    unknown=cats.get('UNKNOWN',0)
    if unknown:structural.append(f'unknown_category:{unknown}')
    complete=not issues and not structural
    summary={'horse_count':len(horses),'complete_horse_count':len(horses)-len(issues),'incomplete_horse_count':len(issues),
      'missing_field_counts':dict(missing),'category_counts':{k:cats.get(k,0) for k in PRIORITY+('UNKNOWN',)},
      'base_open_count':base_summary.get('open_count'),'base_graded_count':base_summary.get('graded_count'),
      'active_elite_count':elite_summary.get('elite_union_count'),'structural_issues':structural,
      'status':'COMPLETE' if complete else 'IN_PROGRESS',
      'definition':'complete within discovered JRA horse master; categories and elite evidence must also pass structural integrity checks; future debut/meeting runners append automatically'}
    OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'summary':summary,'issues':issues[:5000]},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if structural:raise SystemExit('horse master structural integrity failure: '+','.join(structural))

if __name__=='__main__':main()
