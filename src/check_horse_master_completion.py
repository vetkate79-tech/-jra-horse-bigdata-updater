#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

CAT=Path('docs/data/horses/catalog.json')
OUT=Path('status/horse_master_completion.json')


def main():
    if not CAT.exists():
        raise SystemExit('catalog missing')
    doc=json.loads(CAT.read_text(encoding='utf-8'))
    horses=doc.get('horses',[])
    issues=[]
    counts=Counter()
    for h in horses:
        name=h.get('horse_name') or ''
        hid=h.get('horse_id') or ''
        cls=h.get('current_class') or ''
        tags=set(h.get('tags') or [])
        miss=[]
        if not hid: miss.append('horse_id')
        if not name: miss.append('horse_name')
        if not cls and not (tags & {'GRADED','OPEN'}): miss.append('category')
        # active may legitimately be unknown until a profile has been checked.
        if h.get('active') is None: miss.append('active_status')
        if cls=='NEW' or 'NEW' in tags:
            if not h.get('sire'): miss.append('new_sire')
            if not h.get('damsire'): miss.append('new_damsire')
        if 'GRADED' in tags:
            if not h.get('graded_starts'): miss.append('graded_evidence')
        if cls=='OPEN' or 'OPEN' in tags:
            if h.get('flat_acquired_prize_yen') is None and not h.get('open_or_higher_history'):
                miss.append('open_evidence')
        if not h.get('target_starts') and not h.get('latest_race_date') and cls!='NEW':
            miss.append('race_history')
        if miss:
            issues.append({'horse_id':hid,'horse_name':name,'missing':miss})
            for x in miss: counts[x]+=1
    summary={
        'horse_count':len(horses),
        'complete_horse_count':len(horses)-len(issues),
        'incomplete_horse_count':len(issues),
        'missing_field_counts':dict(counts),
        'status':'COMPLETE' if not issues else 'IN_PROGRESS',
        'definition':'complete within discovered JRA horse master; future debut/meeting runners continue to append automatically'
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({'summary':summary,'issues':issues[:5000]},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
