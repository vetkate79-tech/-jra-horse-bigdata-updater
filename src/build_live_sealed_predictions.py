#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from oral_operational_layer import analyze_race, MODEL_VERSION
from situational_race_pattern_shadow import classify_situation
from ensemble_prediction_shadow import route_ensemble

TZ=ZoneInfo('Asia/Tokyo')
WEEKLY=Path('docs/data/horses/weekly_runner_details.json')
CATALOG=Path('docs/data/horses/catalog.json')
BASE=Path('docs/data/horses/base_catalog.json')
PRE=Path('docs/data/horses/pre_race_features.json')
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

def _load_pre_features():
    if not PRE.exists():return {},{}
    try:d=json.loads(PRE.read_text(encoding='utf-8'))
    except Exception:return {},{}
    summary=d.get('summary') or {}
    if summary.get('results_on_or_after_cutoff_used') not in (False,None):raise RuntimeError('pre-race feature leakage gate failed')
    if summary.get('odds_popularity_used') not in (False,None):raise RuntimeError('market data entered pre-race features')
    by_key={}
    for x in d.get('features') or []:
        key=(str(x.get('race_id') or ''),str(x.get('horse_id') or ''))
        if all(key):by_key[key]=x
    return by_key,summary

def _load_weekly_cards():
    if not WEEKLY.exists():return []
    try:d=json.loads(WEEKLY.read_text(encoding='utf-8'))
    except Exception:return []
    groups={}
    for x in d.get('runners') or []:
        r=x.get('race') or {};rid=str(r.get('race_id') or '')
        if not rid:continue
        card=groups.setdefault(rid,{**{k:r.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'horses':[]})
        card['horses'].append({'n':str(x.get('horse_no') or ''),'frame_no':str(x.get('frame_no') or ''),'name':x.get('horse_name') or '','horse_id':x.get('horse_id')})
    return sorted(groups.values(),key=lambda r:(str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0)))

def _safe_horse(card_h,master,pre=None):
    h=master.get(str(card_h.get('horse_id') or ''),{});p=pre or {}
    starts=_num(p.get('starts_before'),_num(h.get('starts_before') or h.get('running_style_sample_starts'),0));show=_num(p.get('show_rate_prior'),_num(h.get('show_rate_prior'),0.30));recent=_num(p.get('recent_form'),_num(h.get('recent_form'),0.35));cond=_num(p.get('condition_fit'),_num(h.get('condition_fit'),0.30));unc=_num(p.get('uncertainty'),_num(h.get('uncertainty'),1.0 if starts<1 else (0.75 if starts<3 else 0.5)));explicit_score=p.get('pre_race_score') if p.get('pre_race_score') is not None else h.get('pre_race_score');score=_num(explicit_score,0.0) if explicit_score is not None else 0.0;style=p.get('pre_race_running_style') or h.get('pre_race_running_style') or h.get('running_style') or None
    return {'n':str(card_h.get('n') or ''),'frame_no':str(card_h.get('frame_no') or ''),'name':card_h.get('name') or '','horse_id':card_h.get('horse_id'),'score':score,'starts_before':starts,'show_rate_prior':show,'recent_form':recent,'condition_fit':cond,'uncertainty':unc,'running_style':style,'draw_show_prior':p.get('draw_show_prior'),'draw_history_starts':p.get('draw_history_starts'),'score_source':p.get('pre_race_score_source') or ('HORSE_MASTER' if explicit_score is not None else 'MISSING')}

def _contains_forbidden(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            if str(k).lower() in FORBIDDEN_KEYS:return True
            if _contains_forbidden(v):return True
    elif isinstance(obj,list):return any(_contains_forbidden(x) for x in obj)
    return False

def main():
    now=datetime.now(TZ);today=now.date().isoformat();cards=_load_weekly_cards();master=_load_horses();pre_by_key,pre_summary=_load_pre_features();races=[];pending=[];frame_total=frame_known=0
    for r in cards:
        date=str(r.get('date') or '')
        if not date or date<today:continue
        q=[]
        for x in (r.get('horses') or []):
            frame_total+=1;frame_known+=int(bool(str(x.get('frame_no') or '')));key=(str(r.get('race_id') or ''),str(x.get('horse_id') or ''));q.append(_safe_horse(x,master,pre_by_key.get(key)))
        scores=[_num(x.get('score')) for x in q if _num(x.get('score'))!=0];evidence=sum(1 for x in q if _num(x.get('starts_before'))>0);spread=(max(scores)-min(scores)) if scores else 0.0;differentiated=len({round(x,3) for x in scores})
        if len(q)<3 or len(scores)<3 or evidence<3 or differentiated<3 or spread<0.50:
            pending.append({'race_id':r.get('race_id'),'date':date,'track':r.get('track'),'race_no':r.get('race_no'),'status':'DATA_PENDING','reason':'at least 3 evidence-backed and differentiated pre-race horse scores are required; no fallback/fabricated ranking is allowed','evidence_horses':evidence,'score_spread':round(spread,3)});continue
        q.sort(key=lambda x:(-_num(x.get('score')),int(x['n']) if x['n'].isdigit() else 999));safe={'race_id':r.get('race_id'),'date':date,'track':r.get('track'),'race_no':r.get('race_no'),'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'ranked_snapshot':q}
        if _contains_forbidden(safe):raise RuntimeError('forbidden market/result field entered pure prediction input')
        analysis=analyze_race(safe);situation=classify_situation(safe,q,analysis.get('axis_durability') or {},analysis.get('third_place_intrusion') or []);analysis['situational_shadow']=situation;analysis['ensemble_shadow']=route_ensemble(situation)
        races.append({**{k:safe.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'ranked_snapshot':q,'analysis':analysis})
    seal_stage='FINAL_WITH_FRAME' if frame_total>0 and frame_known==frame_total else ('PARTIAL_FRAME_RESEAL' if frame_known else 'PRELIMINARY_NO_FRAME')
    core={'schema_version':6,'mode':'LIVE_PURE_PREDICTION_SEAL','seal_stage':seal_stage,'model_version':MODEL_VERSION,'generated_at':now.isoformat(),'odds_popularity_used':False,'results_used':False,'pre_race_feature_cutoff':pre_summary.get('cutoff_date'),'frame_known_count':frame_known,'frame_total_count':frame_total,'draw_feature_applied':bool(pre_summary.get('draw_feature_applied')),'situational_shadow_enabled':True,'situational_shadow_production_override':False,'ensemble_shadow_enabled':True,'ensemble_shadow_production_override':False,'sealed_race_count':len(races),'pending_race_count':len(pending),'races':races,'pending':pending}
    hash_input=json.dumps({k:v for k,v in core.items() if k!='generated_at'},ensure_ascii=False,sort_keys=True,separators=(',',':'));core['prediction_hash_sha256']=hashlib.sha256(hash_input.encode()).hexdigest();OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(core,ensure_ascii=False,indent=2),encoding='utf-8')
    status={'status':'SEALED' if races else ('DATA_PENDING' if pending else 'NO_UPCOMING_RACES'),'seal_stage':seal_stage,'today_jst':today,'sealed_race_count':len(races),'pending_race_count':len(pending),'frame_known_count':frame_known,'frame_total_count':frame_total,'draw_feature_applied':bool(pre_summary.get('draw_feature_applied')),'prediction_hash_sha256':core['prediction_hash_sha256'],'pre_race_feature_cutoff':pre_summary.get('cutoff_date'),'situational_shadow_enabled':True,'situational_shadow_production_override':False,'ensemble_shadow_enabled':True,'ensemble_shadow_production_override':False,'odds_popularity_used':False,'results_used':False};STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(status,ensure_ascii=False))

if __name__=='__main__':main()
