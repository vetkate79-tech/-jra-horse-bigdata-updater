#!/usr/bin/env python3
"""Build race-week detail data only for horses actually on upcoming JRA cards."""
from __future__ import annotations
import json,re
from pathlib import Path
from bs4 import BeautifulSoup
import sys
sys.path.insert(0,'src')
from collect_upcoming_new_horses import current_week_seeds,fetch,cname_url,extract_links,META,COURSE,normalize_horse_id,runner_rows

CAT=Path('docs/data/horses/catalog.json');OUT=Path('docs/data/horses/weekly_runner_details.json');STATUS=Path('status/weekly_runner_details.json')

def load_catalog():
    if not CAT.exists():return {}
    d=json.loads(CAT.read_text(encoding='utf-8'));return {normalize_horse_id(h.get('horse_id')):h for h in d.get('horses',[]) if h.get('horse_id')}

def race_title(soup):
    heads=[]
    for n in soup.find_all(['h1','h2','h3']):
        t=' '.join(n.stripped_strings).strip()
        if not t or any(x in t for x in ('検索ウィンドウ','関連メニュー','開催選択','レース選択','ここから本文','本賞金','出馬表')):continue
        heads.append(t)
    pat=re.compile(r'(未勝利|メイクデビュー|新馬|オープン|特別|ステークス|カップ|賞|記念|クラス|障害|リステッド|重賞|G[123])')
    for t in heads:
        if pat.search(t) and len(t)<=60:return t
    for t in heads:
        if len(t)<=40 and not re.search(r'\d{4}年\d{1,2}月\d{1,2}日',t):return t
    return ''

def race_condition(soup):
    text=' '.join(soup.stripped_strings);m=re.search(r'コース[:：]\s*([0-9,]+)\s*メートル\s*[（(]\s*(芝|ダート)',text)
    if m:return m.group(2),int(m.group(1).replace(',',''))
    m=re.search(r'(芝|ダート|ダ)\s*([0-9]{3,4})\s*[mｍ]?',text)
    return (('芝' if m and m.group(1)=='芝' else 'ダート'),int(m.group(2))) if m else ('',None)

def start_time(soup):
    text=' '.join(soup.stripped_strings);m=re.search(r'発走時刻[:：]\s*(\d{1,2})時(\d{2})分',text)
    return f'{int(m.group(1)):02d}:{m.group(2)}' if m else ''

def frame_and_horse_no(cells):
    nums=[x.strip() for x in cells[:5] if re.fullmatch(r'\d{1,2}',x.strip())]
    if len(nums)>=2:return nums[0],nums[1]
    if len(nums)==1:return '',nums[0]
    return '',''

def row_meta(row_text):
    sex_age='';carried='';jockey='';m=re.search(r'(牡|牝|せん)\s*(\d+)',row_text)
    if m:sex_age=f'{m.group(1)}{m.group(2)}'
    m=re.search(r'(\d{2}(?:\.\d)?)\s*kg\s*([▲△★☆◇]?[^0-9]+?)(?=\s+20\d{2}年|\s*$)',row_text)
    if m:carried=m.group(1);jockey=' '.join(m.group(2).split()).strip()
    return sex_age,carried,jockey

def prior_starts(row_text):
    out=[]
    parts=re.split(r'(?=20\d{2}年\d{1,2}月\d{1,2}日)',row_text)
    for p in parts:
        dm=re.match(r'(20\d{2})年(\d{1,2})月(\d{1,2})日\s+([^\s]+)',p)
        fm=re.search(r'(\d+)着',p);cm=re.search(r'(\d{3,4})(芝|ダ)',p)
        if not dm or not fm or not cm:continue
        lm=re.search(r'3F\s*(\d+(?:\.\d+)?)',p)
        out.append({'race_date':f'{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}','course':dm.group(4),'finish_position':int(fm.group(1)),'distance_m':int(cm.group(1)),'surface':'芝' if cm.group(2)=='芝' else 'ダート','last3f':float(lm.group(1)) if lm else None,'source':'JRA_CURRENT_RACECARD_PRIOR_START'})
    out.sort(key=lambda x:x['race_date'],reverse=True);return out[:4]

def parse_card(cname,raw):
    m=META.search(cname)
    if not m:return None
    soup=BeautifulSoup(raw,'html.parser');d=m.group('date');date=f'{d[:4]}-{d[4:6]}-{d[6:]}';surface,distance_m=race_condition(soup)
    race={'race_id':m.group(0),'date':date,'track':COURSE.get(m.group('course'),m.group('course')),'race_no':int(m.group('race')),'race_name':race_title(soup),'surface':surface,'distance_m':distance_m,'start_time':start_time(soup),'source_url':cname_url(cname),'runners':[]};seen=set()
    for a,hid,name,row_text in runner_rows(soup):
        if hid in seen:continue
        seen.add(hid);tr=a.find_parent('tr');cells=[' '.join(x.stripped_strings) for x in tr.find_all(['th','td'])] if tr else [];frame_no,horse_no=frame_and_horse_no(cells);sex_age,carried,jockey=row_meta(row_text)
        race['runners'].append({'horse_id':hid,'horse_name':name,'frame_no':frame_no,'horse_no':horse_no,'sex_age':sex_age,'carried_weight':carried,'jockey':jockey,'recent_starts_from_card':prior_starts(row_text),'official_row_text':row_text})
    return race if race['runners'] else None

def runner_detail(race,row,h):
    card_recent=row.get('recent_starts_from_card') or [];master_recent=(h.get('recent_starts') or [])[:5];seen=set();recent=[]
    for x in card_recent+master_recent:
        k=(str(x.get('race_date') or x.get('date') or ''),str(x.get('course') or x.get('track') or ''),str(x.get('finish_position') or x.get('finish') or ''))
        if k in seen:continue
        seen.add(k);recent.append(x)
    detail={'horse_id':row['horse_id'],'horse_name':row['horse_name'],'frame_no':row.get('frame_no',''),'horse_no':row.get('horse_no',''),'jockey':row.get('jockey',''),'carried_weight':row.get('carried_weight',''),'race':{k:race.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m','start_time','source_url')},'sex_age':row.get('sex_age') or h.get('sex_age'),'trainer':h.get('trainer'),'current_class':h.get('current_class'),'current_class_label':h.get('current_class_label'),'recent_starts':recent[:5],'official_racecard_text':row.get('official_row_text',''),'detail_scope':'RACE_WEEK_ONLY','source_policy':'JRA_OFFICIAL_RACECARD_PLUS_STORED_JRA_HISTORY'}
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
    dates=sorted({r['race']['date'] for r in runners});frame_known=sum(1 for r in runners if r.get('frame_no'));prior_rows=sum(len(r.get('recent_starts') or []) for r in runners)
    payload={'summary':{'status':'READY' if runners else 'NO_UPCOMING_RACECARDS','race_count':len(cards),'runner_count':len(runners),'dates':dates,'race_name_resolved_count':sum(1 for c in cards if c.get('race_name') and c.get('race_name')!='検索ウィンドウ'),'race_condition_resolved_count':sum(1 for c in cards if c.get('surface') and c.get('distance_m')),'card_prior_start_rows':prior_rows,'frame_known_count':frame_known,'frame_pending_count':len(runners)-frame_known,'missing_master_count':len(set(missing)),'policy':'heavy detail exists only for verified upcoming JRA runners'},'runners':runners};OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');STATUS.write_text(json.dumps({**payload['summary'],'errors':errors,'missing_master_ids':sorted(set(missing))},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(payload['summary'],ensure_ascii=False))
if __name__=='__main__':main()
