#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile
from run_oral_v6_72_sealed_replay import key,parse_profile,hist_features,f
from run_oral_v10_72_connected_durability import connect_features
from build_oral_v8_72_fullstyle import style_from_samples
CARDS=Path('docs/data/race_cards.json');BASE=Path('docs/data/replay-2026-08-29-30-sealed.json');CORNER=Path('docs/data/pretarget-corner-cache.json');OUT=Path('docs/data/pretarget-feature-cache-72.json');STATUS=Path('status/pretarget-feature-cache-72.json')
def main():
 cards=json.loads(CARDS.read_text());base=json.loads(BASE.read_text());corner=json.loads(CORNER.read_text());bm={key(r):r for r in base.get('races',[])};styles={hid:style_from_samples(xs) for hid,xs in corner.get('horses',{}).items()}
 ids=sorted({str(h.get('horse_id') or '') for r in cards.get('races',[]) for h in r.get('horses',[]) if h.get('horse_id')});hist={};errs=[]
 def one(i):return i,parse_profile(request_profile(i))
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(one,i):i for i in ids}
  for n,fu in enumerate(concurrent.futures.as_completed(fs),1):
   i=fs[fu]
   try:k,v=fu.result();hist[k]=v
   except Exception as e:hist[i]=[];errs.append({'horse_id':i,'error':repr(e)})
   if n%100==0:print(f'profiles {n}/{len(ids)} errors={len(errs)}',flush=True)
 races=[]
 for r in cards.get('races',[]):
  b=bm.get(key(r),{});base_by_id={str(x.get('horse_id') or ''):x for x in b.get('ranked_snapshot',[])};base_floor=min([f(x.get('score'),20) for x in b.get('ranked_snapshot',[])] or [20.0]);horses=[]
  for idx,h in enumerate(r.get('horses',[])):
   hid=str(h.get('horse_id') or '');old=base_by_id.get(hid,{});feat=hist_features(hist.get(hid,[]),str(r['date']),int(r.get('distance_m') or 0),str(r.get('track') or ''));conn=connect_features(feat);base_score=f(old.get('score'),max(12.0,base_floor-.20*(idx+1)));unc=f(old.get('uncertainty'),1.0 if feat['history_rows_before']==0 else max(0.0,1-min(5,feat['history_rows_before'])/5));st=styles.get(hid,{'running_style':'UNKNOWN','running_style_label':'判定待ち','style_sample_starts':0,'position_variance':None});horses.append({'n':str(h.get('n')),'name':h.get('name'),'horse_id':hid,'base_score_v1':round(base_score,3),'uncertainty':round(unc,3),**feat,**conn,**st})
  races.append({'race_id':r.get('race_id'),'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'horses':horses})
 payload={'version':'PRETARGET_FEATURE_CACHE_72_V1','race_count':len(races),'horse_profile_count':len(ids),'profile_errors':errs,'result_data_used':False,'odds_popularity_used':False,'target_result_rows_used':False,'corner_cutoff_exclusive':corner.get('cutoff_exclusive'),'policy':'Every horse feature is derived only from information dated before its target race; target result/popularity/odds are excluded.','races':races};canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['feature_cache_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({'version':payload['version'],'race_count':len(races),'horse_profile_count':len(ids),'profile_errors':len(errs),'feature_cache_hash_sha256':payload['feature_cache_hash_sha256']},ensure_ascii=False,indent=2));print(json.dumps({'races':len(races),'profiles':len(ids),'errors':len(errs),'hash':payload['feature_cache_hash_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
