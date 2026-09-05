#!/usr/bin/env python3
"""Collect current JRA win odds as an isolated market layer.

This never mutates the sealed pure prediction. It only publishes current
single-win odds and market rank for value inspection.
"""
from __future__ import annotations
import json,re,hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import sys
sys.path.insert(0,'src')
from collect_upcoming_new_horses import fetch, normalize_horse_id
from collect_upcoming_runner_details import canonical_id

TZ=ZoneInfo('Asia/Tokyo')
WEEKLY=Path('docs/data/horses/weekly_runner_details.json')
OUT=Path('docs/data/current_market_odds.json')
STATUS=Path('status/current_market_odds.json')
HISTORY=Path('docs/data/market-odds-history')

def clean(v): return ' '.join(str(v or '').split())

def archive_market_payload(payload):
    if not isinstance(payload,dict) or not payload:return None
    captured=str(payload.get('captured_at') or datetime.now(TZ).isoformat())
    date=captured[:10] if len(captured)>=10 else 'undated'
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    digest=hashlib.sha256(raw).hexdigest()
    d=HISTORY/date;d.mkdir(parents=True,exist_ok=True);p=d/(digest+'.json')
    if not p.exists():p.write_bytes(raw)
    if p.read_bytes()!=raw:raise RuntimeError('market odds history verification failed: '+str(p))
    return str(p)

def extract_win_odds(tr):
    # JRA renders the single-win price as its own numeric table cell.
    # Do not infer from composite text (weight/bodyweight/etc.).
    candidates=[]
    for cell in tr.find_all(['th','td']):
        txt=clean(cell.get_text(' ',strip=True))
        cls=' '.join(cell.get('class') or []).lower()
        if 'odds' in cls:
            m=re.fullmatch(r'(\d{1,4}(?:\.\d)?)',txt)
            if m:return float(m.group(1))
        m=re.fullmatch(r'(\d{1,4}\.\d)',txt)
        if m:
            v=float(m.group(1))
            if 1.0<=v<=9999.9:candidates.append(v)
    # Usually only the win-odds cell is a bare decimal. If multiple bare
    # decimals exist, refuse to guess rather than publish a false price.
    return candidates[0] if len(candidates)==1 else None

def main():
    now=datetime.now(TZ)
    weekly=json.loads(WEEKLY.read_text(encoding='utf-8')) if WEEKLY.exists() else {'runners':[]}
    by_race={}
    for x in weekly.get('runners') or []:
        r=x.get('race') or {}
        if r.get('date')!=now.date().isoformat():continue
        rid=str(r.get('race_id') or '')
        if not rid:continue
        g=by_race.setdefault(rid,{'race':r,'runners':[]})
        g['runners'].append(x)
    races=[];errors=[];total=0
    for rid,g in by_race.items():
        r=g['race'];url=r.get('source_url')
        if not url:continue
        try: raw=fetch(url)
        except Exception as e:
            errors.append({'race_id':rid,'error':repr(e)});continue
        soup=BeautifulSoup(raw,'html.parser')
        odds_by_id={};odds_by_name={}
        for tr in soup.find_all('tr'):
            horse_anchor=None;hid=None
            for a in tr.find_all('a'):
                href=str(a.get('href') or '')
                m=re.search(r'pw01dud\d{12}/[A-Fa-f0-9]{2}',href)
                if m:
                    horse_anchor=a;hid=canonical_id(m.group(0));break
            if not horse_anchor:continue
            name=clean(horse_anchor.get_text(' ',strip=True))
            price=extract_win_odds(tr)
            if price is None:continue
            odds_by_id[hid]=price
            if name:odds_by_name[name]=price
        rows=[]
        for x in g['runners']:
            hid=canonical_id(x.get('horse_id'));name=clean(x.get('horse_name'))
            o=odds_by_id.get(hid,odds_by_name.get(name))
            if o is None:continue
            rows.append({'horse_id':hid,'horse_no':str(x.get('horse_no') or ''),'horse_name':name,'win_odds':o})
        rows.sort(key=lambda x:(x['win_odds'],int(x['horse_no']) if x['horse_no'].isdigit() else 999))
        for i,x in enumerate(rows,1):x['market_rank']=i
        total+=len(rows)
        races.append({'race_id':rid,'date':r.get('date'),'track':r.get('track'),'race_no':r.get('race_no'),'race_name':r.get('race_name'),'source_url':url,'win_odds':rows})
    payload={'source':'JRA_OFFICIAL','market_layer_only':True,'pure_prediction_mutated':False,'odds_type':'WIN','captured_at':now.isoformat(),'race_count':len(races),'runner_odds_count':total,'races':races}
    OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True)
    if OUT.exists():
        try:archive_market_payload(json.loads(OUT.read_text(encoding='utf-8')))
        except Exception as e:raise RuntimeError('refusing to overwrite market odds before archive: '+repr(e))
    archive_market_payload(payload)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    STATUS.write_text(json.dumps({k:v for k,v in payload.items() if k!='races'}|{'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k!='races'}|{'errors':len(errors)},ensure_ascii=False))
if __name__=='__main__':main()
