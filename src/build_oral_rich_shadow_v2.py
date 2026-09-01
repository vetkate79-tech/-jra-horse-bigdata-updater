#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables
from oral_operational_layer import analyze_race

BASE=Path('docs/data/replay-2026-08-29-30-sealed.json')
OUT=Path('docs/data/oral-integrated-v2-rich-sealed.json')
STATUS=Path('status/oral-integrated-v2-rich.json')
MODEL='ORAL_INTEGRATED_V2_RICH_HISTORY'

def key(r):return (str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0))
def nums(v):return [int(x) for x in re.findall(r'\d+',str(v or ''))]
def f(v,d=0.0):
 try:return float(v)
 except:return d

def parse_history(html):
 tables=normalized_tables(html)
 if not tables:return []
 t=tables[0]
 if len(t.columns)<12:return []
 out=[]
 for _,rr in t.iterrows():
  vals=[str(x).strip() for x in rr.tolist()]
  ds=nums(vals[0] if vals else '')
  if len(ds)<3:continue
  date=f'{ds[0]:04d}-{ds[1]:02d}-{ds[2]:02d}'
  course_nums=nums(vals[3] if len(vals)>3 else '')
  dist=course_nums[-1] if course_nums else None
  finish_nums=nums(vals[7] if len(vals)>7 else '')
  finish=finish_nums[0] if finish_nums else None
  field_nums=nums(vals[5] if len(vals)>5 else '')
  field=field_nums[0] if field_nums else None
  pop_nums=nums(vals[6] if len(vals)>6 else '')
  popularity=pop_nums[0] if pop_nums else None
  weight=f(vals[9],None) if len(vals)>9 else None
  body_nums=nums(vals[10] if len(vals)>10 else '')
  body=body_nums[0] if body_nums else None
  tm=vals[11] if len(vals)>11 else ''
  out.append({'date':date,'distance_m':dist,'finish':finish,'field_size':field,'popularity_result_only':popularity,'carried_weight':weight,'body_weight':body,'time':tm})
 return sorted(out,key=lambda x:x['date'],reverse=True)

def compact_features(hist,target_date,target_distance):
 pre=[x for x in hist if x['date']<target_date and x.get('finish')]
 recent=pre[:5]
 same=[x for x in pre if x.get('distance_m') and abs(x['distance_m']-target_distance)<=200][:8]
 recent_top3=sum(x['finish']<=3 for x in recent)/len(recent) if recent else None
 same_top3=sum(x['finish']<=3 for x in same)/len(same) if same else None
 latest=recent[0] if recent else None
 latest_same=next((x for x in recent if x.get('distance_m') and abs(x['distance_m']-target_distance)<=200),None)
 latest_same_top3=bool(latest_same and latest_same['finish']<=3)
 latest_same_win=bool(latest_same and latest_same['finish']==1)
 # This is a pre-race structural-fit layer, not a result/popularity layer.
 # Popularity is parsed only because it exists in the table and is deliberately excluded below.
 boost=0.0
 if recent_top3 is not None:boost+=8.0*recent_top3
 if same_top3 is not None:boost+=10.0*same_top3
 if latest_same_top3:boost+=8.0
 if latest_same_win:boost+=3.0
 if latest and latest['finish']<=3:boost+=4.0
 return {
  'history_rows_before':len(pre),'recent_top3_rate':None if recent_top3 is None else round(recent_top3,4),
  'same_distance_top3_rate':None if same_top3 is None else round(same_top3,4),
  'latest_finish':latest.get('finish') if latest else None,'latest_distance_m':latest.get('distance_m') if latest else None,
  'latest_same_distance_finish':latest_same.get('finish') if latest_same else None,
  'structural_history_boost':round(boost,3)
 }

def main():
 base=json.loads(BASE.read_text());races=base.get('races',[])
 horse_ids=sorted({str(h.get('horse_id') or '') for r in races for h in r.get('ranked_snapshot',[]) if h.get('horse_id')})
 histories={};errors=[]
 def one(hid):return hid,parse_history(request_profile(hid))
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(one,h):h for h in horse_ids}
  for i,fu in enumerate(concurrent.futures.as_completed(fs),1):
   hid=fs[fu]
   try:k,v=fu.result();histories[k]=v
   except Exception as e:histories[hid]=[];errors.append({'horse_id':hid,'error':repr(e)})
   if i%100==0:print(f'history {i}/{len(horse_ids)} errors={len(errors)}',flush=True)
 out=[]
 for r in races:
  enriched=[];dist=int(r.get('distance_m') or 0)
  for h in r.get('ranked_snapshot',[]):
   x=dict(h);cf=compact_features(histories.get(str(h.get('horse_id') or ''),[]),str(r.get('date')),dist)
   x.update(cf);x['base_score_v1']=f(h.get('score'));x['score']=round(x['base_score_v1']+cf['structural_history_boost'],3);enriched.append(x)
  enriched.sort(key=lambda x:(-f(x.get('score')),int(str(x.get('n') or 999))))
  rr={**r,'ranked_snapshot':enriched}
  a=analyze_race(rr);a['model_version']=MODEL;a['ranking_policy']='V1 base ability + pre-race recent/same-distance structural history; odds/popularity excluded'
  out.append({**{k:r.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'analysis':a,'ranked_snapshot':enriched[:10]})
 payload={'version':MODEL,'mode':'RICH_PRE_RACE_ORAL_SHADOW','result_data_used':False,'odds_popularity_used':False,'history_fetch_errors':errors,'race_count':len(out),'races':out}
 raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest()
 txt=json.dumps(payload,ensure_ascii=False,separators=(',',':'));OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({'version':MODEL,'race_count':len(out),'history_fetch_errors':len(errors),'prediction_hash_sha256':payload['prediction_hash_sha256']},ensure_ascii=False,indent=2));print(json.dumps({'race_count':len(out),'errors':len(errors),'hash':payload['prediction_hash_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
