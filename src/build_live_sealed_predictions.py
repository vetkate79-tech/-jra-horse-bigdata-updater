#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from oral_operational_layer import analyze_race, MODEL_VERSION

TZ=ZoneInfo('Asia/Tokyo')
CARDS=Path('docs/data/race_cards.json')
CATALOG=Path('docs/data/horses/catalog.json')
BASE=Path('docs/data/horses/base_catalog.json')
OUT=Path('docs/data/live_predictions_sealed.json')
STATUS=Path('status/live_prediction_seal.json')

FORBIDDEN_KEYS={'odds','popularity','market_rank','payout','return_amount','result','finish_position','trio_result','trio_payout'}

def _num(v,d=0.0):
    try:return float(v)
    except:return d

def _load_horses():
    for p in (CATALOG,BASE):
        if not p.exists():continue
        try:d=json.loads(p.read_text(encoding='utf-8'))
        except Exception:continue
        hs=d.get('horses') or []
        if hs:return {str(h.get('horse_id') or ''):h for h in hs}
    return {}

def _safe_horse(card_h,master):
    h=master.get(str(card_h.get('horse_id') or ''),{})
    # Only stable/pre-race fields. Latest target-result fields are deliberately ignored.
    starts=_num(h.get('starts_before') or h.get('running_style_sample_starts'),0)
    show=_num(h.get('show_rate_prior'),0.30)
    recent=_num(h.get('recent_form'),0.35)
    cond=_num(h.get('condition_fit'),0.30)
    unc=_num(h.get('uncertainty'), 1.0 if starts<1 else (0.75 if starts<3 else 0.5))
    # If richer safe scores are absent, do not fabricate differentiation.
    explicit_score=h.get('pre_race_score')
    score=_num(explicit_score,0.0) if explicit_score is not None else 0.0
    style=h.get('pre_race_running_style') or None
    return {
      'n':str(card_h.get('n') or ''),'name':card_h.get('name') or '',
      'horse_id':card_h.get('horse_id'),'score':score,
      'starts_before':starts,'show_rate_prior':show,'recent_form':recent,
      'condition_fit':cond,'uncertainty':unc,'running_style':style
    }

def _contains_forbidden(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            if str(k).lower() in FORBIDDEN_KEYS:return True
            if _contains_forbidden(v):return True
    elif isinstance(obj,list):return any(_contains_forbidden(x) for x in obj)
    return False

def main():
    now=datetime.now(TZ)
    today=now.date().isoformat()
    cards=json.loads(CARDS.read_text(encoding='utf-8')) if CARDS.exists() else {'races':[]}
    master=_load_horses()
    races=[];pending=[]
    for r in cards.get('races',[]):
        date=str(r.get('date') or '')
        if not date or date<today:continue
        q=[_safe_horse(x,master) for x in (r.get('horses') or [])]
        # Live production prediction must have real differentiated pre-race evidence.
        scored=sum(1 for x in q if _num(x.get('score'))!=0)
        if len(q)<3 or scored<3:
            pending.append({'race_id':r.get('race_id'),'date':date,'track':r.get('track'),'race_no':r.get('race_no'),'status':'DATA_PENDING','reason':'at least 3 differentiated pre-race horse scores are required; no fallback/fabricated ranking is allowed'})
            continue
        q.sort(key=lambda x:(-_num(x.get('score')),int(x['n']) if x['n'].isdigit() else 999))
        safe={'race_id':r.get('race_id'),'date':date,'track':r.get('track'),'race_no':r.get('race_no'),'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'ranked_snapshot':q}
        if _contains_forbidden(safe):raise RuntimeError('forbidden market/result field entered pure prediction input')
        analysis=analyze_race(safe)
        races.append({**{k:safe.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'analysis':analysis})
    core={'schema_version':1,'mode':'LIVE_PURE_PREDICTION_SEAL','model_version':MODEL_VERSION,'generated_at':now.isoformat(),'odds_popularity_used':False,'results_used':False,'sealed_race_count':len(races),'pending_race_count':len(pending),'races':races,'pending':pending}
    hash_input=json.dumps({k:v for k,v in core.items() if k!='generated_at'},ensure_ascii=False,sort_keys=True,separators=(',',':'))
    core['prediction_hash_sha256']=hashlib.sha256(hash_input.encode()).hexdigest()
    OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(core,ensure_ascii=False,indent=2),encoding='utf-8')
    status={'status':'SEALED' if races else ('DATA_PENDING' if pending else 'NO_UPCOMING_RACES'),'today_jst':today,'sealed_race_count':len(races),'pending_race_count':len(pending),'prediction_hash_sha256':core['prediction_hash_sha256'],'odds_popularity_used':False,'results_used':False}
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False))

if __name__=='__main__':main()
