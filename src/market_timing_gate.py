#!/usr/bin/env python3
"""Evaluate market value as a post-seal, market-only layer.

This module may read the immutable pure-prediction seal and current JRA odds,
but it never rewrites prediction rank, axis, candidates, or tickets.
"""
import json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Tokyo')
SEAL=Path('docs/data/live_predictions_sealed.json')
WEEKLY=Path('docs/data/horses/weekly_runner_details.json')
MARKET=Path('docs/data/current_market_odds.json')
OUT=Path('docs/data/market_watch_status.json')
now=datetime.now(TZ)

POLICY={
    'prerequisite':'market layer starts only after pure prediction is sealed',
    'fixed_snapshots_jst':['09:00','13:00'],
    'firewall':'odds/popularity never change ability ranking, axis, candidates, or pure tickets',
    'final_ticket_status':'MARKET_DATA_PENDING until market-only purchase judgement is completed',
    'honesty_rule':'never fabricate odds or EV; missing market data remains explicitly pending',
    'value_definition':'compare sealed AI rank with current market rank; positive rank_gap means AI rates the horse higher than market',
    'labels':{
        'HIGH_VALUE':'AI順位が市場順位より3以上上かつ単勝5倍以上',
        'VALUE':'AI順位が市場順位より2以上上',
        'FAIR':'AI順位と市場順位が概ね一致',
        'OVERBOUGHT':'市場順位がAI順位より2以上上',
    }
}

def _load(p,default):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return default

def _clock(v):
    s=str(v or '').strip()
    m=re.search(r'(\d{1,2})\s*[時:]\s*(\d{1,2})',s)
    if m:return f'{int(m.group(1)):02d}:{int(m.group(2)):02d}'
    return None

def _race_key(r):
    return (str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0))

seal=_load(SEAL,{'races':[],'prediction_hash_sha256':None})
weekly=_load(WEEKLY,{'runners':[]})
market=_load(MARKET,{'races':[],'captured_at':None,'runner_odds_count':0})

weekly_by={}
for x in weekly.get('runners') or []:
    r=x.get('race') or {}
    k=_race_key(r)
    if k[0] and k[1] and k[2]:
        weekly_by[k]=r

market_by={_race_key(r):r for r in market.get('races') or []}

rows=[]
for p in seal.get('races') or []:
    k=_race_key(p)
    card=weekly_by.get(k,{})
    mr=market_by.get(k,{})
    odds_rows=mr.get('win_odds') or []
    odds_by_no={str(x.get('horse_no') or ''):x for x in odds_rows}
    odds_by_id={str(x.get('horse_id') or ''):x for x in odds_rows}
    odds_by_name={str(x.get('horse_name') or ''):x for x in odds_rows}

    a=p.get('analysis') or {}
    ranked=p.get('ranked_snapshot') or a.get('ranked_snapshot') or []
    evaluations=[]
    for idx,h in enumerate(ranked,1):
        horse_no=str(h.get('n') or h.get('horse_no') or '')
        horse_id=str(h.get('horse_id') or '')
        horse_name=str(h.get('name') or h.get('horse_name') or '')
        o=odds_by_id.get(horse_id) or odds_by_no.get(horse_no) or odds_by_name.get(horse_name)
        if not o:continue
        market_rank=int(o.get('market_rank') or 0) or None
        win_odds=float(o.get('win_odds')) if o.get('win_odds') is not None else None
        rank_gap=(market_rank-idx) if market_rank is not None else None
        if rank_gap is not None and rank_gap>=3 and win_odds is not None and win_odds>=5:
            label='HIGH_VALUE';jp='妙味高'
        elif rank_gap is not None and rank_gap>=2:
            label='VALUE';jp='妙味あり'
        elif rank_gap is not None and rank_gap<=-2:
            label='OVERBOUGHT';jp='市場先行'
        else:
            label='FAIR';jp='妥当'
        evaluations.append({
            'horse_no':horse_no,'horse_id':horse_id,'horse_name':horse_name,
            'sealed_ai_rank':idx,'market_rank':market_rank,'win_odds':win_odds,
            'rank_gap':rank_gap,'value_label':label,'value_label_ja':jp,
            'reason':(
                f'AI{idx}位に対し市場{market_rank}位。市場よりAI評価が{rank_gap}段階高い。'
                if rank_gap is not None and rank_gap>0 else
                f'AI{idx}位と市場{market_rank}位の差は小さい。'
                if rank_gap is not None and abs(rank_gap)<=1 else
                f'AI{idx}位に対し市場{market_rank}位。市場評価がAIより{abs(rank_gap)}段階高い。'
                if rank_gap is not None else '市場順位未取得'
            )
        })

    rows.append({
        'race_id':p.get('race_id'),'date':k[0],'track':k[1],'race_no':k[2],
        'start_time':_clock(card.get('start_time')),
        'prediction_sealed':True,
        'prediction_hash_sha256':seal.get('prediction_hash_sha256'),
        'market_snapshot_captured_at':market.get('captured_at'),
        'market_data_status':'CONNECTED' if evaluations else 'NO_MATCHED_MARKET_DATA',
        'runner_market_count':len(evaluations),
        'value_evaluations':evaluations,
        'high_value_horses':[x for x in evaluations if x['value_label']=='HIGH_VALUE'],
        'value_horses':[x for x in evaluations if x['value_label'] in ('HIGH_VALUE','VALUE')],
        'firewall_ok':market.get('pure_prediction_mutated') is False,
    })

payload={
    'checked_at':now.isoformat(),
    'policy':POLICY,
    'sealed_prediction_hash':seal.get('prediction_hash_sha256'),
    'market_snapshot':{
        'captured_at':market.get('captured_at'),
        'snapshot_slot':market.get('snapshot_slot'),
        'race_count':market.get('race_count'),
        'runner_odds_count':market.get('runner_odds_count'),
        'pure_prediction_mutated':market.get('pure_prediction_mutated'),
    },
    'race_count':len(rows),
    'races':rows,
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'race_count':len(rows),'market_runner_count':sum(x['runner_market_count'] for x in rows),'market_captured_at':market.get('captured_at'),'firewall_ok':market.get('pure_prediction_mutated') is False},ensure_ascii=False))
