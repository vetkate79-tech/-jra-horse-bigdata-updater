#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile
from oral_operational_layer import analyze_race
from run_oral_v6_72_sealed_replay import key,parse_profile,hist_features,f,pick_main,pick_holes
from run_oral_v10_72_connected_durability import connect_features
from build_oral_v8_72_fullstyle import style_from_samples,diversified_main,holes as style_holes,tickets as style_tickets

CARDS=Path('docs/data/race_cards.json');BASE=Path('docs/data/replay-2026-08-29-30-sealed.json');CACHE=Path('docs/data/pretarget-corner-cache.json')
OUT=Path('docs/data/oral-v12-72-rank-consensus-sealed.json');STATUS=Path('status/oral-v12-72-rank-consensus-sealed.json');MODEL='ORAL_V12_TWO_ENGINE_RANK_CONSENSUS'

def rank_norm(items,keyname,reverse=True):
    ordered=sorted(items,key=lambda x:(-f(x.get(keyname)) if reverse else f(x.get(keyname)),int(x.get('n') or 999)))
    n=max(1,len(ordered)-1);return {id(x):1-(i/n) for i,x in enumerate(ordered)}

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
    rows=[]
    for r in cards.get('races',[]):
        b=bm.get(key(r),{});base_by_id={str(x.get('horse_id') or ''):x for x in b.get('ranked_snapshot',[])};base_floor=min([f(x.get('score'),20) for x in b.get('ranked_snapshot',[])] or [20.0]);hs=[]
        for idx,h in enumerate(r.get('horses',[])):
            hid=str(h.get('horse_id') or '');old=base_by_id.get(hid,{});feat=hist_features(hist.get(hid,[]),str(r['date']),int(r.get('distance_m') or 0),str(r.get('track') or ''));conn=connect_features(feat);base_score=f(old.get('score'),max(12.0,base_floor-.20*(idx+1)));unc=f(old.get('uncertainty'),1.0 if feat['history_rows_before']==0 else max(0.0,1-min(5,feat['history_rows_before'])/5));st=styles.get(hid,{'running_style':'UNKNOWN','running_style_label':'判定待ち','style_sample_starts':0,'position_variance':None});hs.append({'n':str(h.get('n')),'name':h.get('name'),'horse_id':hid,'base_score_v1':round(base_score,3),'uncertainty':round(unc,3),'oral_structure_score':f(feat.get('oral_structure_score')),**feat,**conn,**st})
        base_rank=rank_norm(hs,'base_score_v1');struct_rank=rank_norm(hs,'oral_structure_score')
        for x in hs:
            conf=min(1.0,f(x.get('starts_before'))/5);w=.45*conf;bn=base_rank[id(x)];sn=struct_rank[id(x)];cons=(1-w)*bn+w*sn;x['base_rank_norm']=round(bn,4);x['structure_rank_norm']=round(sn,4);x['structure_consensus_weight']=round(w,3);x['score']=round(cons*100,3)
        hs.sort(key=lambda x:(-f(x['score']),-f(x['base_score_v1']),int(x['n'])))
        rr={**b,'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'ranked_snapshot':hs};a=analyze_race(rr);axis=next((x for x in hs if x['n']==str((a.get('axis') or {}).get('horse_no'))),hs[0] if hs else {})
        recovery=bool(axis.get('latest_finish') and int(axis['latest_finish'])>3 and f(axis.get('exact_distance_top3_rate'))>=.60)
        if recovery and a.get('pre_market_decision')=='BUY':a['pre_market_decision']='CAUTION';a['classification']='C';a['decision_override_reason']='過去同距離実績は高いが直近馬券外のため復調前提軸として慎重化'
        mains=pick_main(hs,axis);hp=pick_holes(hs,axis,mains,recovery);ts=[];mains_out=[];holes_out=[]
        if a.get('pre_market_decision')!='PASS':
            rolepool=[]
            for idx,x in enumerate(mains+hp):rolepool.append({'horse_no':x['n'],'horse_name':x['name'],'running_style':x.get('running_style','UNKNOWN'),'running_style_label':x.get('running_style_label','判定待ち'),'style_sample_starts':x.get('style_sample_starts',0),'position_variance':x.get('position_variance'),'role_score':100-idx*5})
            if rolepool:
                dm=diversified_main(rolepool,axis['n']);dh=style_holes(rolepool,axis['n'],dm);ts=style_tickets(axis['n'],dm,dh);mains_out=[{'horse_no':x['horse_no'],'horse_name':x['horse_name'],'running_style':x.get('running_style')} for x in dm];holes_out=[{'horse_no':x['horse_no'],'horse_name':x['horse_name'],'running_style':x.get('running_style')} for x in dh]
        else:
            mains_out=[{'horse_no':x['n'],'horse_name':x['name']} for x in mains];holes_out=[{'horse_no':x['n'],'horse_name':x['name']} for x in hp]
        a['model_version']=MODEL;a['role_main_partners']=mains_out;a['role_holes']=holes_out;a['partner_roles']=mains_out+holes_out;a['trio_tickets']=ts;a['ticket_count']=len(ts);a['ticket_shape']='TWO_ENGINE_CONSENSUS_V12' if ts else 'PASS';a['axis_consensus_detail']={'base_rank_norm':axis.get('base_rank_norm'),'structure_rank_norm':axis.get('structure_rank_norm'),'structure_weight':axis.get('structure_consensus_weight'),'history_rows':axis.get('starts_before')};a['leakage_policy']='profile history date < target; no target result/popularity/odds used'
        rows.append({'race_id':r.get('race_id'),'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'analysis':a})
    payload={'version':MODEL,'race_count':len(rows),'profile_count':len(ids),'profile_fetch_errors':errs,'result_data_used':False,'odds_popularity_used':False,'post_target_running_style_used':False,'consensus_policy':'Base ability rank and structural-fit rank are combined; structural weight rises only with pre-race history confidence and is capped at 45%.','races':rows};canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({'version':MODEL,'race_count':len(rows),'profile_count':len(ids),'errors':len(errs),'prediction_hash_sha256':payload['prediction_hash_sha256']},ensure_ascii=False,indent=2));print(json.dumps({'races':len(rows),'hash':payload['prediction_hash_sha256'],'errors':len(errs)},ensure_ascii=False))
if __name__=='__main__':main()
