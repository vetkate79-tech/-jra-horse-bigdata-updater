#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile
from oral_operational_layer import analyze_race
from run_oral_v6_72_sealed_replay import key,parse_profile,hist_features,effective,f,pick_main,pick_holes,make_tickets
from build_oral_v8_72_fullstyle import style_from_samples,diversified_main,holes as style_holes,tickets as style_tickets

CARDS=Path('docs/data/race_cards.json');BASE=Path('docs/data/replay-2026-08-29-30-sealed.json');CACHE=Path('docs/data/pretarget-corner-cache.json')
OUT=Path('docs/data/oral-v10-72-connected-durability-sealed.json');STATUS=Path('status/oral-v10-72-connected-durability-sealed.json');MODEL='ORAL_V10_72_CONNECTED_DURABILITY'

def clamp(v):return max(0.0,min(1.0,float(v)))
def connect_features(feat):
    starts=int(feat.get('history_rows_before') or 0)
    recent=clamp(feat.get('recent_top3_rate') or 0)
    exact=clamp(feat.get('exact_distance_top3_rate') or 0)
    near=clamp(feat.get('near_distance_top3_rate') or 0)
    course=clamp(feat.get('same_course_top3_rate') or 0)
    exact_course=clamp(feat.get('exact_course_top3_rate') or 0)
    if starts==0:
        return {'starts_before':0,'recent_form':.35,'show_rate_prior':.30,'condition_fit':.30,'connected_feature_confidence':0.0}
    show=clamp(.65*recent+.20*exact+.15*near)
    cond=clamp(.35*exact+.20*near+.20*course+.25*exact_course)
    conf=clamp(starts/5)
    return {'starts_before':starts,'recent_form':round(recent,4),'show_rate_prior':round(show,4),'condition_fit':round(cond,4),'connected_feature_confidence':round(conf,3)}

def main():
    cards=json.loads(CARDS.read_text());base=json.loads(BASE.read_text());cache=json.loads(CACHE.read_text());bm={key(r):r for r in base.get('races',[])};styles={hid:style_from_samples(xs) for hid,xs in cache.get('horses',{}).items()}
    ids=sorted({str(h.get('horse_id') or '') for r in cards.get('races',[]) for h in r.get('horses',[]) if h.get('horse_id')});hist={};errs=[]
    def one(i):return i,parse_profile(request_profile(i))
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        fs={ex.submit(one,i):i for i in ids}
        for n,fu in enumerate(concurrent.futures.as_completed(fs),1):
            i=fs[fu]
            try:k,v=fu.result();hist[k]=v
            except Exception as e:hist[i]=[];errs.append({'horse_id':i,'error':repr(e)})
            if n%100==0:print(f'profiles {n}/{len(ids)} errors={len(errs)}',flush=True)
    rows=[];dur_counts={};style_applied=0
    for r in cards.get('races',[]):
        b=bm.get(key(r),{});base_by_id={str(x.get('horse_id') or ''):x for x in b.get('ranked_snapshot',[])};base_floor=min([f(x.get('score'),20) for x in b.get('ranked_snapshot',[])] or [20.0]);hs=[]
        for idx,h in enumerate(r.get('horses',[])):
            hid=str(h.get('horse_id') or '');old=base_by_id.get(hid,{});feat=hist_features(hist.get(hid,[]),str(r['date']),int(r.get('distance_m') or 0),str(r.get('track') or ''));conn=connect_features(feat);base_score=f(old.get('score'),max(12.0,base_floor-.20*(idx+1)));unc=f(old.get('uncertainty'),1.0 if feat['history_rows_before']==0 else max(0.0,1-min(5,feat['history_rows_before'])/5));score=effective(base_score,feat['oral_structure_score'],unc);st=styles.get(hid,{'running_style':'UNKNOWN','running_style_label':'判定待ち','style_sample_starts':0,'position_variance':None})
            hs.append({'n':str(h.get('n')),'name':h.get('name'),'horse_id':hid,'base_score_v1':round(base_score,3),'uncertainty':round(unc,3),'score':score,**feat,**conn,**st})
        hs.sort(key=lambda x:(-f(x['score']),int(x['n'])));rr={**b,'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'ranked_snapshot':hs};a=analyze_race(rr);axis=next((x for x in hs if x['n']==str((a.get('axis') or {}).get('horse_no'))),hs[0] if hs else {})
        dur=(a.get('axis_durability') or {}).get('status','LOW');dur_counts[dur]=dur_counts.get(dur,0)+1
        recovery=bool(axis.get('latest_finish') and int(axis['latest_finish'])>3 and f(axis.get('exact_distance_top3_rate'))>=.60)
        if recovery and a.get('pre_market_decision')=='BUY':a['pre_market_decision']='CAUTION';a['classification']='C';a['decision_override_reason']='過去同距離実績は高いが直近馬券外のため復調前提軸として慎重化'
        mains=pick_main(hs,axis);hp=pick_holes(hs,axis,mains,recovery)
        # Keep V8's general role-diversity improvement when the race is purchased.
        if a.get('pre_market_decision')!='PASS':
            rolepool=[]
            for idx,x in enumerate(mains+hp):rolepool.append({'horse_no':x['n'],'horse_name':x['name'],'running_style':x.get('running_style','UNKNOWN'),'running_style_label':x.get('running_style_label','判定待ち'),'style_sample_starts':x.get('style_sample_starts',0),'position_variance':x.get('position_variance'),'role_score':100-idx*5})
            if rolepool:
                dm=diversified_main(rolepool,axis['n']);dh=style_holes(rolepool,axis['n'],dm);ts=style_tickets(axis['n'],dm,dh);mains_out=[{'horse_no':x['horse_no'],'horse_name':x['horse_name'],'running_style':x.get('running_style')} for x in dm];holes_out=[{'horse_no':x['horse_no'],'horse_name':x['horse_name'],'running_style':x.get('running_style')} for x in dh];style_applied+=1
            else:ts=[];mains_out=[];holes_out=[]
        else:ts=[];mains_out=[{'horse_no':x['n'],'horse_name':x['name']} for x in mains];holes_out=[{'horse_no':x['n'],'horse_name':x['name']} for x in hp]
        a['model_version']=MODEL;a['recovery_axis']=recovery;a['role_main_partners']=mains_out;a['role_holes']=holes_out;a['partner_roles']=mains_out+holes_out;a['trio_tickets']=ts;a['ticket_count']=len(ts);a['ticket_shape']='CONNECTED_DURABILITY_ROLE_DIVERSIFIED_V10' if ts else 'PASS';a['feature_connection_policy']='axis durability fields are explicitly populated from target-date-exclusive JRA profile history';a['running_style_replay_policy']='target-date-exclusive pretarget corner cache only';a['leakage_policy']='no target result/popularity/odds in prediction input'
        rows.append({'race_id':r.get('race_id'),'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'analysis':a})
    payload={'version':MODEL,'mode':'SEALED_PRE_RESULT_REPLAY','race_count':len(rows),'profile_count':len(ids),'profile_fetch_errors':errs,'result_data_used':False,'odds_popularity_used':False,'post_target_running_style_used':False,'durability_status_counts':dur_counts,'style_role_applied_races':style_applied,'races':rows};canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({k:payload[k] for k in ('version','race_count','profile_count','durability_status_counts','style_role_applied_races','prediction_hash_sha256')},ensure_ascii=False,indent=2));print(json.dumps({'races':len(rows),'durability':dur_counts,'style_applied':style_applied,'hash':payload['prediction_hash_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
