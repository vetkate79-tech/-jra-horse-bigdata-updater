#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,csv,hashlib,json,re,sys,urllib.parse,urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables, UA
BASE=Path('docs/data/pretarget-feature-cache-72.json');CTX=Path('data/race_context_2026.csv');OUT=Path('docs/data/pretarget-class-feature-cache-72.json');STATUS=Path('status/pretarget-class-feature-cache-72.json');JRA='https://www.jra.go.jp'
def nums(v):return [int(x) for x in re.findall(r'\d+',str(v or ''))]
def key(d,t,r):return(str(d),str(t).strip().replace('競馬場',''),int(r))
def absurl(h):return urllib.parse.urljoin(JRA,h)
def profile_hist(hid):
 html=request_profile(hid);ts=normalized_tables(html);soup=BeautifulSoup(html,'html.parser');links=[a.get('href') for a in soup.find_all('a',href=True) if 'accessS.html?CNAME=pw01sde' in a.get('href','')]
 if not ts:return[]
 t=ts[0];links=links[:len(t)];out=[]
 for ix,(_,rr) in enumerate(t.iterrows()):
  vals=[str(x).strip() for x in rr.tolist()];ds=nums(vals[0] if vals else '');dn=nums(vals[3] if len(vals)>3 else '');fn=nums(vals[7] if len(vals)>7 else '')
  if len(ds)<3:continue
  out.append({'date':f'{ds[0]:04d}-{ds[1]:02d}-{ds[2]:02d}','distance_m':dn[-1] if dn else None,'finish':fn[0] if fn else None,'href':links[ix] if ix<len(links) else ''})
 return sorted(out,key=lambda x:x['date'],reverse=True)
def getclass(url):
 if not url:return None
 req=urllib.request.Request(absurl(url),headers={'User-Agent':UA,'Referer':JRA+'/','Accept-Language':'ja'})
 try:
  with urllib.request.urlopen(req,timeout=20) as resp:raw=resp.read()
 except:return None
 for c in ('3勝クラス','2勝クラス','1勝クラス','オープン','未勝利','新馬'):
  for enc in ('utf-8','cp932','euc_jp'):
   try:
    if c.encode(enc) in raw:return c
   except:pass
 return None
def rate(xs):return round(sum(x['finish']<=3 for x in xs)/len(xs),4) if xs else None
def main():
 base=json.loads(BASE.read_text());ctx={}
 with CTX.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):ctx[key(r['race_date'],r['course'],r['race_no'])]=r.get('race_class')
 race_horse=[];ids={}
 for r in base['races']:
  k=key(r['date'],r['track'],r['race_no']);tc=ctx.get(k)
  for h in r['horses']:
   hid=str(h.get('horse_id') or '');race_horse.append((k,r,tc,h,hid));ids[hid]=True
 hist={};errs=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
  fs={ex.submit(profile_hist,h):h for h in ids if h}
  for fu in concurrent.futures.as_completed(fs):
   h=fs[fu]
   try:hist[h]=fu.result()
   except Exception as e:hist[h]=[];errs.append({'horse_id':h,'error':repr(e)})
 urls=sorted({x['href'] for _,r,_,_,hid in race_horse for x in hist.get(hid,[]) if x.get('href') and x['date']<r['date']})
 cmap={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=28) as ex:
  fs={ex.submit(getclass,u):u for u in urls}
  for fu in concurrent.futures.as_completed(fs):
   u=fs[fu]
   try:cmap[u]=fu.result()
   except:cmap[u]=None
 out=[];resolved=0
 for r in base['races']:
  k=key(r['date'],r['track'],r['race_no']);tc=ctx.get(k);hs=[]
  for h in r['horses']:
   x=dict(h);pre=[z for z in hist.get(str(h.get('horse_id') or ''),[]) if z['date']<r['date'] and z.get('finish')]
   same=[z for z in pre if tc and cmap.get(z.get('href'))==tc][:10];exact=[z for z in same if z.get('distance_m')==int(r['distance_m'])][:10];lc=next((z for z in pre if tc and cmap.get(z.get('href'))==tc),None);lec=next((z for z in pre if tc and cmap.get(z.get('href'))==tc and z.get('distance_m')==int(r['distance_m'])),None)
   x.update({'target_class':tc,'same_class_starts':len(same),'same_class_top3_rate':rate(same),'exact_class_starts':len(exact),'exact_class_top3_rate':rate(exact),'latest_same_class_finish':lc.get('finish') if lc else None,'latest_exact_class_finish':lec.get('finish') if lec else None})
   if same:resolved+=1
   hs.append(x)
  out.append({**{z:r.get(z) for z in ('race_id','date','track','race_no','race_name','surface','distance_m')},'target_class':tc,'horses':hs})
 payload={'version':'PRETARGET_CLASS_FEATURE_CACHE_72_V1','race_count':len(out),'horse_count':sum(len(r['horses']) for r in out),'profile_count':len(ids),'profile_errors':errs,'historical_result_urls':len(urls),'class_resolved_urls':sum(v is not None for v in cmap.values()),'horses_with_same_class_history':resolved,'isolation':{'target_class_source':'pre-race race_context_2026.csv','historical_class_source':'JRA official result pages dated before each target race','target_result_rows_used':False,'odds_popularity_used':False},'races':out};raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['cache_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest();OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({k:payload[k] for k in ('version','race_count','horse_count','profile_count','profile_errors','historical_result_urls','class_resolved_urls','horses_with_same_class_history','isolation','cache_hash_sha256')},ensure_ascii=False,indent=2));print(STATUS.read_text())
if __name__=='__main__':main()
