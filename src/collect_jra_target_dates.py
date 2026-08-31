#!/usr/bin/env python3
import csv,json,os,re,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

os.environ.setdefault('TARGET_YEAR','2026')
import collect_jra_html_results as core

TARGETS={x.replace('-','') for x in os.getenv('TARGET_DATES','2026-08-29,2026-08-30').split(',')}
SEED=os.getenv('JRA_MONTH_SEED','pw01skl10202608/E1')
OUT=Path(os.getenv('TARGET_OUT','data/race_results_html_2026_weekend.csv'))
PAYOUTS=Path('data/race_payouts_2026_weekend.csv')
CONTEXT=Path('data/race_context_2026_weekend.csv')
STATUS=Path('status/html_collection_2026_weekend.json')
UA=core.UA

def request(cname,post=False,retries=5):
    data=urllib.parse.urlencode({'cname':cname}).encode() if post else None
    url=core.ENDPOINT if post else core.ENDPOINT+'?CNAME='+urllib.parse.quote(cname,safe='')
    req=urllib.request.Request(url,data=data,headers={'User-Agent':UA,'Referer':core.ENDPOINT,'Content-Type':'application/x-www-form-urlencoded'})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=60) as r: raw=r.read()
            if len(raw)<15000: raise RuntimeError(f'short response {len(raw)}')
            return raw.decode('shift_jis','replace')
        except Exception:
            if attempt==retries-1: raise
            time.sleep(2**attempt)

core.request=request

def atomic_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=sorted(set().union(*(r.keys() for r in rows))) if rows else []
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    tmp.replace(path)

def discover_target_races():
    # JRA public navigation pages are GET links. POST here previously returned a page
    # from which target race CNAMEs were not discoverable, producing 0/72.
    month=request(SEED,post=False)
    days=core.cnames(core.DAY,month)
    races=set()
    inspected=[]
    for day in days:
        try:
            html=request(day,post=False)
        except Exception as e:
            inspected.append({'day':day,'error':repr(e)})
            continue
        found=core.cnames(core.RACE,html)
        inspected.append({'day':day,'races_found':len(found)})
        for race in found:
            m=core.META.search(race)
            if m and m.group('date') in TARGETS:
                races.add(race)
    return races,inspected

def main():
    races,discovery_log=discover_target_races()
    if len(races)!=72:
        STATUS.parent.mkdir(exist_ok=True)
        STATUS.write_text(json.dumps({'races_discovered':len(races),'expected':72,'target_dates':sorted(TARGETS),'discovery_log':discovery_log,'status':'DISCOVERY_INCOMPLETE'},ensure_ascii=False,indent=2),encoding='utf-8')
        raise RuntimeError(f'target race discovery gate failed: expected 72, got {len(races)}')
    all_rows=[];all_payouts=[];all_context=[];errors=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(core.extract_race,c):c for c in sorted(races)}
        for f in as_completed(futs):
            try:
                _,rows,payouts,ctx,err=f.result();all_rows.extend(rows);all_payouts.extend(payouts);all_context.append(ctx)
                if err:errors.append({'race':futs[f],'errors':err})
            except Exception as e:errors.append({'race':futs[f],'errors':[repr(e)]})
    passed=[r for r in all_rows if r.get('data_status')=='PASS_HTML']
    passed_races={r['race_id'] for r in passed}
    by_date={d:len({r['race_id'] for r in passed if r.get('race_date')==f'{d[:4]}-{d[4:6]}-{d[6:]}'}) for d in sorted(TARGETS)}
    missing_ids=sum(not r.get('horse_id') for r in passed)
    ok=len(passed_races)==72 and all(v==36 for v in by_date.values()) and not errors and missing_ids==0
    atomic_csv(OUT,all_rows);atomic_csv(PAYOUTS,all_payouts);atomic_csv(CONTEXT,all_context)
    STATUS.parent.mkdir(exist_ok=True)
    state={'races_discovered':len(races),'races_passed':len(passed_races),'race_count_by_date':by_date,'runner_rows':len(passed),'missing_horse_ids':missing_ids,'errors':errors,'discovery_log':discovery_log,'status':'PASS' if ok else 'INCOMPLETE'}
    STATUS.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in state.items() if k not in ('errors','discovery_log')},ensure_ascii=False,indent=2))
    if not ok:raise SystemExit('target date quality gate failed')

if __name__=='__main__':main()
