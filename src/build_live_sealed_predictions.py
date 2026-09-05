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
from ticket_value_regime_shadow import classify_ticket_policy
from axis_survival_shadow import select_survival_axis
from axis_survival_shadow import reorder_with_survival_axis
from partner_intrusion_shadow import score_low_rank_intrusion

TZ=ZoneInfo('Asia/Tokyo')
WEEKLY=Path('docs/data/horses/weekly_runner_details.json')
CATALOG=Path('docs/data/horses/catalog.json')
BASE=Path('docs/data/horses/base_catalog.json')
PRE=Path('docs/data/horses/pre_race_features.json')
OUT=Path('docs/data/live_predictions_sealed.json')
STATUS=Path('status/live_prediction_seal.json')
SEAL_HISTORY=Path('docs/data/prediction-seal-history')
UPGRADE_LOG=Path('docs/data/model_upgrade_log.json')
PUBLICATION_MODEL='ORAL_INTEGRATED_V1_2_SHADOW__TOP3_SURVIVAL_R2_CHALLENGER'
FORBIDDEN_KEYS={'odds','popularity','market_rank','payout','return_amount','result','finish_position','trio_result','trio_payout'}

def _archive_seal_payload(payload):
    if not isinstance(payload,dict) or not payload:
        return None
    dates=sorted({
        str(r.get('date') or '')
        for r in (payload.get('races') or [])+(payload.get('pending') or [])
        if str(r.get('date') or '')
    })
    if not dates:
        dates=['undated']
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    digest=str(payload.get('prediction_hash_sha256') or hashlib.sha256(raw).hexdigest())
    written=[]
    for date in dates:
        d=SEAL_HISTORY/date
        d.mkdir(parents=True,exist_ok=True)
        out=d/f'{digest}.json'
        if not out.exists():
            out.write_bytes(raw)
        if out.read_bytes()!=raw:
            raise RuntimeError(f'seal history verification failed: {out}')
        written.append(str(out))
    return written

def _champion_archive_for(date):
    return Path(f'docs/data/live_predictions_champion_{date}.json')

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

def _assert_registered_model_version():
    if not UPGRADE_LOG.exists():
        raise RuntimeError('model upgrade log is missing; production seal is blocked')
    d=json.loads(UPGRADE_LOG.read_text(encoding='utf-8'))
    baseline=str((d.get('baseline') or {}).get('model_version') or '')
    upgrades=d.get('upgrades') or []
    allowed=baseline
    if upgrades:
        latest=upgrades[-1]
        required=('upgrade_id','promoted_at','from_model','to_model','reason_for_change','validation_path','change_summary','promotion_gate','comparison_at_promotion','post_upgrade_health')
        missing=[k for k in required if not latest.get(k)]
        if missing:
            raise RuntimeError('latest complete upgrade log is incomplete: '+','.join(missing))
        allowed=str(latest.get('to_model') or '')
    if str(MODEL_VERSION)!=allowed:
        raise RuntimeError(f'unregistered production model version: {MODEL_VERSION}; expected {allowed}. Complete upgrade evidence must be registered before sealing')

def _contains_forbidden(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            if str(k).lower() in FORBIDDEN_KEYS:return True
            if _contains_forbidden(v):return True
    elif isinstance(obj,list):return any(_contains_forbidden(x) for x in obj)
    return False

def main():
    _assert_registered_model_version()
    now=datetime.now(TZ);today=now.date().isoformat()
    champion_archive=_champion_archive_for(today)
    # Persist the outgoing live seal before any overwrite. Date rollover must
    # never destroy a prior prediction snapshot.
    prior=None
    if OUT.exists():
        prior=json.loads(OUT.read_text(encoding='utf-8'))
        _archive_seal_payload(prior)
    # Preserve the first same-day comparison anchor under a date-specific name.
    if prior and not champion_archive.exists():
        same_day=any(str(r.get('date') or '')==today for r in (prior.get('races') or [])+(prior.get('pending') or []))
        if same_day:
            champion_archive.write_text(json.dumps(prior,ensure_ascii=False,indent=2),encoding='utf-8')
            if json.loads(champion_archive.read_text(encoding='utf-8'))!=prior:
                raise RuntimeError(f'champion archive verification failed: {champion_archive}')
    cards=_load_weekly_cards();master=_load_horses();pre_by_key,pre_summary=_load_pre_features();races=[];pending=[];frame_total=frame_known=0
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
        champion_analysis=analyze_race(safe)
        survival=select_survival_axis(q)
        challenger_q=reorder_with_survival_axis(q,survival)
        challenger_safe={**safe,'ranked_snapshot':challenger_q}
        analysis=analyze_race(challenger_safe)
        analysis['model_version']=PUBLICATION_MODEL
        analysis['challenger_reseal']={
            'status':'PUBLIC_CHALLENGER',
            'base_model_version':MODEL_VERSION,
            'mechanism':survival.get('architecture'),
            'changed_from_champion':bool(survival.get('changed_from_ability_rank1')),
            'champion_axis':champion_analysis.get('axis'),
            'challenger_axis':analysis.get('axis'),
            'switch_gate':survival.get('switch_gate'),
            'results_used':False,
            'odds_popularity_used':False,
        }
        situation=classify_situation(challenger_safe,challenger_q,analysis.get('axis_durability') or {},analysis.get('third_place_intrusion') or []);analysis['situational_shadow']=situation;analysis['ensemble_shadow']=route_ensemble(situation);analysis['axis_survival_shadow']=survival;analysis['partner_intrusion_shadow']=score_low_rank_intrusion(challenger_q,safe.get('surface'),safe.get('distance_m'));analysis['ticket_value_regime_shadow']=classify_ticket_policy(challenger_safe,challenger_q,analysis)
        races.append({**{k:safe.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'ranked_snapshot':challenger_q,'champion_ranked_snapshot':q,'analysis':analysis})
    seal_stage='FINAL_WITH_FRAME' if frame_total>0 and frame_known==frame_total else ('PARTIAL_FRAME_RESEAL' if frame_known else 'PRELIMINARY_NO_FRAME')
    core={'schema_version':7,'mode':'LIVE_PURE_PREDICTION_CHALLENGER_RESEAL','seal_stage':seal_stage,'model_version':PUBLICATION_MODEL,'base_model_version':MODEL_VERSION,'publication_status':'PUBLIC_CHALLENGER','challenger_mechanism':'TOP3_SURVIVAL_AXIS_SHADOW_V4_R2_EXACT','champion_archive':str(champion_archive),'generated_at':now.isoformat(),'odds_popularity_used':False,'results_used':False,'pre_race_feature_cutoff':pre_summary.get('cutoff_date'),'frame_known_count':frame_known,'frame_total_count':frame_total,'draw_feature_applied':bool(pre_summary.get('draw_feature_applied')),'situational_shadow_enabled':True,'situational_shadow_production_override':False,'ensemble_shadow_enabled':True,'ensemble_shadow_production_override':False,'ticket_value_regime_shadow_enabled':True,'ticket_value_regime_shadow_production_override':False,'sealed_race_count':len(races),'pending_race_count':len(pending),'challenger_axis_change_count':sum(bool((r.get('analysis') or {}).get('challenger_reseal',{}).get('changed_from_champion')) for r in races),'races':races,'pending':pending}
    hash_input=json.dumps({k:v for k,v in core.items() if k!='generated_at'},ensure_ascii=False,sort_keys=True,separators=(',',':'));core['prediction_hash_sha256']=hashlib.sha256(hash_input.encode()).hexdigest();OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True)
    _archive_seal_payload(core)
    OUT.write_text(json.dumps(core,ensure_ascii=False,indent=2),encoding='utf-8')
    status={'status':'SEALED' if races else ('DATA_PENDING' if pending else 'NO_UPCOMING_RACES'),'publication_status':'PUBLIC_CHALLENGER','model_version':PUBLICATION_MODEL,'base_model_version':MODEL_VERSION,'challenger_mechanism':core['challenger_mechanism'],'challenger_axis_change_count':core['challenger_axis_change_count'],'champion_archive':str(champion_archive),'seal_stage':seal_stage,'today_jst':today,'sealed_race_count':len(races),'pending_race_count':len(pending),'frame_known_count':frame_known,'frame_total_count':frame_total,'draw_feature_applied':bool(pre_summary.get('draw_feature_applied')),'prediction_hash_sha256':core['prediction_hash_sha256'],'pre_race_feature_cutoff':pre_summary.get('cutoff_date'),'situational_shadow_enabled':True,'situational_shadow_production_override':False,'ensemble_shadow_enabled':True,'ensemble_shadow_production_override':False,'ticket_value_regime_shadow_enabled':True,'ticket_value_regime_shadow_production_override':False,'odds_popularity_used':False,'results_used':False};STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(status,ensure_ascii=False))

if __name__=='__main__':main()
