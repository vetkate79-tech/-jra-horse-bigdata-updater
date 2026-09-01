#!/usr/bin/env python3
import csv,json,os,re,time,urllib.parse,urllib.request,html as html_lib
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

os.environ.setdefault('TARGET_YEAR','2026')
import collect_jra_html_results as core

TARGETS={x.replace('-','') for x in os.getenv('TARGET_DATES','2026-08-29,2026-08-30').split(',')}
OUT=Path(os.getenv('TARGET_OUT','data/race_results_html_2026_weekend.csv'))
PAYOUTS=Path('data/race_payouts_2026_weekend.csv')
CONTEXT=Path('data/race_context_2026_weekend.csv')
STATUS=Path('status/html_collection_2026_weekend.json')
UA=core.UA

# Verified JRA result-page seeds. Each page contains the race-navigation links for
# its own venue/day, so six seeds are sufficient to discover 6 x 12 = 72 races.
# Keeping these explicit also avoids depending on JRA's month/day selector markup.
DEFAULT_SEEDS=[
    'pw01sde0104202603030120260829/4C', # 8/29 新潟1R
    'pw01sde0107202603030120260829/2A', # 8/29 中京1R
    'pw01sde0101202602030120260829/3D', # 8/29 札幌1R
    'pw01sde0104202603040120260830/74', # 8/30 新潟1R
    'pw01sde0107202603040120260830/52', # 8/30 中京1R
    'pw01sde0101202602040120260830/65', # 8/30 札幌1R
]
SEEDS=[x.strip() for x in os.getenv('JRA_TARGET_RACE_SEEDS',','.join(DEFAULT_SEEDS)).split(',') if x.strip()]


def request(cname,post=False,retries=5):
    data=urllib.parse.urlencode({'cname':cname}).encode() if post else None
    url=core.ENDPOINT if post else core.ENDPOINT+'?CNAME='+urllib.parse.quote(cname,safe='')
    req=urllib.request.Request(url,data=data,headers={
        'User-Agent':UA,'Referer':core.ENDPOINT,
        'Content-Type':'application/x-www-form-urlencoded',
        'Accept-Language':'ja,en-US;q=0.8,en;q=0.6',
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=60) as r: raw=r.read()
            if len(raw)<15000: raise RuntimeError(f'short response {len(raw)}')
            # JRA DB pages have historically used Shift_JIS/CP932.
            return raw.decode('cp932','replace')
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


def race_links(raw_html):
    """Extract both /XX and %2FXX CNAME forms from JRA navigation markup."""
    text=urllib.parse.unquote(html_lib.unescape(raw_html))
    vals=re.findall(r'pw01sde(?:01|10)\d{20}/[A-Fa-f0-9]{2}',text)
    return list(dict.fromkeys(v.upper() if v[-2:].islower() else v for v in vals))


def logical_key(cname):
    m=core.META.search(cname)
    if not m:return None
    g=m.groupdict()
    return (g['date'],g['course'],g['race'])


def discover_target_races():
    discovered={}
    discovery_log=[]
    for seed in SEEDS:
        try:
            page=request(seed,post=False)
        except Exception as e:
            discovery_log.append({'seed':seed,'error':repr(e)})
            continue
        links=race_links(page)
        accepted=0
        for race in links+[seed]:
            m=core.META.search(race)
            if not m or m.group('date') not in TARGETS:
                continue
            key=logical_key(race)
            if not key:
                continue
            # Prefer the public 01 variant when both 01/10 variants appear.
            old=discovered.get(key)
            if old is None or ('pw01sde01' in race and 'pw01sde10' in old):
                discovered[key]=race
            accepted+=1
        discovery_log.append({'seed':seed,'links_found':len(links),'target_links':accepted})
    return set(discovered.values()),discovery_log


def main():
    races,discovery_log=discover_target_races()
    if len(races)!=72:
        STATUS.parent.mkdir(exist_ok=True)
        STATUS.write_text(json.dumps({
            'races_discovered':len(races),'expected':72,
            'target_dates':sorted(TARGETS),'seeds':SEEDS,
            'discovery_log':discovery_log,'status':'DISCOVERY_INCOMPLETE'
        },ensure_ascii=False,indent=2),encoding='utf-8')
        raise RuntimeError(f'target race discovery gate failed: expected 72, got {len(races)}')

    all_rows=[];all_payouts=[];all_context=[];errors=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(core.extract_race,c):c for c in sorted(races)}
        for f in as_completed(futs):
            try:
                _,rows,payouts,ctx,err=f.result()
                all_rows.extend(rows);all_payouts.extend(payouts);all_context.append(ctx)
                if err:errors.append({'race':futs[f],'errors':err})
            except Exception as e:
                errors.append({'race':futs[f],'errors':[repr(e)]})

    passed=[r for r in all_rows if r.get('data_status')=='PASS_HTML']
    passed_races={r['race_id'] for r in passed}
    by_date={d:len({r['race_id'] for r in passed if r.get('race_date')==f'{d[:4]}-{d[4:6]}-{d[6:]}'}) for d in sorted(TARGETS)}
    discovered_by_date={d:sum(1 for r in races if (core.META.search(r) and core.META.search(r).group('date')==d)) for d in sorted(TARGETS)}
    missing_ids=sum(not r.get('horse_id') for r in passed)
    ok=(len(passed_races)==72 and all(v==36 for v in by_date.values()) and not errors and missing_ids==0)

    atomic_csv(OUT,all_rows);atomic_csv(PAYOUTS,all_payouts);atomic_csv(CONTEXT,all_context)
    STATUS.parent.mkdir(exist_ok=True)
    state={
        'races_discovered':len(races),'discovered_race_count_by_date':discovered_by_date,
        'races_passed':len(passed_races),'race_count_by_date':by_date,
        'runner_rows':len(passed),'missing_horse_ids':missing_ids,
        'errors':errors,'discovery_log':discovery_log,
        'status':'PASS' if ok else 'INCOMPLETE'
    }
    STATUS.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in state.items() if k not in ('errors','discovery_log')},ensure_ascii=False,indent=2))
    if not ok:raise SystemExit('target date quality gate failed')

if __name__=='__main__':main()
