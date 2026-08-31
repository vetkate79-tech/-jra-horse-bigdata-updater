#!/usr/bin/env python3
import csv,json,re
from collections import defaultdict
from pathlib import Path

SRC=Path('data/race_results_html_2026_weekend.csv')
OUT=Path('docs/data/race_cards.json')

def clean(v):
    v='' if v is None else str(v).strip()
    return '' if v.lower()=='nan' else v

def num(v):
    v=clean(v).replace('.0','')
    m=re.search(r'\d+',v)
    return int(m.group()) if m else None

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    if not SRC.exists():
        OUT.write_text(json.dumps({'source':'JRA_OFFICIAL_ONLY','status':'DATA_PENDING','races':[]},ensure_ascii=False,indent=2),encoding='utf-8')
        return
    rows=[]
    with SRC.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r.get('data_status')!='PASS_HTML':
                continue
            rows.append(r)
    groups=defaultdict(list)
    for r in rows:
        key=(r.get('race_date',''),r.get('course',''),num(r.get('race_no')))
        if key[0] and key[1] and key[2]: groups[key].append(r)
    races=[]
    for (date,track,race_no),rs in sorted(groups.items()):
        rs=sorted(rs,key=lambda x:num(x.get('horse_no')) or 999)
        first=rs[0]
        horses=[]
        for r in rs:
            n=num(r.get('horse_no'))
            if not n: continue
            frame=num(r.get('枠') or r.get('frame'))
            horses.append({
                'n':str(n),'frame':frame,'name':clean(r.get('horse_name')),
                'sex':clean(r.get('sex_age')),'weight':clean(r.get('carried_weight')),
                'jockey':clean(r.get('jockey')),'recent':'',
                'horse_id':clean(r.get('horse_id'))
            })
        races.append({
            'race_id':clean(first.get('race_id')),
            'date':date,'track':track,'race_no':race_no,
            'race_name':clean(first.get('race_name')),
            'start_time':clean(first.get('scheduled_start')),
            'surface':clean(first.get('surface')),
            'distance_m':num(first.get('distance_m')),
            'field_size':len(horses),
            'source_url':clean(first.get('source_url')),
            'source':'JRA_OFFICIAL_RESULT_HTML',
            'horses':horses
        })
    payload={'source':'JRA_OFFICIAL_ONLY','status':'READY' if races else 'DATA_PENDING','race_count':len(races),'races':races}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__': main()
