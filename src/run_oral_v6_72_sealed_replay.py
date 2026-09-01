#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,hashlib,itertools,json,re,sys
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables
from oral_operational_layer import analyze_race

CARDS=Path('docs/data/race_cards.json')
BASE=Path('docs/data/replay-2026-08-29-30-sealed.json')
OUT=Path('docs/data/oral-v6-72-predictions-sealed.json')
STATUS=Path('status/oral-v6-72-predictions-sealed.json')
MODEL='ORAL_V6_72_SEALED_REPLAY'

def key(r):return(str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0))
def nums(v):return[int(x) for x in re.findall(r'\d+',str(v or ''))]
def f(v,d=0.0):
 try:return float(v)
 except:return d

def parse_profile(html):
 ts=normalized_tables(html)
 if not ts:return[]
 t=ts[0]
 if len(t.columns)<12:return[]
 out=[]
 for _,rr in t.iterrows():
  vals=[str(x).strip() for x in rr.tolist()];ds=nums(vals[0] if vals else '')
  if len(ds)<3:continue
  course=vals[1] if len(vals)>1 else '';race_name=vals[2] if len(vals)>2 else '';cond=vals[3] if len(vals)>3 else ''
  dn=nums(cond);fn=nums(vals[7] if len(vals)>7 else '');field=nums(vals[5] if len(vals)>5 else '')
  out.append({'date':f'{ds[0]:04d}-{ds[1]:02d}-{ds[2]:02d}','course':course,'race_name':race_name,'distance_m':dn[-1] if dn else None,'finish':fn[0] if fn else None,'field_size':field[0] if field else None})
 return sorted(out,key=lambda x:x['date'],reverse=True)

def hist_features(hist,date,dist,track):
 pre=[x for x in hist if x['date']<date and x.get('finish')];recent=pre[:5]
 exact=[x for x in pre if x.get('distance_m')==dist][:8]
 near=[x for x in pre if x.get('distance_m') and abs(x['distance_m']-dist)<=200][:8]
 same_course=[x for x in pre if track and track in str(x.get('course') or '')][:8]
 exact_course=[x for x in pre if x.get('distance_m')==dist and track and track in str(x.get('course') or '')][:8]
 def rate(xs):return sum(x['finish']<=3 for x in xs)/len(xs) if xs else 0.0
 latest=recent[0] if recent else None
 le=next((x for x in recent if x.get('distance_m')==dist),None)
 lc=next((x for x in recent if track and track in str(x.get('course') or '')),None)
 lec=next((x for x in recent if x.get('distance_m')==dist and track and track in str(x.get('course') or '')),None)
 structure=10*rate(recent)+12*rate(exact)+5*rate(near)+8*rate(same_course)+12*rate(exact_course)
 if latest and latest['finish']<=3:structure+=4
 if le and le['finish']<=3:structure+=7
 if lc and lc['finish']<=5:structure+=5
 if lec and lec['finish']<=5:structure+=8
 if latest and latest.get('field_size') and latest['field_size']>1:structure+=3*max(0,1-(latest['finish']-1)/(latest['field_size']-1))
 return {'history_rows_before':len(pre),'recent_top3_rate':round(rate(recent),4),'exact_distance_top3_rate':round(rate(exact),4),'near_distance_top3_rate':round(rate(near),4),'same_course_top3_rate':round(rate(same_course),4),'exact_course_top3_rate':round(rate(exact_course),4),'latest_finish':latest.get('finish') if latest else None,'latest_exact_finish':le.get('finish') if le else None,'latest_course_finish':lc.get('finish') if lc else None,'latest_exact_course_finish':lec.get('finish') if lec else None,'oral_structure_score':round(structure,3)}

def effective(base,structure,unc):
 structure=min(50.0,max(0.0,structure));unc=max(0.0,min(1.0,unc));raw=base+structure;rel=max(.45,1-.70*unc);return round(raw*rel,3)
def combo(a,b,c):return '-'.join(map(str,sorted(map(int,[a,b,c]))))
def main_score(h):
 s=f(h.get('score'))*.52+f(h.get('oral_structure_score'))
 if int(h.get('latest_exact_course_finish') or 99)<=5:s+=8
 if int(h.get('latest_finish') or 99)<=5:s+=4
 if f(h.get('exact_distance_top3_rate'))>=.50:s+=7
 return s

def pick_main(hs,axis):
 elig=[]
 for h in hs:
  if h['n']==axis['n']:continue
  if int(h.get('latest_finish') or 99)<=7 or int(h.get('latest_exact_course_finish') or 99)<=5 or f(h.get('exact_distance_top3_rate'))>=.50:
   x=dict(h);x['main_score']=round(main_score(x),3);elig.append(x)
 elig.sort(key=lambda x:(-x['main_score'],int(x['n'])))
 return elig[:3]

def pick_holes(hs,axis,main,recovery):
 used={axis['n'],*[x['n'] for x in main]};rest=[dict(x) for x in hs if x['n'] not in used]
 if recovery:
  cand=[x for x in rest if int(x.get('latest_finish') or 99) in (3,4)]
  cand.sort(key=lambda x:(int(x.get('latest_finish') or 99),-main_score(x),int(x['n'])))
  return cand[:2]
 rest.sort(key=lambda x:(-f(x.get('score')),-f(x.get('oral_structure_score')),int(x['n'])))
 return rest[:4]

def make_tickets(axis,main,holes,recovery):
 out=[];a=axis['n']
 for x,y in itertools.combinations(main,2):out.append(combo(a,x['n'],y['n']))
 for m in main:
  for h in holes:
   if len(out)>=9:break
   out.append(combo(a,m['n'],h['n']))
  if len(out)>=9:break
 return list(dict.fromkeys(out))[:9]

def main():
 cards=json.loads(CARDS.read_text());base=json.loads(BASE.read_text());bm={key(r):r for r in base.get('races',[])}
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
   hid=str(h.get('horse_id') or '');old=base_by_id.get(hid,{});feat=hist_features(hist.get(hid,[]),str(r['date']),int(r.get('distance_m') or 0),str(r.get('track') or ''))
   base_score=f(old.get('score'),max(12.0,base_floor-.20*(idx+1)));unc=f(old.get('uncertainty'),1.0 if feat['history_rows_before']==0 else max(0.0,1-min(5,feat['history_rows_before'])/5))
   score=effective(base_score,feat['oral_structure_score'],unc)
   x={'n':str(h.get('n')),'name':h.get('name'),'horse_id':hid,'base_score_v1':round(base_score,3),'uncertainty':round(unc,3),'score':score,'running_style':'UNKNOWN',**feat};hs.append(x)
  hs.sort(key=lambda x:(-f(x['score']),int(x['n'])))
  rr={**b,'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'ranked_snapshot':hs}
  a=analyze_race(rr);axis=next((x for x in hs if x['n']==str((a.get('axis') or {}).get('horse_no'))),hs[0] if hs else {})
  recovery=bool(axis.get('latest_finish') and int(axis['latest_finish'])>3 and f(axis.get('exact_distance_top3_rate'))>=.60)
  if recovery and a.get('pre_market_decision')=='BUY':a['pre_market_decision']='CAUTION';a['classification']='C';a['decision_override_reason']='過去同距離実績は高いが直近馬券外のため復調前提軸として慎重化'
  mains=pick_main(hs,axis);holes=pick_holes(hs,axis,mains,recovery);ts=make_tickets(axis,mains,holes,recovery) if a.get('pre_market_decision')!='PASS' else []
  a['model_version']=MODEL;a['recovery_axis']=recovery;a['role_main_partners']=[{'horse_no':x['n'],'horse_name':x['name']} for x in mains];a['role_holes']=[{'horse_no':x['n'],'horse_name':x['name']} for x in holes];a['partner_roles']=a['role_main_partners']+a['role_holes'];a['trio_tickets']=ts;a['ticket_count']=len(ts);a['ticket_shape']='ROLE_DIVERSIFIED_AXIS_V6' if ts else 'PASS';a['running_style_replay_policy']='UNKNOWN: post-target style cache intentionally not reused';a['leakage_policy']='profile history rows date < target only; no target result/popularity/odds used'
  rows.append({'race_id':r.get('race_id'),'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'analysis':a})
 payload={'version':MODEL,'mode':'SEALED_PRE_RESULT_REPLAY','race_count':len(rows),'profile_count':len(ids),'profile_fetch_errors':errs,'result_data_used':False,'odds_popularity_used':False,'post_target_running_style_used':False,'races':rows}
 canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();txt=json.dumps(payload,ensure_ascii=False,indent=2);OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({'version':MODEL,'race_count':len(rows),'profile_count':len(ids),'errors':len(errs),'prediction_hash_sha256':payload['prediction_hash_sha256']},ensure_ascii=False,indent=2));print(json.dumps({'race_count':len(rows),'profiles':len(ids),'errors':len(errs),'prediction_hash_sha256':payload['prediction_hash_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
