#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,json,re,sys
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables
from oral_operational_layer import analyze_race

BASE=Path('docs/data/replay-2026-08-29-30-sealed.json')
GOLD=Path('docs/data/oral-chat-golden-cases.json')
OUT=Path('docs/data/oral-golden-fast-v2.json')

def key(r):return (str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0))
def nums(v):return [int(x) for x in re.findall(r'\d+',str(v or ''))]
def f(v,d=0.0):
 try:return float(v)
 except:return d

def parse_history(html):
 ts=normalized_tables(html)
 if not ts or len(ts[0].columns)<12:return []
 out=[]
 for _,rr in ts[0].iterrows():
  vals=[str(x).strip() for x in rr.tolist()];ds=nums(vals[0] if vals else '')
  if len(ds)<3:continue
  dn=nums(vals[3] if len(vals)>3 else '');fn=nums(vals[7] if len(vals)>7 else '');field=nums(vals[5] if len(vals)>5 else '')
  out.append({'date':f'{ds[0]:04d}-{ds[1]:02d}-{ds[2]:02d}','distance_m':dn[-1] if dn else None,'finish':fn[0] if fn else None,'field_size':field[0] if field else None,'carried_weight':f(vals[9],None) if len(vals)>9 else None,'body_weight':(nums(vals[10])[0] if len(vals)>10 and nums(vals[10]) else None),'time':vals[11] if len(vals)>11 else ''})
 return sorted(out,key=lambda x:x['date'],reverse=True)

def feats(hist,date,dist):
 pre=[x for x in hist if x['date']<date and x.get('finish')];recent=pre[:5];exact=[x for x in pre if x.get('distance_m')==dist][:8];near=[x for x in pre if x.get('distance_m') and abs(x['distance_m']-dist)<=200][:8]
 rt=sum(x['finish']<=3 for x in recent)/len(recent) if recent else 0;et=sum(x['finish']<=3 for x in exact)/len(exact) if exact else 0;nt=sum(x['finish']<=3 for x in near)/len(near) if near else 0
 latest=recent[0] if recent else None;le=next((x for x in recent if x.get('distance_m')==dist),None);ln=next((x for x in recent if x.get('distance_m') and abs(x['distance_m']-dist)<=200),None)
 # Oral-like structure score: current/recent exact-condition achievement is intentionally stronger than lifetime averages.
 structure=12*rt+14*et+6*nt
 if latest and latest['finish']<=3:structure+=5
 if le and le['finish']<=3:structure+=12
 elif ln and ln['finish']<=3:structure+=6
 if le and le['finish']==1:structure+=3
 # Field-normalized recent competitiveness, result-independent of target race.
 if latest and latest.get('field_size') and latest['field_size']>1:structure+=5*max(0,1-(latest['finish']-1)/(latest['field_size']-1))
 return {'history_rows_before':len(pre),'recent_top3_rate':round(rt,4),'exact_distance_top3_rate':round(et,4),'near_distance_top3_rate':round(nt,4),'latest_finish':latest.get('finish') if latest else None,'latest_exact_finish':le.get('finish') if le else None,'latest_near_finish':ln.get('finish') if ln else None,'structure_score':round(structure,3)}

def main():
 base=json.loads(BASE.read_text());gold=json.loads(GOLD.read_text());bm={key(r):r for r in base.get('races',[])};targets=[bm[key(g)] for g in gold['cases'] if key(g) in bm]
 ids=sorted({str(h.get('horse_id') or '') for r in targets for h in r.get('ranked_snapshot',[]) if h.get('horse_id')});hist={};errs=[]
 def one(i):return i,parse_history(request_profile(i))
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(one,i):i for i in ids}
  for fu in concurrent.futures.as_completed(fs):
   i=fs[fu]
   try:k,v=fu.result();hist[k]=v
   except Exception as e:hist[i]=[];errs.append({'horse_id':i,'error':repr(e)})
 rows=[]
 for r in targets:
  rank=[];dist=int(r.get('distance_m') or 0)
  for h in r.get('ranked_snapshot',[]):
   x=dict(h);ff=feats(hist.get(str(h.get('horse_id') or ''),[]),str(r.get('date')),dist);x.update(ff);x['base_score_v1']=f(h.get('score'));x['score']=round(x['base_score_v1']+ff['structure_score'],3);rank.append(x)
  rank.sort(key=lambda x:(-x['score'],int(str(x.get('n') or 999))))
  rr={**r,'ranked_snapshot':rank};a=analyze_race(rr)
  rows.append({**{k:r.get(k) for k in ('date','track','race_no','race_name','surface','distance_m')},'analysis':a,'ranked_snapshot':rank})
 OUT.write_text(json.dumps({'version':'ORAL_GOLDEN_FAST_V2','history_fetch_errors':errs,'races':rows},ensure_ascii=False,indent=2));print(json.dumps({'races':len(rows),'profiles':len(ids),'errors':len(errs),'axes':[(x['track'],x['race_no'],x['analysis']['axis'],x['analysis']['pre_market_decision']) for x in rows]},ensure_ascii=False))
if __name__=='__main__':main()
