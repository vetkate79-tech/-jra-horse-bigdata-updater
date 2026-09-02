#!/usr/bin/env python3
import json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Tokyo')
SEAL=Path('docs/data/live_predictions_sealed.json')
CARDS=Path('docs/data/race_cards.json')
OUT=Path('docs/data/market_watch_status.json')
now=datetime.now(TZ)

POLICY={
    'prerequisite':'market layer starts only for races present in the pure-prediction seal',
    'thursday':'pure prediction/seal first; no market influence on ability ranking',
    'friday_morning':'pure prediction only',
    'after_friday_noon':'market checkpoint every 12h',
    'race_day':'market checkpoint every 3h',
    'race_relative':['T-60','T-30','T-10'],
    'firewall':'odds never change ability ranking; only value/purchase judgment',
    'final_ticket_rule':'final ticket status stays MARKET_DATA_PENDING until real market data is connected; never fabricate odds or EV'
}

def _load(p,default):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return default

def _clock(v):
    s=str(v or '').strip()
    m=re.search(r'(\d{1,2})\s*[時:]\s*(\d{1,2})',s)
    if m:return f'{int(m.group(1)):02d}:{int(m.group(2)):02d}'
    m=re.match(r'^(\d{1,2}):(\d{2})$',s)
    return f'{int(m.group(1)):02d}:{int(m.group(2)):02d}' if m else None

def parse_dt(r):
    d=r.get('date') or r.get('race_date');t=_clock(r.get('start_time') or r.get('scheduled_start'))
    if not d or not t:return None
    try:return datetime.fromisoformat(f'{d}T{t}:00').replace(tzinfo=TZ)
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

seal=_load(SEAL,{'races':[],'prediction_hash_sha256':None})
cards=_load(CARDS,{'races':[]})
card_by_id={str(x.get('race_id')):x for x in cards.get('races',[])}
rows=[]
for p in seal.get('races',[]):
    rid=str(p.get('race_id') or '')
    c=card_by_id.get(rid,{})
    r={**p,'start_time':c.get('start_time')}
    is_due,reason=due(r)
    rows.append({
        'race_id':rid,'date':r.get('date'),'track':r.get('track'),'race_no':r.get('race_no'),
        'start_time':r.get('start_time'),'prediction_sealed':True,
        'prediction_hash_sha256':seal.get('prediction_hash_sha256'),
        'phase':phase_for(r),'market_check_due':is_due,'checkpoint':reason,
        'market_data_status':'PENDING_EXTERNAL_MARKET_DATA' if is_due else 'NOT_DUE',
        'final_ticket_status':'MARKET_DATA_PENDING' if is_due else 'PRE_MARKET'
    })
semantic={'policy':POLICY,'sealed_prediction_hash':seal.get('prediction_hash_sha256'),'races':rows}
old=_load(OUT,{})
old_semantic={'policy':old.get('policy'),'sealed_prediction_hash':old.get('sealed_prediction_hash'),'races':old.get('races')}
changed=old_semantic!=semantic
if changed:
    OUT.write_text(json.dumps({'checked_at':now.isoformat(),**semantic},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checked_at':now.isoformat(),'sealed_races':len(rows),'market_due':sum(x['market_check_due'] for x in rows),'state_changed':changed},ensure_ascii=False))
