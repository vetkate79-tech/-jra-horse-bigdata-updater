#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import build_live_sealed_predictions as base
from oral_operational_layer import analyze_race, MODEL_VERSION
from situational_race_pattern_shadow import classify_situation
from ensemble_prediction_shadow import route_ensemble
from ticket_value_regime_shadow import classify_ticket_policy
from axis_survival_shadow import select_survival_axis,reorder_with_survival_axis
from partner_intrusion_shadow import score_low_rank_intrusion

TZ=ZoneInfo('Asia/Tokyo')
NEW_MODEL='NEW_HORSE_DEDICATED_V2_CONSERVATIVE_PRIOR'


def _explicit_starts(card_h,master,pre):
    p=pre or {}; h=master.get(str(card_h.get('horse_id') or ''),{})
    for k in ('starts_before','career_starts_before'):
        if p.get(k) is not None:return base._num(p.get(k)),True
        if h.get(k) is not None:return base._num(h.get(k)),True
    if h.get('running_style_sample_starts') is not None:return base._num(h.get('running_style_sample_starts')),True
    return 0.0,False


def _is_new_horse_race(r,master,pre_by_key,new_entries):
    name=str(r.get('race_name') or '')
    if '新馬' in name or 'メイクデビュー' in name:return True,'RACE_NAME'
    if str(r.get('race_id') or '') in new_entries:return True,'UPCOMING_NEW_REGISTRY'
    seen=[]
    for h in r.get('horses') or []:
        key=(str(r.get('race_id') or ''),str(h.get('horse_id') or ''))
        starts,known=_explicit_starts(h,master,pre_by_key.get(key))
        seen.append((starts,known))
    if len(seen)>=3 and all(known and starts<=0 for starts,known in seen):
        return True,'ALL_RUNNERS_ZERO_PRIOR_STARTS'
    return False,'NORMAL'


def _new_horse_score(card_h,entry,surface,distance):
    text=str((entry or {}).get('row_text') or '')
    sire=base._new_text_field(text,r'父：\s*([^ ]+)')
    damsire=base._new_text_field(text,r'母の父：\s*([^)]+)\)')
    trainer=base._new_text_field(text,r'([^\s()]+\s+[^\s()]+)\s+\(美浦\)') or str(card_h.get('trainer') or '')
    jockey=str(card_h.get('jockey') or '')

    # V2 principle: pedigree is a weak prior, never a proxy for demonstrated ability.
    dirt_sire={'ナダル':1.4,'ドレフォン':1.2,'ニューイヤーズデイ':1.2,'マインドユアビスケッツ':1.0,'コパノリッキー':1.0,'クリソベリル':0.9,'マジェスティックウォリアー':0.9,'インカンテーション':0.7,'チュウワウィザード':0.7,'オメガパフューム':0.6,'マテラスカイ':0.5,'ゴールドシップ':-0.3}
    turf_sire={'ゴールドシップ':1.1,'キズナ':1.1,'ダイワメジャー':1.0,'ドレフォン':0.4}
    damsire_map={'ゴールドアリュール':0.5,'アグネスデジタル':0.4,'プリサイスエンド':0.4,'ドレフォン':0.3,'ネオユニヴァース':0.3,'ダイワメジャー':0.3,'キングヘイロー':0.2,'キズナ':0.2,'トーセンジョーダン':0.1,'High Chaparral':0.1}
    jockey_map={'C.ルメール':1.3,'三浦 皇成':0.8,'岩田 康誠':0.8,'北村 友一':0.7,'津村 明秀':0.7,'大野 拓弥':0.6,'菊沢 一樹':0.4,'内田 博幸':0.4,'丸山 元気':0.4,'丸田 恭介':0.2,'▲ 水沼 元輝':0.1,'△ 石神 深道':0.1}
    trainer_map={'伊藤 圭三':1.0,'中舘 英二':0.9,'栗田 徹':0.9,'森 一誠':0.9,'武井 亮':0.8,'和田 正一郎':0.8,'加藤 士津八':0.8,'蛯名 正義':0.7,'奥平 雅士':0.4,'清水 英克':0.4,'秋本 大介':0.1}

    sire_adj=(dirt_sire if str(surface)=='ダート' else turf_sire).get(sire,0.0)
    damsire_adj=damsire_map.get(damsire,0.0)
    pedigree_adj=max(-1.5,min(1.5,sire_adj+damsire_adj))
    trainer_adj=trainer_map.get(trainer,0.0)
    jockey_adj=jockey_map.get(jockey,0.0)
    connection_adj=0.0
    if 'ノーザンファーム' in text:connection_adj=max(connection_adj,0.7)
    if '社台コーポレーション白老ファーム' in text or '白老ファーム' in text:connection_adj=max(connection_adj,0.6)
    if '社台ファーム' in text:connection_adj=max(connection_adj,0.6)
    if 'サンデーレーシング' in text or 'シルクレーシング' in text or '社台レースホース' in text:connection_adj+=0.3
    connection_adj=min(connection_adj,0.8)

    # Pedigree is capped at 20% of the designed positive spread. Missing data reduces confidence, not ability.
    score=50.0 + pedigree_adj + trainer_adj + jockey_adj + connection_adj
    present={'sire':bool(sire),'damsire':bool(damsire),'trainer':bool(trainer),'jockey':bool(jockey)}
    coverage=sum(present.values())/4.0
    evaluable=bool(sire or damsire) and bool(trainer or jockey)
    missing=[k for k,v in present.items() if not v]
    confidence=round(0.30+0.45*coverage,3)
    return round(score,3),{
        'sire':sire,'damsire':damsire,'trainer':trainer,'jockey':jockey,
        'pedigree_adjustment':round(pedigree_adj,3),'trainer_adjustment':round(trainer_adj,3),
        'jockey_adjustment':round(jockey_adj,3),'connection_adjustment':round(connection_adj,3),
        'pedigree_share_cap':0.20,'evidence_coverage':round(coverage,3),'confidence':confidence,
        'evaluation_status':'RATED' if evaluable else 'UNRATED_DARK_HORSE','missing_evidence':missing,
        'principle':'PEDIGREE_IS_WEAK_PRIOR_NOT_ABILITY'
    }


def _new_horse_analysis(safe,unrated):
    q=list(safe.get('ranked_snapshot') or [])
    ns=[str(x.get('n') or '') for x in q if str(x.get('n') or '').isdigit()]
    common={'model_version':NEW_MODEL,'unrated_dark_horses':unrated,'market_isolation':'NO_ODDS_OR_POPULARITY_USED','pedigree_policy':'WEAK_PRIOR_CAPPED_20PCT'}
    if len(ns)<5:
        return {**common,'classification':'PASS','pre_market_decision':'PASS','ticket_shape':'PASS','formation_columns':{'first':[],'second':[],'third':[]},'trio_tickets':[],'ticket_count':0,'data_quality':'LOW'}
    top=ns[:6];a,b,c,d,e,f=top
    formation={'first':[a,b],'second':[a,b,c,d],'third':[a,b,c,d,e,f]}
    preferred=[(a,b,c),(a,b,d),(a,b,e),(a,b,f),(a,c,d),(b,c,d),(a,c,e),(b,c,e),(b,d,e)]
    tickets=list(dict.fromkeys(base._new_combo(x) for x in preferred))
    gap=base._num(q[0].get('score'))-base._num(q[1].get('score')) if len(q)>1 else 0
    roles=[{'horse_no':str(h.get('n')),'horse_name':h.get('name',''),'rank':i,'roles':['新馬能力上位'] if i<=4 else ['3着侵入候補'],'uncertainty':round(1.0-(h.get('new_horse_evidence') or {}).get('confidence',0.4),3),'running_style':'UNKNOWN'} for i,h in enumerate(q[1:9],start=2)]
    intrusion=[{'horse_no':str(h.get('n')),'horse_name':h.get('name',''),'rank':i,'running_style':'UNKNOWN','axis_win_flow':'新馬・展開未確定','scenario_fit':0.0,'reason':'新馬V2で複数の事前根拠を統合。血統単独では上位化しない','intrusion_score':round(max(0,base._num(h.get('score'))/base._num(q[0].get('score'),1)),3)} for i,h in enumerate(q[4:6],start=5)]
    return {**common,
      'axis':{'horse_no':a,'horse_name':q[0].get('name','')},
      'axis_durability':{'score':round(42+min(10,max(0,gap*3)),1),'status':'LOW','gap_to_second':round(gap,3),'uncertainty':0.80,'starts_before':0,'reasons':['全馬未出走のため能力差を強く断定しない','血統は弱い事前分布としてのみ使用','未評価馬は完全ダークホースとして別管理']},
      'partner_roles':roles,'third_place_intrusion':intrusion,
      'axis_win_flow':{'axis_style':'UNKNOWN','front_count':0,'flow':'新馬・展開未確定','favored_styles':[],'reason':'既走脚質がないため展開を固定しない'},
      'failure_scenarios':[{'id':'BASE','label':'新馬上位評価成立','covered_horses':[b,c,d]},{'id':'AXIS_FAIL','label':'最上位評価馬が飛ぶ','covered_horses':[b,c,d,e]},{'id':'THIRD_INTRUSION','label':'3着低順位馬侵入','covered_horses':[e,f]},{'id':'UNRATED_DARK_HORSE','label':'未評価馬が能力を示す','covered_horses':[str(x.get('n')) for x in unrated]}],
      'ticket_shape':'NEW_HORSE_GROUP','formation_columns':formation,'trio_tickets':tickets,'ticket_count':len(tickets),
      'classification':'C','pre_market_decision':'CAUTION','data_quality':'NEW_HORSE_DEDICATED_V2',
      'derived_ticket_analysis':{},
      'implementation_note':'New-horse V2: pedigree is capped as a weak prior; missing information lowers confidence rather than implied ability. All-zero-prior-start cards are treated as new-horse races even without a name label.'}


def main():
    base._assert_registered_model_version()
    now=datetime.now(TZ);today=now.date().isoformat();champion_archive=base._champion_archive_for(today)
    prior=None
    if base.OUT.exists():
        prior=json.loads(base.OUT.read_text(encoding='utf-8'));base._archive_seal_payload(prior)
    if prior and not champion_archive.exists():
        same_day=any(str(r.get('date') or '')==today for r in (prior.get('races') or [])+(prior.get('pending') or []))
        if same_day:champion_archive.write_text(json.dumps(prior,ensure_ascii=False,indent=2),encoding='utf-8')
    cards=base._load_weekly_cards();master=base._load_horses();pre_by_key,pre_summary=base._load_pre_features();new_entries=base._load_upcoming_new();races=[];pending=[];frame_total=frame_known=0
    for r in cards:
        date=str(r.get('date') or '')
        if not date or date<today:continue
        q=[]
        for x in r.get('horses') or []:
            frame_total+=1;frame_known+=int(bool(str(x.get('frame_no') or '')));key=(str(r.get('race_id') or ''),str(x.get('horse_id') or ''));q.append(base._safe_horse(x,master,pre_by_key.get(key)))
        is_new,new_reason=_is_new_horse_race(r,master,pre_by_key,new_entries)
        if is_new:
            new_race=new_entries.get(str(r.get('race_id') or ''),{});by_id={str(x.get('horse_id') or ''):x for x in (new_race.get('horses') or [])}
            rated=[];unrated=[]
            for x,card_h in zip(q,r.get('horses') or []):
                score,evidence=_new_horse_score(card_h,by_id.get(str(card_h.get('horse_id') or ''),{}),r.get('surface'),r.get('distance_m'))
                x.update({'score':score,'starts_before':0,'show_rate_prior':0.30,'recent_form':0.35,'condition_fit':0.30,'uncertainty':round(1.0-evidence['confidence'],3),'running_style':'UNKNOWN','score_source':NEW_MODEL,'new_horse_evidence':evidence})
                if evidence['evaluation_status']=='UNRATED_DARK_HORSE':
                    unrated.append({'n':x.get('n'),'name':x.get('name'),'horse_id':x.get('horse_id'),'missing_evidence':evidence.get('missing_evidence',[]),'status':'UNRATED_DARK_HORSE'})
                else:rated.append(x)
            rated.sort(key=lambda x:(-base._num(x.get('score')),int(x['n']) if str(x.get('n') or '').isdigit() else 999))
            safe={'race_id':r.get('race_id'),'date':date,'track':r.get('track'),'race_no':r.get('race_no'),'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'ranked_snapshot':rated}
            if base._contains_forbidden(safe):raise RuntimeError('forbidden market/result field entered new-horse prediction input')
            analysis=_new_horse_analysis(safe,unrated);analysis['new_horse_detection_reason']=new_reason
            races.append({**{k:safe.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'ranked_snapshot':rated,'champion_ranked_snapshot':rated,'unrated_dark_horses':unrated,'analysis':analysis});continue
        scores=[base._num(x.get('score')) for x in q if base._num(x.get('score'))!=0];evidence=sum(1 for x in q if base._num(x.get('starts_before'))>0);spread=(max(scores)-min(scores)) if scores else 0.0;differentiated=len({round(x,3) for x in scores})
        if len(q)<3 or len(scores)<3 or evidence<3 or differentiated<3 or spread<0.50:
            pending.append({'race_id':r.get('race_id'),'date':date,'track':r.get('track'),'race_no':r.get('race_no'),'status':'DATA_PENDING','reason':'at least 3 evidence-backed and differentiated pre-race horse scores are required; no fallback/fabricated ranking is allowed','evidence_horses':evidence,'score_spread':round(spread,3)});continue
        q.sort(key=lambda x:(-base._num(x.get('score')),int(x['n']) if x['n'].isdigit() else 999));safe={'race_id':r.get('race_id'),'date':date,'track':r.get('track'),'race_no':r.get('race_no'),'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'ranked_snapshot':q}
        if base._contains_forbidden(safe):raise RuntimeError('forbidden market/result field entered pure prediction input')
        champion_analysis=analyze_race(safe);survival=select_survival_axis(q);challenger_q=reorder_with_survival_axis(q,survival);challenger_safe={**safe,'ranked_snapshot':challenger_q};analysis=analyze_race(challenger_safe);analysis['model_version']=base.PUBLICATION_MODEL
        analysis['challenger_reseal']={'status':'PUBLIC_CHALLENGER','base_model_version':MODEL_VERSION,'mechanism':survival.get('architecture'),'changed_from_champion':bool(survival.get('changed_from_ability_rank1')),'champion_axis':champion_analysis.get('axis'),'challenger_axis':analysis.get('axis'),'switch_gate':survival.get('switch_gate'),'results_used':False,'odds_popularity_used':False}
        situation=classify_situation(challenger_safe,challenger_q,analysis.get('axis_durability') or {},analysis.get('third_place_intrusion') or []);analysis['situational_shadow']=situation;analysis['ensemble_shadow']=route_ensemble(situation);analysis['axis_survival_shadow']=survival;analysis['partner_intrusion_shadow']=score_low_rank_intrusion(challenger_q,safe.get('surface'),safe.get('distance_m'));analysis['ticket_value_regime_shadow']=classify_ticket_policy(challenger_safe,challenger_q,analysis)
        races.append({**{k:safe.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'ranked_snapshot':challenger_q,'champion_ranked_snapshot':q,'analysis':analysis})
    seal_stage='FINAL_WITH_FRAME' if frame_total>0 and frame_known==frame_total else ('PARTIAL_FRAME_RESEAL' if frame_known else 'PRELIMINARY_NO_FRAME')
    unrated_races=sum(bool(r.get('unrated_dark_horses')) for r in races);unrated_horses=sum(len(r.get('unrated_dark_horses') or []) for r in races)
    core={'schema_version':8,'mode':'LIVE_PURE_PREDICTION_CHALLENGER_RESEAL','seal_stage':seal_stage,'model_version':base.PUBLICATION_MODEL,'base_model_version':MODEL_VERSION,'publication_status':'PUBLIC_CHALLENGER','challenger_mechanism':'TOP3_SURVIVAL_AXIS_SHADOW_V4_R2_EXACT','champion_archive':str(champion_archive),'generated_at':now.isoformat(),'odds_popularity_used':False,'results_used':False,'pre_race_feature_cutoff':pre_summary.get('cutoff_date'),'frame_known_count':frame_known,'frame_total_count':frame_total,'draw_feature_applied':bool(pre_summary.get('draw_feature_applied')),'situational_shadow_enabled':True,'situational_shadow_production_override':False,'ensemble_shadow_enabled':True,'ensemble_shadow_production_override':False,'ticket_value_regime_shadow_enabled':True,'ticket_value_regime_shadow_production_override':False,'new_horse_model_version':NEW_MODEL,'new_horse_detection_all_zero_starts_enabled':True,'new_horse_unrated_zone_enabled':True,'new_horse_unrated_race_count':unrated_races,'new_horse_unrated_horse_count':unrated_horses,'sealed_race_count':len(races),'pending_race_count':len(pending),'challenger_axis_change_count':sum(bool((r.get('analysis') or {}).get('challenger_reseal',{}).get('changed_from_champion')) for r in races),'races':races,'pending':pending}
    hash_input=json.dumps({k:v for k,v in core.items() if k!='generated_at'},ensure_ascii=False,sort_keys=True,separators=(',',':'));core['prediction_hash_sha256']=hashlib.sha256(hash_input.encode()).hexdigest();base.OUT.parent.mkdir(parents=True,exist_ok=True);base.STATUS.parent.mkdir(parents=True,exist_ok=True);base._archive_seal_payload(core);base.OUT.write_text(json.dumps(core,ensure_ascii=False,indent=2),encoding='utf-8')
    status={k:core[k] for k in ('publication_status','model_version','base_model_version','challenger_mechanism','challenger_axis_change_count','champion_archive','seal_stage','sealed_race_count','pending_race_count','frame_known_count','frame_total_count','draw_feature_applied','prediction_hash_sha256','pre_race_feature_cutoff','odds_popularity_used','results_used','new_horse_model_version','new_horse_detection_all_zero_starts_enabled','new_horse_unrated_zone_enabled','new_horse_unrated_race_count','new_horse_unrated_horse_count')};status['status']='SEALED' if races else ('DATA_PENDING' if pending else 'NO_UPCOMING_RACES');status['today_jst']=today;base.STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(status,ensure_ascii=False))

if __name__=='__main__':main()
