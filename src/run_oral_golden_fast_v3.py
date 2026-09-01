#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,json,re,sys,urllib.parse,urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables, UA
from oral_operational_layer import analyze_race
BASE=Path('docs/data/replay-2026-08-29-30-sealed.json');GOLD=Path('docs/data/oral-chat-golden-cases.json');OUT=Path('docs/data/oral-golden-fast-v3.json')
JRA='https://www.jra.go.jp'
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def nums(v):return[int(x) for x in re.findall(r'\d+',str(v or ''))]
def f(v,d=0.0):
 try:return float(v)
 except:return d
def track_code(url):
 m=re.search(r'pw01sde(\d{4})',str(url));return m.group(1) if m else ''
def absurl(h):return urllib.parse.urljoin(JRA,h)

def profile_history(hid):
 html=request_profile(hid);ts=normalized_tables(html)
 if not ts or len(ts[0].columns)<12:return[]
 soup=BeautifulSoup(html,'html.parser');links=[a.get('href') for a in soup.find_all('a',href=True) if 'accessS.html?CNAME=pw01sde' in a.get('href','')]
 # first sequence corresponds to result-history rows; later calendar links repeat a subset
 links=links[:len(ts[0])]
 out=[]
 for ix,(_,rr) in enumerate(ts[0].iterrows()):
  vals=[str(x).strip() for x in rr.tolist()];ds=nums(vals[0] if vals else '')
  if len(ds)<3:continue
  dn=nums(vals[3] if len(vals)>3 else '');fn=nums(vals[7] if len(vals)>7 else '');field=nums(vals[5] if len(vals)>5 else '')
  href=links[ix] if ix<len(links) else ''
  out.append({'date':f'{ds[0]:04d}-{ds[1]:02d}-{ds[2]:02d}','distance_m':dn[-1] if dn else None,'finish':fn[0] if fn else None,'field_size':field[0] if field else None,'href':href,'track_code':track_code(href)})
 return sorted(out,key=lambda x:x['date'],reverse=True)

def result_class(url):
 if not url:return None
 req=urllib.request.Request(absurl(url),headers={'User-Agent':UA,'Referer':JRA+'/','Accept-Language':'ja'})
 try:
  with urllib.request.urlopen(req,timeout=30) as resp:raw=resp.read()
 except:return None
 for cls in ('3勝クラス','2勝クラス','1勝クラス','オープン'):
  for enc in ('utf-8','cp932','euc_jp'):
   try:
    if cls.encode(enc) in raw:return cls
   except:pass
 # ASCII survives even when Japanese decoding does not; some pages expose age + class label.
 text=raw.decode('latin1','ignore')
 return None

def feats(hist,date,dist,target_track,target_class,classmap):
 pre=[x for x in hist if x['date']<date and x.get('finish')];recent=pre[:5]
 for x in recent:x['race_class']=classmap.get(x.get('href'))
 exact=[x for x in pre if x.get('distance_m')==dist][:8];same_track=[x for x in pre if target_track and x.get('track_code')==target_track][:8];same_class=[x for x in pre if target_class and classmap.get(x.get('href'))==target_class][:8]
 exact_track=[x for x in pre if x.get('distance_m')==dist and target_track and x.get('track_code')==target_track][:8]
 exact_class=[x for x in pre if x.get('distance_m')==dist and target_class and classmap.get(x.get('href'))==target_class][:8]
 def rate(xs):return sum(x['finish']<=3 for x in xs)/len(xs) if xs else 0
 latest=recent[0] if recent else None;lc=next((x for x in recent if target_class and classmap.get(x.get('href'))==target_class),None);let=next((x for x in recent if x.get('distance_m')==dist and target_track and x.get('track_code')==target_track),None);lec=next((x for x in recent if x.get('distance_m')==dist and target_class and classmap.get(x.get('href'))==target_class),None)
 score=8*rate(recent)+8*rate(exact)+8*rate(same_track)+12*rate(same_class)+12*rate(exact_track)+18*rate(exact_class)
 if latest and latest['finish']<=3:score+=3
 if lc and lc['finish']<=3:score+=8
 if let and let['finish']<=3:score+=9
 if lec and lec['finish']<=3:score+=14
 if lec and lec['finish']==2:score+=2  # narrow defeat at current class is strong repeatability, not a win-vs-loss preference
 if latest and latest.get('field_size') and latest['field_size']>1:score+=3*max(0,1-(latest['finish']-1)/(latest['field_size']-1))
 return {'target_class':target_class,'recent_top3_rate':round(rate(recent),3),'same_class_top3_rate':round(rate(same_class),3),'exact_class_top3_rate':round(rate(exact_class),3),'exact_track_top3_rate':round(rate(exact_track),3),'latest_finish':latest.get('finish') if latest else None,'latest_same_class_finish':lc.get('finish') if lc else None,'latest_exact_track_finish':let.get('finish') if let else None,'latest_exact_class_finish':lec.get('finish') if lec else None,'oral_structure_score':round(score,3)}

def main():
 base=json.loads(BASE.read_text());gold=json.loads(GOLD.read_text());bm={key(r):r for r in base['races']};targets=[bm[key(g)] for g in gold['cases'] if key(g) in bm]
 ids=sorted({str(h['horse_id']) for r in targets for h in r.get('ranked_snapshot',[]) if h.get('horse_id')});hist={};errs=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(profile_history,i):i for i in ids}
  for fu in concurrent.futures.as_completed(fs):
   i=fs[fu]
   try:hist[i]=fu.result()
   except Exception as e:hist[i]=[];errs.append({'horse_id':i,'error':repr(e)})
 # fetch class only for current + recent five links, deduplicated
 urls=sorted({x['href'] for hs in hist.values() for x in hs[:6] if x.get('href')});classmap={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(result_class,u):u for u in urls}
  for fu in concurrent.futures.as_completed(fs):classmap[fs[fu]]=fu.result()
 rows=[];summary=[]
 for r in targets:
  # current row is first profile history row; its class is static pre-race metadata
  anyh=next((h for h in r['ranked_snapshot'] if hist.get(str(h.get('horse_id')))),None);current_href=hist[str(anyh['horse_id'])][0]['href'] if anyh else '';target_class=classmap.get(current_href);tc=track_code(r.get('race_id'))
  rank=[]
  for h in r['ranked_snapshot']:
   x=dict(h);ff=feats(hist.get(str(h.get('horse_id')),[]),str(r['date']),int(r['distance_m']),tc,target_class,classmap);x.update(ff);x['base_score_v1']=f(h.get('score'));x['score']=round(x['base_score_v1']+ff['oral_structure_score'],3);rank.append(x)
  rank.sort(key=lambda x:(-x['score'],int(str(x.get('n') or 999))));rr={**r,'ranked_snapshot':rank};a=analyze_race(rr)
  rows.append({**{k:r.get(k) for k in ('date','track','race_no','race_name','surface','distance_m')},'target_class':target_class,'analysis':a,'ranked_snapshot':rank})
  summary.append({'track':r['track'],'race_no':r['race_no'],'target_class':target_class,'axis':a['axis'],'decision':a['pre_market_decision'],'ticket_count':a['ticket_count'],'top7':[{'n':x['n'],'name':x['name'],'score':x['score'],'latest':x['latest_finish'],'same_class':x['latest_same_class_finish'],'exact_class':x['latest_exact_class_finish'],'exact_track':x['latest_exact_track_finish']} for x in rank[:7]]})
 OUT.write_text(json.dumps({'version':'ORAL_GOLDEN_FAST_V3','history_errors':errs,'class_urls':len(urls),'class_resolved':sum(v is not None for v in classmap.values()),'summary':summary,'races':rows},ensure_ascii=False,indent=2));print(json.dumps({'errors':len(errs),'class_resolved':sum(v is not None for v in classmap.values()),'summary':summary},ensure_ascii=False))
if __name__=='__main__':main()
