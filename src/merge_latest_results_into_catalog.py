#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path

CAT=Path('docs/data/horses/catalog.json'); SRC=Path('data/race_results_html_2026.csv')

def clean(v):
    s='' if v is None else str(v).strip()
    return '' if s.lower()=='nan' else s

def read_rows():
    if not SRC.exists():return []
    with SRC.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    out=[]
    for r in rows:
        if clean(r.get('horse_id')) and clean(r.get('horse_name')) and clean(r.get('race_date')):out.append(r)
    return out

def main():
    base={'summary':{},'horses':[]}
    if CAT.exists():base=json.loads(CAT.read_text(encoding='utf-8'))
    horses=base.get('horses',[]);by_id={clean(h.get('horse_id')):h for h in horses if clean(h.get('horse_id'))};by_name={clean(h.get('horse_name')):h for h in horses}
    grouped=defaultdict(list)
    for r in read_rows():grouped[clean(r['horse_id'])].append(r)
    newest=''
    for hid,rs in grouped.items():
        rs.sort(key=lambda r:(clean(r.get('race_date')),clean(r.get('race_id')),int(float(clean(r.get('horse_no')) or 0))))
        r=rs[-1];newest=max(newest,clean(r.get('race_date')))
        h=by_id.get(hid) or by_name.get(clean(r.get('horse_name')))
        if not h:
            h={'horse_name':clean(r.get('horse_name')),'horse_id':hid,'tags':['CENTRAL_RESULT_AUTO'],'graded_experience':[],'graded_starts':[],'target_starts':[]}
            horses.append(h);by_id[hid]=h;by_name[h['horse_name']]=h
        h['horse_name']=clean(r.get('horse_name')) or h.get('horse_name','');h['horse_id']=hid
        h['sex_age']=clean(r.get('sex_age')) or h.get('sex_age','');h['trainer']=clean(r.get('trainer')) or h.get('trainer','')
        h['latest_race_date']=clean(r.get('race_date'));h['latest_course']=clean(r.get('course'));h['latest_surface']=clean(r.get('surface'));h['latest_distance_m']=clean(r.get('distance_m'));h['latest_finish']=clean(r.get('finish_position'))
        h['latest_start']={'race_id':clean(r.get('race_id')),'date':clean(r.get('race_date')),'course':clean(r.get('course')),'race_no':clean(r.get('race_no')),'race_name':clean(r.get('race_name')),'surface':clean(r.get('surface')),'distance_m':clean(r.get('distance_m')),'horse_no':clean(r.get('horse_no')),'finish':clean(r.get('finish_position')),'jockey':clean(r.get('jockey')),'source_url':clean(r.get('source_url'))}
        recent=[]
        for x in reversed(rs[-5:]):
            recent.append({'race_id':clean(x.get('race_id')),'date':clean(x.get('race_date')),'course':clean(x.get('course')),'race_no':clean(x.get('race_no')),'race_name':clean(x.get('race_name')),'surface':clean(x.get('surface')),'distance_m':clean(x.get('distance_m')),'finish':clean(x.get('finish_position'))})
        h['recent_starts']=recent
        tags=set(h.get('tags') or []);tags.add('CENTRAL_RESULT_AUTO');h['tags']=sorted(tags)
    horses.sort(key=lambda h:clean(h.get('horse_name')))
    s=base.setdefault('summary',{});s['horse_count']=len(horses);s['auto_result_source']='JRA_OFFICIAL_RESULT_HTML';s['latest_completed_jra_date']=newest or s.get('latest_completed_jra_date','');s['auto_update_enabled']=True
    CAT.parent.mkdir(parents=True,exist_ok=True);CAT.write_text(json.dumps({'summary':s,'horses':horses},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'horse_count':len(horses),'latest_completed_jra_date':s['latest_completed_jra_date']},ensure_ascii=False))

if __name__=='__main__':main()
