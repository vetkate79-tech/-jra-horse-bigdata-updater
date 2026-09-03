#!/usr/bin/env python3
"""Build race-week detail data only for horses actually on upcoming JRA cards."""
from __future__ import annotations
import json, urllib.parse, html as html_lib, re
from pathlib import Path
from bs4 import BeautifulSoup
import sys
sys.path.insert(0,'src')
from collect_upcoming_new_horses import current_week_seeds,fetch,cname_url,extract_links,META,COURSE,HORSE_ID,normalize_horse_id,runner_rows

CAT=Path('docs/data/horses/catalog.json');OUT=Path('docs/data/horses/weekly_runner_details.json');STATUS=Path('status/weekly_runner_details.json')

def load_catalog():
    if not CAT.exists():return {}
    d=json.loads(CAT.read_text(encoding='utf-8'));return {normalize_horse_id(h.get('horse_id')):h for h in d.get('horses',[]) if h.get('horse_id')}

def race_title(soup):
    for sel in ('main h2','#main h2','.race_num + h2','h2'):
        n=soup.select_one(sel)
        if n:
            t=' '.join(n.stripped_strings)
            if t:return t
    return ''

def race_condition(soup):
    text=' '.join(soup.stripped_strings);m=re.search(r'(芝|ダート|ダ)\s*([0-9]{3,4})\s*[mｍ]?',text)
    if not m:return '',None
    return ('芝' if m.group(1)=='芝' else 'ダート'),int(m.group(2))

def frame_and_horse_no(cells):
    nums=[]
    for x in cells[:5]:
        s=x.strip()
        if re.fullmatch(r'\d{1,2}',s):nums.append(s)
    if len(nums)>=2:return nums[0],nums[1]
    if len(nums)==1:return '',nums[0]
    return '',''

def parse_card(cname,raw):
    m=META.search(cname)
    if not m:return None
    soup=BeautifulSoup(raw,'html.parser');d=m.group('date');date=f'{d[:4]}-{d[4:6]}-{d[6:]}';surface,distance_m=race_condition(soup)
    race={'race_id':m.group(0),'date':date,'track':COURSE.get(m.group('course'),m.group('course')),'race_no':int(m.group('race')),'race_name':race_title(soup),'surface':surface,'distance_m':distance_m,'source_url':cname_url(cname),'runners':[]};seen=set()
    for a,hid,name,row_text in runner_rows(soup):
        if hid in seen:continue
        seen.add(hid);tr=a.find_parent('tr');cells=[' '.join(x.stripped_strings) for x in tr.find_all(['th','td'])] if tr else []
        frame_no,horse_no=frame_and_horse_no(cells)
        race['runners'].append({'horse_id':hid,'horse_name':name,'frame_no':frame_no,'horse_no':horse_no,'official_row_text':row_text})
    return race if race['runners'] else None

def runner_detail(race,row,h):
    recent=(h.get('recent_starts') or [])[:5];detail={'horse_id':row['horse_id'],'horse_name':row['horse_name'],'frame_no':row.get('frame_no',''),'horse_no':row.get('horse_no',''),'race':{k:race.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m','source_url')},'sex_age':h.get('sex_age'),'trainer':h.get('trainer'),'current_class':h.get('current_class'),'current_class_label':h.get('current_class_label'),'recent_starts':recent,'official_racecard_text':row.get('official_row_text',''),'detail_scope':'RACE_WEEK_ONLY','source_policy':'JRA_OFFICIAL_RACECARD_PLUS_STORED_JRA_HISTORY'}
    for k in ('win_rate','quinella_rate','show_rate','sire','dam','damsire','pedigree_summary','training_summary'):
        if h.get(k) not in (None,''):detail[k]=h[k]
    return detail

def main():
    by_id=load_catalog();seeds=current_week_seeds();cards=[];errors=[]
    for key,seed in seeds.items():
        try:
            raw=fetch(cname_url(seed));links=extract_links(raw)+[seed];logical=set()
            for c in links:
                m=META.search(c)
                if not m or (m.group('date'),m.group('course'))!=key:continue
                lk=(m.group('date'),m.group('course'),m.group('race'))
                if lk in logical:continue
                logical.add(lk)
                try:
                    card=parse_card(c,fetch(cname_url(c)))
                    if card:cards.append(card)
                except Exception as e:errors.append({'race':c,'error':repr(e)})
        except Exception as e:errors.append({'seed':seed,'error':repr(e)})
    cards=sorted({c['race_id']:c for c in cards}.values(),key=lambda x:(x['date'],x['track'],x['race_no']));runners=[];missing=[]
    for race in cards:
        for row in race['runners']:
            h=by_id.get(row['horse_id'])
            if h is None:h={'horse_id':row['horse_id'],'horse_name':row['horse_name']};missing.append(row['horse_id'])
            runners.append(runner_detail(race,row,h))
    dates=sorted({r['race']['date'] for r in runners});frame_known=sum(1 for r in runners if r.get('frame_no'))
    payload={'summary':{'status':'READY' if runners else 'NO_UPCOMING_RACECARDS','race_count':len(cards),'runner_count':len(runners),'dates':dates,'frame_known_count':frame_known,'frame_pending_count':len(runners)-frame_known,'missing_master_count':len(set(missing)),'policy':'heavy detail exists only for verified upcoming JRA runners'},'runners':runners};OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');STATUS.write_text(json.dumps({**payload['summary'],'errors':errors,'missing_master_ids':sorted(set(missing))},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(payload['summary'],ensure_ascii=False))
if __name__=='__main__':main()
