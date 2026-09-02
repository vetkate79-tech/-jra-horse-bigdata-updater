#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,csv,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'src')
from build_pretarget_class_cache_72 import profile_hist,getclass,key,rate
BASE=Path('docs/data/pretarget-feature-cache-72.json');V12=Path('docs/data/oral-v12-72-rank-consensus-sealed.json');CTX=Path('data/race_context_2026.csv');OUT=Path('docs/data/pretarget-class-shortlist-72.json');STATUS=Path('status/pretarget-class-shortlist-72.json')
def f(v,d=0.0):
 try:return float(v)
 except:return d
def eff(h):
 raw=f(h.get('base_score_v1'))+min(50,f(h.get('oral_structure_score')));return raw*max(.45,1-.7*f(h.get('uncertainty'),1))
def main():
 b=json.loads(BASE.read_text());v=json.loads(V12.read_text());vm={key(r['date'],r['track'],r['race_no']):r for r in v['races']};ctx={}
 with CTX.open(encoding='utf-8-sig',newline='') as f0:
  for r in csv.DictReader(f0):ctx[key(r['race_date'],r['course'],r['race_no'])]=r.get('race_class')
 selections=[];ids=set()
 for r in b['races']:
  k=key(r['date'],r['track'],r['race_no']);va=vm[k]['analysis'];axis=str((va.get('axis') or {}).get('horse_no') or '');rank=sorted(r['horses'],key=lambda h:(-eff(h),int(h['n'])));nos=[]
  for n in [axis]+[str(h['n']) for h in rank[:6]]:
   if n and n not in nos:nos.append(n)
  hs=[h for h in r['horses'] if str(h['n']) in nos];ids.update(str(h.get('horse_id') or '') for h in hs);selections.append((r,ctx.get(k),hs))
 hist={};errs=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
  fs={ex.submit(profile_hist,h):h for h in ids if h}
  for fu in concurrent.futures.as_completed(fs):
   h=fs[fu]
   try:hist[h]=fu.result()
   except Exception as e:hist[h]=[];errs.append({'horse_id':h,'error':repr(e)})
 urls=sorted({z['href'] for r,tc,hs in selections for h in hs for z in hist.get(str(h.get('horse_id') or ''),[])[:10] if z.get('href') and z['date']<r['date']});cm={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=28) as ex:
  fs={ex.submit(getclass,u):u for u in urls}
  for fu in concurrent.futures.as_completed(fs):
   try:cm[fs[fu]]=fu.result()
   except:cm[fs[fu]]=None
 out=[]
 for r,tc,hs in selections:
  oo=[]
  for h in hs:
   pre=[z for z in hist.get(str(h.get('horse_id') or ''),[]) if z['date']<r['date'] and z.get('finish')];same=[z for z in pre if tc and cm.get(z.get('href'))==tc][:10];exact=[z for z in same if z.get('distance_m')==int(r['distance_m'])][:10];lc=next((z for z in pre if tc and cm.get(z.get('href'))==tc),None);le=next((z for z in pre if tc and cm.get(z.get('href'))==tc and z.get('distance_m')==int(r['distance_m'])),None);x=dict(h);x.update({'v4_effective':round(eff(h),3),'target_class':tc,'same_class_starts':len(same),'same_class_top3_rate':rate(same),'exact_class_starts':len(exact),'exact_class_top3_rate':rate(exact),'latest_same_class_finish':lc.get('finish') if lc else None,'latest_exact_class_finish':le.get('finish') if le else None});oo.append(x)
  out.append({**{z:r.get(z) for z in ('race_id','date','track','race_no','race_name','surface','distance_m')},'target_class':tc,'horses':oo})
 payload={'version':'PRETARGET_CLASS_SHORTLIST_72_V1','race_count':len(out),'profile_count':len(ids),'profile_errors':errs,'historical_result_urls':len(urls),'class_resolved_urls':sum(v is not None for v in cm.values()),'isolation':{'target_class_source':'pre-race race_context_2026.csv','historical_only_before_target':True,'target_result_rows_used':False,'odds_popularity_used':False},'races':out};raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['cache_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest();OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({k:payload[k] for k in ('version','race_count','profile_count','profile_errors','historical_result_urls','class_resolved_urls','isolation','cache_hash_sha256')},ensure_ascii=False,indent=2));print(STATUS.read_text())
if __name__=='__main__':main()
