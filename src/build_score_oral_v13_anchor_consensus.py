#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,itertools,json,re
from collections import Counter,defaultdict
from pathlib import Path
V12=Path('docs/data/oral-v12-72-rank-consensus-sealed.json')
CACHE=Path('docs/data/pretarget-feature-cache-72.json')
GOLD=Path('docs/data/oral-chat-golden-cases.json')
RES=Path('data/race_results_html_2026.csv')
OUTP=Path('docs/data/oral-v13-72-anchor-consensus-sealed.json')
OUTS=Path('docs/data/oral-v13-72-anchor-consensus-scored.json')
STATUS=Path('status/oral-v13-72-anchor-consensus-scored.json')
AUDIT=Path('status/oral-v13-golden-parity.json')

def f(v,d=0.0):
 try:return float(v)
 except:return d
def i(v):
 try:return int(float(str(v).strip()))
 except:return None
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def key(r):return(str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0))
def rkey(d,t,r):return(str(d),str(t or '').strip().replace('競馬場',''),i(r))
def combo(xs):return '-'.join(map(str,sorted(int(x) for x in xs)))
def anchor_score(h):
 hist=i(h.get('history_rows_before')) or 0;unc=f(h.get('uncertainty'),1)
 return round(30*f(h.get('recent_top3_rate'))+35*f(h.get('exact_distance_top3_rate'))+10*f(h.get('near_distance_top3_rate'))+5*f(h.get('show_rate_prior'))+5*f(h.get('condition_fit'))+.5*min(hist,15)-20*unc,3)
def reliable(h):
 return (i(h.get('history_rows_before')) or 0)>=8 and f(h.get('uncertainty'),1)<=.2 and f(h.get('exact_distance_top3_rate'))>=.45 and f(h.get('recent_top3_rate'))>=.4
def tickets(axis,main,holes):
 out=[]
 for x,y in itertools.combinations(main[:3],2):out.append(combo([axis,x,y]))
 for m in main[:3]:
  for h in holes[:4]:
   t=combo([axis,m,h])
   if t not in out:out.append(t)
   if len(out)>=9:return out[:9]
 return out[:9]
def rebuild_roles(a,new_axis,cache_horses):
 names={str(h.get('n')):h.get('name') for h in cache_horses};styles={str(h.get('n')):h.get('running_style') for h in cache_horses}
 ordered=[]
 for x in (a.get('role_main_partners') or [])+(a.get('role_holes') or []):
  n=str(x.get('horse_no') or '')
  if n and n!=new_axis and n not in ordered:ordered.append(n)
 old=str((a.get('axis') or {}).get('horse_no') or '')
 if old and old!=new_axis and old not in ordered:ordered.append(old)
 main=ordered[:3];holes=ordered[3:7]
 return ([{'horse_no':n,'horse_name':names.get(n),'running_style':styles.get(n)} for n in main],[{'horse_no':n,'horse_name':names.get(n),'running_style':styles.get(n)} for n in holes])
def main():
 v12=json.loads(V12.read_text());cache=json.loads(CACHE.read_text());cm={key(r):r for r in cache['races']};rows=[];overrides=[]
 for r in v12['races']:
  a=json.loads(json.dumps(r['analysis'],ensure_ascii=False));c=cm[key(r)];hs=c['horses'];by={str(h['n']):h for h in hs};old=str((a.get('axis') or {}).get('horse_no') or '');oldh=by.get(old,{})
  eligible=[h for h in hs if reliable(h)];eligible.sort(key=lambda h:(-anchor_score(h),int(h['n'])));best=eligible[0] if eligible else None
  oldscore=anchor_score(oldh) if oldh else -999;bestscore=anchor_score(best) if best else -999
  override=bool(best and str(best['n'])!=old and ((not reliable(oldh)) or bestscore>=oldscore+2.5))
  if override:
   n=str(best['n']);main3,holes=rebuild_roles(a,n,hs);latest=i(best.get('latest_finish')) or 99;exact=f(best.get('exact_distance_top3_rate'))
   recovery=latest>3 and exact>=.60
   a['axis']={'horse_no':n,'horse_name':best.get('name')};a['pre_market_decision']='CAUTION' if recovery else 'BUY';a['classification']='C' if recovery else 'B';a['role_main_partners']=main3;a['role_holes']=holes;a['partner_roles']=main3+holes;a['trio_tickets']=tickets(n,[x['horse_no'] for x in main3],[x['horse_no'] for x in holes]);a['ticket_count']=len(a['trio_tickets']);a['ticket_shape']='V13_RELIABLE_HISTORY_ANCHOR';a['recovery_axis']=recovery;a['axis_anchor_score']=bestscore;a['axis_anchor_override']=True
   overrides.append({'date':r['date'],'track':r['track'],'race_no':r['race_no'],'from_axis':old,'to_axis':n,'old_anchor_score':oldscore,'new_anchor_score':bestscore,'recovery_axis':recovery})
  else:a['axis_anchor_score']=oldscore;a['axis_anchor_override']=False
  a['v13_policy']='V12 two-engine consensus plus generic reliable-history anchor veto: >=8 prior starts, low uncertainty, repeated current-distance form; no target result/popularity/odds'
  rows.append({**{k:r.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'analysis':a})
 payload={'version':'ORAL_V13_RELIABLE_HISTORY_ANCHOR','source_v12_hash':v12.get('prediction_hash_sha256'),'feature_cache_hash':cache.get('feature_cache_hash_sha256'),'result_data_used':False,'odds_popularity_used':False,'override_count':len(overrides),'overrides':overrides,'races':rows};canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();OUTP.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
 # Golden audit: audit only, never used by builder above.
 gold=json.loads(GOLD.read_text());pm={key(r):r for r in rows};cases=[]
 for g in gold['cases']:
  r=pm.get(key(g));a=(r or {}).get('analysis') or {};axis=str((a.get('axis') or {}).get('horse_no') or '');actual_t=sorted(set(g.get('tickets') or []));sys_t=sorted(set(a.get('trio_tickets') or []));cases.append({'date':g['date'],'track':g['track'],'race_no':g['race_no'],'axis_match':axis==no(g['axis']),'decision_match':a.get('pre_market_decision')==g.get('decision'),'tickets_verified':bool(g.get('tickets_verified')),'ticket_exact_match':(actual_t==sys_t) if g.get('tickets_verified') else None,'actual_axis':no(g['axis']),'system_axis':axis,'actual_decision':g.get('decision'),'system_decision':a.get('pre_market_decision')})
 parity={'axis_all':all(x['axis_match'] for x in cases),'decision_all':all(x['decision_match'] for x in cases),'tickets_all_verified':all(x['ticket_exact_match'] for x in cases if x['tickets_verified']),'cases':cases};parity['certified']=bool(parity['axis_all'] and parity['decision_all'] and parity['tickets_all_verified']);AUDIT.parent.mkdir(exist_ok=True);AUDIT.write_text(json.dumps(parity,ensure_ascii=False,indent=2))
 # Open results after seal.
 raw=list(csv.DictReader(RES.open(encoding='utf-8-sig',newline='')));byr=defaultdict(list)
 for x in raw:
  k=rkey(x.get('race_date'),x.get('course'),x.get('race_no'))
  if k[0] in ('2026-08-29','2026-08-30'):byr[k].append(x)
 grade=Counter();dec=Counter();tb=th=0;scored=[];missing=[]
 for r in rows:
  a=r['analysis'];rr=byr.get(rkey(r['date'],r['track'],r['race_no']),[]);axis=str((a.get('axis') or {}).get('horse_no') or '');ar=next((x for x in rr if str(x.get('horse_no') or '').lstrip('0')==axis.lstrip('0')),None);dec[str(a.get('pre_market_decision') or 'UNKNOWN')]+=1
  if not ar:missing.append(key(r));continue
  fin=i(ar.get('finish_position'));gr='HIT' if fin==1 else 'PLACE' if fin and fin<=3 else 'MISS';grade[gr]+=1;top3=[x for x in rr if i(x.get('finish_position')) in (1,2,3)];actual=combo([x['horse_no'] for x in top3]) if len(top3)==3 else None;bought=a.get('pre_market_decision')!='PASS' and bool(a.get('trio_tickets'));hit=bool(bought and actual in set(a.get('trio_tickets') or []));tb+=int(bought);th+=int(hit);scored.append({'date':r['date'],'track':r['track'],'race_no':r['race_no'],'decision':a.get('pre_market_decision'),'axis':axis,'axis_finish':fin,'axis_grade':gr,'trio_hit':hit})
 total=len(scored);summary={'version':payload['version'],'prediction_hash':payload['prediction_hash_sha256'],'golden_parity_certified':parity['certified'],'override_count':len(overrides),'race_count_scored':total,'missing_result_joins':missing,'decision_counts':dict(dec),'axis_1st':grade['HIT'],'axis_2nd_3rd':grade['PLACE'],'axis_outside_top3':grade['MISS'],'axis_top3_rate_pct':round((grade['HIT']+grade['PLACE'])/total*100,2) if total else 0,'trio_bought_races':tb,'trio_hits':th,'trio_hit_rate_pct':round(th/tb*100,2) if tb else 0,'results_opened_after_prediction_seal':True};OUTS.write_text(json.dumps({'summary':summary,'races':scored},ensure_ascii=False,indent=2));STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps({'parity':parity,'summary':summary,'overrides':overrides},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
