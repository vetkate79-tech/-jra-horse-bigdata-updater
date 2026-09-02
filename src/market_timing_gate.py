#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Tokyo')
DATA=Path('docs/data/dashboard.json')
OUT=Path('docs/data/market_watch_status.json')
now=datetime.now(TZ)

POLICY={
    'thursday':'publish all races immediately without odds',
    'friday_morning':'pure prediction only',
    'after_friday_noon':'odds check every 12h',
    'race_day':'odds check every 3h',
    'race_relative':['T-60','T-30','T-10'],
    'firewall':'odds never change ability ranking; only value/purchase judgment'
}

def parse_dt(r):
    d=r.get('race_date') or r.get('date')
    t=r.get('start_time') or r.get('scheduled_start')
    if not d or not t:return None
    try:return datetime.fromisoformat(f'{d}T{t}').replace(tzinfo=TZ)
    except:return None

def phase_for(r):
    dt=parse_dt(r)
    if not dt:return 'DATA_PENDING'
    if now.weekday()==3:return 'PURE_PREDICTION'
    if now.weekday()==4 and now.hour<12:return 'PURE_PREDICTION'
    if now.date()<dt.date():return 'VALUE_WATCH_12H'
    mins=(dt-now).total_seconds()/60
    if mins<0:return 'STARTED'
    if mins<=10:return 'T_MINUS_10'
    if mins<=30:return 'T_MINUS_30'
    if mins<=60:return 'T_MINUS_60'
    return 'RACE_DAY_3H'

def due(r):
    dt=parse_dt(r)
    if not dt:return False,'NO_START_TIME'
    p=phase_for(r)
    if p in ('PURE_PREDICTION','STARTED','DATA_PENDING'):return False,p
    mins=(dt-now).total_seconds()/60
    if p=='T_MINUS_10':return 0<=mins<=10,'T_MINUS_10'
    if p=='T_MINUS_30':return 10<mins<=30,'T_MINUS_30'
    if p=='T_MINUS_60':return 30<mins<=60,'T_MINUS_60'
    if p=='RACE_DAY_3H':return now.hour%3==0 and now.minute<10,'RACE_DAY_3H'
    if p=='VALUE_WATCH_12H':return now.hour in (0,12) and now.minute<10,'VALUE_WATCH_12H'
    return False,p

raw=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else {'races':[]}
rows=[]
for r in raw.get('races',[]):
    is_due,reason=due(r)
    rows.append({
        'race_id':r.get('race_id'),'track':r.get('track'),'race_no':r.get('race_no'),
        'start_time':r.get('start_time'),'phase':phase_for(r),
        'odds_check_due':is_due,'checkpoint':reason
    })

semantic={'policy':POLICY,'races':rows}
old={}
if OUT.exists():
    try:old=json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:old={}
old_semantic={'policy':old.get('policy'),'races':old.get('races')}
changed=old_semantic!=semantic
if changed:
    OUT.write_text(json.dumps({'checked_at':now.isoformat(),**semantic},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checked_at':now.isoformat(),'races':len(rows),'due':sum(x['odds_check_due'] for x in rows),'state_changed':changed},ensure_ascii=False))
