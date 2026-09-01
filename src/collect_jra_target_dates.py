#!/usr/bin/env python3
import csv,json,os,re,time,urllib.parse,urllib.request,html as html_lib
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import defaultdict,Counter
from pathlib import Path

os.environ.setdefault('TARGET_YEAR','2026')
import collect_jra_html_results as core

# JRA exposes both pw01sde01... and pw01sde10... result-page CNAMEs.
core.META=re.compile(r"pw01sde(?:01|10)(?P<course>\d{2})(?P<year>\d{4})(?P<meeting>\d{2})(?P<day>\d{2})(?P<race>\d{2})(?P<date>\d{8})")

TARGETS={x.replace('-','') for x in os.getenv('TARGET_DATES','2026-08-29,2026-08-30').split(',')}
OUT=Path(os.getenv('TARGET_OUT','data/race_results_html_2026_weekend.csv'))
PAYOUTS=Path('data/race_payouts_2026_weekend.csv')
CONTEXT=Path('data/race_context_2026_weekend.csv')
STATUS=Path('status/html_collection_2026_weekend.json')
UA=core.UA

# Verified JRA result-page seeds. Each page exposes all 12 race links for that
# venue/day. Six seeds therefore cover the target 72 races deterministically.
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
    text=urllib.parse.unquote(html_lib.unescape(raw_html))
    return list(dict.fromkeys(re.findall(r'pw01sde(?:01|10)\d{20}/[A-Fa-f0-9]{2}',text)))


def logical_key(cname):
    m=core.META.search(cname)
    if not m:return None
    g=m.groupdict()
    return (g['date'],g['course'],g['race'])


def discover_target_races():
    discovered={}; discovery_log=[]
    for seed in SEEDS:
        try: page=request(seed,post=False)
        except Exception as e:
            discovery_log.append({'seed':seed,'error':repr(e)}); continue
        links=race_links(page); accepted=0
        for race in links+[seed]:
            m=core.META.search(race)
            if not m or m.group('date') not in TARGETS: continue
            key=logical_key(race)
            if not key: continue
            old=discovered.get(key)
            if old is None or ('pw01sde01' in race and 'pw01sde10' in old): discovered[key]=race
            accepted+=1
        discovery_log.append({'seed':seed,'links_found':len(links),'target_links':accepted})
    return set(discovered.values()),discovery_log


def minimal_racecard_coverage(rows):
    groups=defaultdict(list)
    for r in rows:
        name=str(r.get('horse_name','')).strip()
        no=str(r.get('horse_no','')).strip().replace('.0','')
        date=str(r.get('race_date','')).strip()
        course=str(r.get('course','')).strip()
        race_no=str(r.get('race_no','')).strip().replace('.0','')
        if not name or not re.fullmatch(r'\d{1,2}',no) or not date or not course or not re.fullmatch(r'\d{1,2}',race_no):
            continue
        groups[(date,course,int(race_no))].append(r)
    good={}; bad=[]
    for key,rs in groups.items():
        names=[str(x.get('horse_name','')).strip() for x in rs]
        nums=[str(x.get('horse_no','')).strip().replace('.0','') for x in rs]
        reasons=[]
        if not 3<=len(rs)<=18: reasons.append('runner_count')
        if len(names)!=len(set(names)): reasons.append('duplicate_name')
        if len(nums)!=len(set(nums)): reasons.append('duplicate_horse_no')
        if reasons: bad.append({'race':key,'reasons':reasons,'rows':len(rs)})
        else: good[key]=rs
    by_date=Counter(k[0] for k in good)
    return good,bad,dict(by_date)


def main():
    races,discovery_log=discover_target_races()
    if len(races)!=72:
        STATUS.parent.mkdir(exist_ok=True)
        STATUS.write_text(json.dumps({
            'races_discovered':len(races),'expected':72,'target_dates':sorted(TARGETS),
            'seeds':SEEDS,'discovery_log':discovery_log,'status':'DISCOVERY_INCOMPLETE'
        },ensure_ascii=False,indent=2),encoding='utf-8')
        raise RuntimeError(f'target race discovery gate failed: expected 72, got {len(races)}')

    all_rows=[]; all_payouts=[]; all_context=[]; gate_errors=[]; fatal_errors=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(core.extract_race,c):c for c in sorted(races)}
        for f in as_completed(futs):
            race=futs[f]
            try:
                _,rows,payouts,ctx,err=f.result()
                all_rows.extend(rows); all_payouts.extend(payouts); all_context.append(ctx)
                if err: gate_errors.append({'race':race,'errors':err})
            except Exception as e:
                fatal_errors.append({'race':race,'errors':[repr(e)]})

    strict=[r for r in all_rows if r.get('data_status')=='PASS_HTML']
    strict_races={r['race_id'] for r in strict}
    strict_by_date={d:len({r['race_id'] for r in strict if r.get('race_date')==f'{d[:4]}-{d[4:6]}-{d[6:]}'}) for d in sorted(TARGETS)}
    missing_ids=sum(not r.get('horse_id') for r in strict)
    good_cards,bad_cards,card_by_date=minimal_racecard_coverage(all_rows)
    expected_dates={f'{d[:4]}-{d[4:6]}-{d[6:]}' for d in TARGETS}
    racecard_ok=(len(good_cards)==72 and all(card_by_date.get(d,0)==36 for d in expected_dates) and not fatal_errors)
    strict_ok=(len(strict_races)==72 and all(v==36 for v in strict_by_date.values()) and not gate_errors and not fatal_errors and missing_ids==0)

    atomic_csv(OUT,all_rows); atomic_csv(PAYOUTS,all_payouts); atomic_csv(CONTEXT,all_context)
    STATUS.parent.mkdir(exist_ok=True)
    state={
        'races_discovered':len(races),
        'racecard_races_ready':len(good_cards),'racecard_count_by_date':card_by_date,
        'all_runner_rows':len(all_rows),'racecard_bad_groups':bad_cards,
        'strict_races_passed':len(strict_races),'strict_race_count_by_date':strict_by_date,
        'strict_runner_rows':len(strict),'strict_missing_horse_ids':missing_ids,
        'strict_gate_error_count':len(gate_errors),'fatal_error_count':len(fatal_errors),
        'gate_errors':gate_errors,'fatal_errors':fatal_errors,'discovery_log':discovery_log,
        'status':'PASS' if strict_ok else ('RACECARD_PASS' if racecard_ok else 'INCOMPLETE')
    }
    STATUS.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in state.items() if k not in ('gate_errors','fatal_errors','discovery_log','racecard_bad_groups')},ensure_ascii=False,indent=2))
    if not racecard_ok: raise SystemExit('target racecard coverage failed')

if __name__=='__main__':main()
