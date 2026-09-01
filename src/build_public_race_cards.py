#!/usr/bin/env python3
import csv,json,re
from collections import defaultdict,Counter
from pathlib import Path

SRC=Path('data/race_results_html_2026_weekend.csv')
OUT=Path('docs/data/race_cards.json')
TARGET_DATES={'2026-08-29','2026-08-30'}


def clean(v):
    v='' if v is None else str(v).strip()
    return '' if v.lower()=='nan' else v


def num(v):
    v=clean(v).replace('.0','')
    m=re.fullmatch(r'\d+',v)
    return int(v) if m else None


def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    if not SRC.exists():
        raise SystemExit('race result source missing')

    rows=[]
    with SRC.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if clean(r.get('race_date')) not in TARGET_DATES: continue
            if not clean(r.get('horse_name')) or num(r.get('horse_no')) is None: continue
            rows.append(r)

    groups=defaultdict(list)
    for r in rows:
        key=(clean(r.get('race_date')),clean(r.get('course')),num(r.get('race_no')))
        if key[0] and key[1] and key[2]: groups[key].append(r)

    races=[]; rejected=[]
    for (date,track,race_no),rs in sorted(groups.items()):
        rs=sorted(rs,key=lambda x:num(x.get('horse_no')) or 999)
        names=[clean(x.get('horse_name')) for x in rs]
        numbers=[num(x.get('horse_no')) for x in rs]
        reasons=[]
        if not 3<=len(rs)<=18: reasons.append('runner_count')
        if len(names)!=len(set(names)): reasons.append('duplicate_name')
        if len(numbers)!=len(set(numbers)): reasons.append('duplicate_horse_no')
        if reasons:
            rejected.append({'date':date,'track':track,'race_no':race_no,'reasons':reasons})
            continue

        first=rs[0]; horses=[]
        for r in rs:
            n=num(r.get('horse_no')); frame=num(r.get('枠') or r.get('frame'))
            horses.append({
                'n':str(n),'frame':frame,'name':clean(r.get('horse_name')),
                'sex':clean(r.get('sex_age')),'weight':clean(r.get('carried_weight')),
                'jockey':clean(r.get('jockey')),'recent':'','horse_id':clean(r.get('horse_id'))
            })
        statuses={clean(x.get('data_status')) for x in rs}
        quality='STRICT_PASS' if statuses=={'PASS_HTML'} else 'RACECARD_MINIMAL_VERIFIED'
        races.append({
            'race_id':clean(first.get('race_id')),
            'date':date,'track':track,'race_no':race_no,
            'race_name':clean(first.get('race_name')),
            'start_time':clean(first.get('scheduled_start')),
            'surface':clean(first.get('surface')),
            'distance_m':num(first.get('distance_m')),
            'field_size':len(horses),
            'source_url':clean(first.get('source_url')),
            'source':'JRA_OFFICIAL_RESULT_HTML','quality':quality,
            'horses':horses
        })

    by_date=Counter(x['date'] for x in races)
    by_track=Counter(f"{x['date']}:{x['track']}" for x in races)
    ready=(len(races)==72 and all(by_date.get(d,0)==36 for d in TARGET_DATES) and all(v==12 for v in by_track.values()) and len(by_track)==6)
    payload={
        'source':'JRA_OFFICIAL_ONLY','status':'READY' if ready else 'INCOMPLETE',
        'race_count':len(races),'race_count_by_date':dict(sorted(by_date.items())),
        'race_count_by_date_track':dict(sorted(by_track.items())),
        'rejected':rejected,'races':races
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k not in ('races','rejected')},ensure_ascii=False,indent=2))
    if not ready: raise SystemExit(f'public race card coverage incomplete: {len(races)}/72')

if __name__=='__main__': main()
