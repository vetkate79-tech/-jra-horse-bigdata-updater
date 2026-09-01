#!/usr/bin/env python3
import csv,json
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import collect_active_elite_horses as elite

SRC=Path('data/race_results_html_2026.csv'); DOCS=Path('docs/data/horses')

def clean(v):
    s='' if v is None else str(v).strip();return '' if s.lower()=='nan' else s

def read_csv(path):
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def load_horses(name):
    p=DOCS/name
    if not p.exists():return []
    try:return json.loads(p.read_text(encoding='utf-8')).get('horses',[])
    except Exception:return []

def main():
    rows=read_csv(SRC)
    dates=sorted({clean(r.get('race_date')) for r in rows if clean(r.get('race_date'))})
    if not dates:print('{"status":"NO_DATA"}');return
    latest=dates[-1];candidates={}
    for r in rows:
        if clean(r.get('race_date'))!=latest:continue
        hid=clean(r.get('horse_id'));name=clean(r.get('horse_name'))
        if hid:candidates[hid]={'horse_id':hid,'horse_name':name,'candidate_sources':{'LATEST_COMPLETED_MEETING'}}
    for fn in ('active_elite.json','active_graded.json','active_open.json'):
        for h in load_horses(fn):
            hid=clean(h.get('horse_id'))
            if hid:candidates.setdefault(hid,{'horse_id':hid,'horse_name':clean(h.get('horse_name')),'candidate_sources':set()})['candidate_sources'].add('EXISTING_ELITE_REFRESH')
    parsed=[];errors=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        fs={ex.submit(elite.request_profile,c['horse_id']):c for c in candidates.values()}
        for f in as_completed(fs):
            c=fs[f]
            try:parsed.append(elite.parse_profile(c,f.result()))
            except Exception as e:errors.append({'horse_id':c['horse_id'],'error':repr(e)})
    if errors:raise SystemExit(f'incremental elite refresh errors: {len(errors)}')
    active=[x for x in parsed if x.get('active')];new_g={x['horse_id']:x for x in active if x.get('graded_starts')};new_o={x['horse_id']:x for x in active if (x.get('flat_acquired_prize_yen') or 0)>elite.OPEN_THRESHOLD_YEN}
    touched=set(candidates)
    old_g={x['horse_id']:x for x in load_horses('active_graded.json') if x.get('horse_id') not in touched};old_o={x['horse_id']:x for x in load_horses('active_open.json') if x.get('horse_id') not in touched}
    old_g.update(new_g);old_o.update(new_o);union={**old_g,**old_o}
    summary={'source':'JRA_OFFICIAL_HORSE_PROFILE_INCREMENTAL','latest_completed_date':latest,'profiles_refreshed':len(parsed),'active_graded_count':len(old_g),'active_open_count':len(old_o),'elite_union_count':len(union),'open_threshold_yen':elite.OPEN_THRESHOLD_YEN}
    DOCS.mkdir(parents=True,exist_ok=True)
    for fn,obj in [('active_graded.json',old_g),('active_open.json',old_o),('active_elite.json',union)]:
        hs=sorted(obj.values(),key=lambda x:x.get('horse_name',''));(DOCS/fn).write_text(json.dumps({'summary':summary,'horses':hs},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
