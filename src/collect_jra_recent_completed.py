#!/usr/bin/env python3
"""Discover recently completed JRA central meetings and merge official results.

Designed for scheduled GitHub Actions. It is fail-closed: if a date cannot be
verified as complete (12 races per discovered venue), nothing for that date is
published.
"""
from __future__ import annotations
import csv,json,os,re,time,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from pathlib import Path
from collections import defaultdict,deque

os.environ.setdefault('TARGET_YEAR',str(datetime.now(timezone(timedelta(hours=9))).year))
import collect_jra_html_results as core

JST=timezone(timedelta(hours=9)); NOW=datetime.now(JST)
DATA=Path('data'); STATUS=Path('status/jra_post_meeting_update.json')
OUT=DATA/f'race_results_html_{NOW.year}.csv'; PAYOUTS=DATA/f'race_payouts_{NOW.year}.csv'; CONTEXT=DATA/f'race_context_{NOW.year}.csv'
UA=core.UA
ALL_CNAME=re.compile(r'(pw01(?:skl|srl|sde)\d+/[A-F0-9]{2})')
RACE_META=core.META

def target_dates():
    raw=os.getenv('TARGET_DATES','').strip()
    if raw:return {x.replace('-','') for x in raw.split(',') if x.strip()}
    days=int(os.getenv('LOOKBACK_DAYS','4'))
    return {(NOW.date()-timedelta(days=i)).strftime('%Y%m%d') for i in range(days)}

def fetch(cname=None,post=False,retries=3):
    data=urllib.parse.urlencode({'cname':cname}).encode() if post and cname else None
    if cname:url=core.ENDPOINT+'?CNAME='+urllib.parse.quote(cname,safe='')
    else:url=core.ENDPOINT
    req=urllib.request.Request(url,data=data,headers={'User-Agent':UA,'Referer':'https://www.jra.go.jp/','Content-Type':'application/x-www-form-urlencoded'})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=45) as r:raw=r.read()
            if len(raw)<5000:raise RuntimeError(f'short response {len(raw)}')
            return raw.decode('cp932','replace')
        except Exception:
            if i==retries-1:raise
            time.sleep(1.5*(i+1))

def href_cnames(html):
    vals=[]
    for m in re.finditer(r'CNAME=([^&"\'> ]+)',html,re.I):
        vals.append(urllib.parse.unquote(m.group(1)))
    vals.extend(ALL_CNAME.findall(html))
    return list(dict.fromkeys(vals))

def current_card_urls():
    out=[]
    weekly=Path('docs/data/horses/weekly_runner_details.json')
    if weekly.exists():
        try:
            d=json.loads(weekly.read_text(encoding='utf-8'))
            for x in d.get('runners',[]):
                r=x.get('race') or {}
                u=str(r.get('source_url') or '')
                if u and r.get('date','').replace('-','') in target_dates():out.append(u)
        except Exception:pass
    return list(dict.fromkeys(out))

def fetch_url(url,retries=3):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Referer':'https://www.jra.go.jp/'})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=45) as r:raw=r.read()
            if len(raw)<5000:raise RuntimeError(f'short response {len(raw)}')
            return raw.decode('cp932','replace')
        except Exception:
            if i==retries-1:raise
            time.sleep(1.5*(i+1))

def seed_cnames():
    out=[]
    cards=Path('docs/data/race_cards.json')
    if cards.exists():
        try:
            d=json.loads(cards.read_text(encoding='utf-8'))
            for r in d.get('races',[]):
                u=r.get('source_url','');m=re.search(r'CNAME=([^&]+)',u)
                if m:out.append(urllib.parse.unquote(m.group(1)))
        except Exception:pass
    for dt in (NOW,NOW-timedelta(days=31)):
        out.append(f'pw01skl10{dt.year}{dt.month:02d}/E1')
    return list(dict.fromkeys(out))

def discover():
    targets=target_dates(); found=set(); visited=set(); q=deque([None]+seed_cnames()); log=[]
    # Current JRA race-card pages contain menu links to the corresponding
    # official result pages. Seed from those exact pages so discovery does not
    # depend on historical month-selector checksums or one CNAME generation.
    for url in current_card_urls():
        try:
            html=fetch_url(url)
            links=href_cnames(html);log.append({'page':url,'links':len(links),'seed':'weekly_card'})
            for link in links:
                m=RACE_META.search(link)
                if m and m.group('date') in targets:found.add(link)
                elif link.startswith('pw01srl') or link.startswith('pw01skl'):
                    q.append(link)
        except Exception as e:
            log.append({'page':url,'error':repr(e),'seed':'weekly_card'})
    max_pages=int(os.getenv('DISCOVERY_MAX_PAGES','180'))
    while q and len(visited)<max_pages:
        cname=q.popleft(); key=cname or '__BASE__'
        if key in visited:continue
        visited.add(key)
        html=None
        for post in ((False,True) if cname else (False,)):
            try:
                html=fetch(cname,post=post);break
            except Exception as e:
                last=repr(e)
        if html is None:
            log.append({'page':key,'error':last});continue
        links=href_cnames(html);log.append({'page':key,'links':len(links)})
        for link in links:
            m=RACE_META.search(link)
            if m:
                if m.group('date') in targets:found.add(link)
                continue
            if link.startswith('pw01srl') or link.startswith('pw01skl'):
                if link not in visited:q.append(link)
        # Once we have at least one target race, follow its siblings too.
        for r in list(found):
            if r not in visited:q.append(r)
    return found,log

def minimal_ok(rows):
    if not 3<=len(rows)<=18:return False
    nums=[];ids=[];names=[]
    for r in rows:
        try:nums.append(int(float(str(r.get('horse_no','')))))
        except:return False
        names.append(str(r.get('horse_name','')).strip());ids.append(str(r.get('horse_id','')).strip())
    return len(set(nums))==len(nums) and all(names) and len(set(names))==len(names) and all(ids)

def merge_csv(path,new_rows,key_fields):
    old=[]
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
    by={tuple(r.get(k,'') for k in key_fields):r for r in old}
    for r in new_rows:by[tuple(r.get(k,'') for k in key_fields)]=r
    rows=list(by.values());fields=sorted(set().union(*(r.keys() for r in rows))) if rows else []
    path.parent.mkdir(exist_ok=True);tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    tmp.replace(path)
    return len(rows)

def main():
    races,discovery_log=discover();groups=defaultdict(set)
    for c in races:
        m=RACE_META.search(c)
        if m:groups[m.group('date')].add((m.group('course'),int(m.group('race'))))
    complete_dates=[];incomplete={}
    for d,vals in groups.items():
        by_course=defaultdict(set)
        for course,rno in vals:by_course[course].add(rno)
        bad={c:sorted(ns) for c,ns in by_course.items() if ns!=set(range(1,13))}
        if not bad and by_course:complete_dates.append(d)
        else:incomplete[d]=bad
    accepted={c for c in races if (RACE_META.search(c) and RACE_META.search(c).group('date') in complete_dates)}
    all_rows=[];payouts=[];contexts=[];errors=[];racecards_ready=0
    for c in sorted(accepted):
        try:
            _,rows,pays,ctx,strict_err=core.extract_race(c)
            if not minimal_ok(rows):raise RuntimeError('minimal racecard gate failed')
            racecards_ready+=1
            all_rows.extend(rows);payouts.extend(pays);contexts.append(ctx)
            if strict_err:errors.append({'race':c,'strict_errors':strict_err})
        except Exception as e:errors.append({'race':c,'fatal':repr(e)})
    fatal=[e for e in errors if 'fatal' in e]
    if fatal:
        STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({'status':'FAILED','fatal_errors':fatal,'discovered':len(races),'complete_dates':complete_dates},ensure_ascii=False,indent=2),encoding='utf-8');raise SystemExit('fatal extraction errors')
    changed=bool(all_rows)
    totals={}
    if changed:
        totals['result_rows']=merge_csv(OUT,all_rows,['race_id','horse_no'])
        if payouts:totals['payout_rows']=merge_csv(PAYOUTS,payouts,['race_id','bet_type','winning_selection'])
        if contexts:totals['context_rows']=merge_csv(CONTEXT,contexts,['race_id'])
    status={'status':'UPDATED' if changed else 'NO_COMPLETED_MEETING','checked_at':NOW.isoformat(),'target_dates':sorted(target_dates()),'discovered_races':len(races),'complete_dates':sorted(complete_dates),'incomplete':incomplete,'racecards_ready':racecards_ready,'new_runner_rows':len(all_rows),'strict_warnings':errors,'totals':totals,'discovery_pages':len(discovery_log)}
    STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(status,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
