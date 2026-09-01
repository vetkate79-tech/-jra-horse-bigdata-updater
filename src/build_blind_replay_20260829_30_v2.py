#!/usr/bin/env python3
"""Parallel blind replay for every JRA race on 2026-08-29/30.

Prediction inputs are frozen before result/payout files are opened. Current JRA
profile pages are allowed only as a historical container; rows dated on/after the
target date are removed before feature calculation.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables

CARDS=Path('docs/data/race_cards.json'); ARCHIVE=Path('docs/data/replay-demo-2026-08-29-30.json')
PROFILE25=Path('data/horse_profiles_2025.csv'); RESULTS25=Path('data/race_results_html_2025.csv')
RESULTS26=Path('data/race_results_html_2026.csv'); PAYOUTS26=Path('data/race_payouts_2026.csv')
SEALED=Path('docs/data/replay-2026-08-29-30-sealed.json'); FULL=Path('docs/data/replay-2026-08-29-30-full.json')
STATUS=Path('status/replay-2026-08-29-30-evaluation.json'); TARGET={'2026-08-29','2026-08-30'}
MODEL='BLIND_RULE_REPLAY_V0.2'

def csvrows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def num(v,d=None):
 try:return float(str(v).replace(',',''))
 except:return d
def integer(v,d=None):
 m=re.search(r'\d+',str(v or ''));return int(m.group()) if m else d
def ndate(v):
 s=str(v or '').replace('年','-').replace('月','-').replace('日','').replace('/','-').replace('.','-')
 m=re.search(r'(20\d{2})-(\d{1,2})-(\d{1,2})',s)
 return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''
def val(row,keys):
 for c,v in row.items():
  if any(k in str(c) for k in keys) and str(v).strip() not in ('','nan','None'):return str(v).strip()
 return ''
def surf_dist(row):
 text=' '.join(row.values());m=re.search(r'(芝|ダート|ダ)\s*([0-9]{3,4})',text)
 return (('ダート' if m.group(1)!='芝' else '芝'),int(m.group(2))) if m else ('',None)
def parse_profile_rows(html):
 out=[]
 for table in normalized_tables(html):
  if not any(('レース名' in c or '競走名' in c) for c in table.columns):continue
  for _,rr in table.iterrows():
   r={str(c):str(v).strip() for c,v in rr.items()};date=ndate(val(r,['年月日','日付']));finish=integer(val(r,['着順']))
   if not date or finish is None:continue
   s,d=surf_dist(r)
   out.append({'date':date,'finish':finish,'race_name':val(r,['レース名','競走名']),'surface':s,'distance_m':d,'last3f':num(val(r,['上り3F','上がり3F','上り']))})
 return sorted(out,key=lambda x:x['date'],reverse=True)
def fetch_histories(races):
 ids=sorted({h.get('horse_id','') for r in races for h in r.get('horses',[]) if h.get('horse_id')});out={};err=[]
 def one(hid):return hid,parse_profile_rows(request_profile(hid))
 with ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(one,h):h for h in ids}
  for i,f in enumerate(as_completed(fs),1):
   hid=fs[f]
   try:k,v=f.result();out[k]=v
   except Exception as e:out[hid]=[];err.append({'horse_id':hid,'error':repr(e)})
   if i%100==0:print(f'profiles {i}/{len(ids)} errors={len(err)}',flush=True)
 return out,err
def baseline25():return {r.get('horse_id',''):r for r in csvrows(PROFILE25)}
def people25():
 j=defaultdict(lambda:[0,0]);t=defaultdict(lambda:[0,0])
 for r in csvrows(RESULTS25):
  f=integer(r.get('finish_position'))
  if f is None:continue
  for k,b in ((r.get('jockey',''),j),(r.get('trainer',''),t)):
   if k:b[k][0]+=1;b[k][1]+=int(f<=3)
 def rate(b,k):
  n,x=b.get(k,[0,0]);return (x+2)/(n+8) if n else .25
 return lambda k:rate(j,k),lambda k:rate(t,k)
def features(h,r,hist,b,jr,tr):
 starts25=int(num(b.get('starts'),0) or 0);top325=int(num(b.get('top3'),0) or 0);starts26=len(hist);top326=sum(x['finish']<=3 for x in hist)
 starts=starts25+starts26;show=(top325+top326+1.5)/(starts+5) if starts else .30;recent=hist[:5]
 if recent:
  ws=[5,4,3,2,1][:len(recent)];rec=sum(w*(1/max(1,min(18,x['finish']))) for w,x in zip(ws,recent))/sum(ws);rec=min(1,rec*3.2)
 else:
  av=num(b.get('avg_finish'));rec=max(0,min(1,(12-(av or 12))/11)) if av else .35
 matches=[x for x in hist if x['surface']==r.get('surface') and x['distance_m'] and abs(x['distance_m']-int(r.get('distance_m') or 0))<=300]
 cond=(sum(x['finish']<=3 for x in matches)+1)/(len(matches)+3) if matches else show
 ls=[x['last3f'] for x in recent if x.get('last3f')];l3=.5 if not ls else max(0,min(1,(40-min(ls))/8));j=jr(h.get('jockey',''));tt=tr(h.get('trainer',''));unc=1-min(1,starts/5)
 score=45*show+25*rec+10*cond+8*j+7*tt+5*l3-8*unc
 return {'score':round(score,3),'starts_before':starts,'show_rate_prior':round(show,4),'recent_form':round(rec,4),'condition_fit':round(cond,4),'uncertainty':round(unc,4)}
def tickets7(rank):
 ns=[str(x['n']) for x in rank[:6]];out=[]
 for i,j in [(1,2),(1,3),(1,4),(2,3),(2,4),(3,4),(1,5)]:
  if len(ns)>j:out.append('-'.join(map(str,sorted(map(int,[ns[0],ns[i],ns[j]])))))
 return list(dict.fromkeys(out))
def archived():
 d=json.loads(ARCHIVE.read_text());return {(r['date'],r['track'],int(r['race_no'])):r for r in d.get('races',[]) if r.get('date') in TARGET}
def archive_tickets(a):
 ax=str(a.get('axis','')).split()[0];p=[str(x).split()[0] for x in a.get('partners',[])];z=[str(x).split()[0] for x in a.get('holes',[])];o=set()
 if not ax.isdigit():return []
 for b in p:
  for c in p+z:
   if b.isdigit() and c.isdigit() and len({ax,b,c})==3:o.add('-'.join(map(str,sorted(map(int,[ax,b,c])))))
 return sorted(o,key=lambda s:tuple(map(int,s.split('-'))))
def make_sealed():
 cards=json.loads(CARDS.read_text());races=sorted([r for r in cards.get('races',[]) if r.get('date') in TARGET],key=lambda x:(x['date'],x['track'],int(x['race_no'])));base=baseline25();jr,tr=people25();am=archived();allhist,errors=fetch_histories(races);out=[];excluded=0
 for i,r in enumerate(races,1):
  rank=[]
  for h in r.get('horses',[]):
   raw=allhist.get(h.get('horse_id',''),[]);hist=[x for x in raw if x['date']<r['date']];excluded+=sum(x['date']>=r['date'] for x in raw)
   rank.append({'n':str(h.get('n')),'name':h.get('name',''),'horse_id':h.get('horse_id',''),**features(h,r,hist,base.get(h.get('horse_id',''),{}),jr,tr)})
  rank.sort(key=lambda x:(-x['score'],int(x['n'])));key=(r['date'],r['track'],int(r['race_no']));a=am.get(key)
  common={x:r.get(x) for x in ('race_id','date','track','race_no','race_name','surface','distance_m')}
  if a:
   ts=archive_tickets(a);p={**common,'prediction_source':a.get('prediction_source','PRE_RACE_CONVERSATION_LOG'),'type_label':a.get('type_label','事前予想'),'decision':a.get('decision','BUY'),'axis':a.get('axis'),'partners':a.get('partners',[]),'holes':a.get('holes',[]),'formation':a.get('formation'),'ticket_count':len(ts) or int(a.get('ticket_count') or 0),'stake':int(a.get('stake') or 100*(len(ts) or int(a.get('ticket_count') or 0))),'tickets':ts,'model_version':'ARCHIVED_PRE_RACE','ranked_snapshot':rank[:10]}
  else:
   top=rank[0] if rank else None;sec=rank[1] if len(rank)>1 else None;gap=top['score']-sec['score'] if top and sec else 0;avg=sum(x['starts_before'] for x in rank[:5])/max(1,min(5,len(rank)));none=rank and all(x['starts_before']==0 for x in rank)
   if none:dec,reason='PASS','全頭で事前実走データ不足'
   elif avg<1.5:dec,reason='PASS','上位候補の事前データ不足'
   elif gap>=7:dec,reason='A','中心1頭の評価差が大きい'
   elif gap>=3.5:dec,reason='B','中心候補が比較的明確'
   elif gap>=1.5:dec,reason='C','上位差が小さく展開依存'
   else:dec,reason='PASS','軸候補の評価差が小さい'
   ts=[] if dec=='PASS' else tickets7(rank);p={**common,'prediction_source':'BLIND_REPLAY_RECONSTRUCTION','type_label':'結果遮断再現','decision':dec,'axis':f"{top['n']} {top['name']}" if top else '判定不能','partners':[f"{x['n']} {x['name']}" for x in rank[1:4]],'holes':[f"{x['n']} {x['name']}" for x in rank[4:6]],'pre_note':reason+'。人気・オッズ・当該レース結果は予想生成に不使用。','formation':'PASS' if not ts else '三連複 1頭軸・再現7点','ticket_count':len(ts),'stake':100*len(ts),'tickets':ts,'model_version':MODEL,'ranked_snapshot':rank[:10]}
  out.append(p)
  if i%12==0:print(f'prediction {i}/{len(races)}',flush=True)
 payload={'mode':'BLIND_PRE_RACE_RECONSTRUCTION','dates':sorted(TARGET),'race_count':len(out),'model_version':MODEL,'leakage_policy':'Prediction snapshot is written before target result/payout files are opened. JRA profile rows dated on/after each target date are excluded. Popularity and odds are not prediction inputs.','profile_fetch_errors':errors,'excluded_profile_rows_at_or_after_target':excluded,'races':out};raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest();SEALED.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');return payload
def score(s):
 if not SEALED.exists():raise RuntimeError('sealed first')
 rr=[x for x in csvrows(RESULTS26) if x.get('race_date') in TARGET];pp=[x for x in csvrows(PAYOUTS26) if x.get('race_date') in TARGET and x.get('bet_type') in ('3連複','三連複')];fin=defaultdict(list)
 for x in rr:
  f=integer(x.get('finish_position'))
  if f and f<=3:fin[x.get('race_id')].append((f,str(x.get('horse_no')),x.get('horse_name','')))
 pay={x.get('race_id'):x for x in pp};tot={'races':0,'bets':0,'passes':0,'hits':0,'stake':0,'return':0,'axis_survived':0,'candidate_top3_complete':0,'ticket_conversion_failures':0,'archived_pre_race':0,'blind_reconstructed':0};out=[]
 for p in s['races']:
  q=dict(p);top=sorted(fin.get(p.get('race_id'),[]));actual={n for _,n,_ in top};pr=pay.get(p.get('race_id'),{});w='-'.join(map(str,sorted(map(int,re.findall(r'\d+',pr.get('winning_selection','')))))) if pr.get('winning_selection') else '';ts=set(p.get('tickets') or []);pas=p.get('decision')=='PASS' or not ts;hit=(w in ts) if not pas else False;ax=str(p.get('axis','')).split()[0];cand={str(x).split()[0] for x in [p.get('axis',''),*(p.get('partners') or []),*(p.get('holes') or [])]};cap=len(actual&cand);conv=cap==3 and not hit and not pas;ret=int(num(pr.get('payout_per_100_yen'),0) or 0) if hit else 0
  q.update({'result_top3':[f'{n} {name}' for _,n,name in top],'trio_result':w,'trio_payout':int(num(pr.get('payout_per_100_yen'),0) or 0),'hit':hit,'return_amount':ret,'axis_survived':ax in actual,'candidate_top3_captured':cap,'ticket_conversion_failure':conv})
  if pas:q['review']='PASS。結果開封後も事前順位・候補は変更していない。'
  elif hit:q['review']='的中。封印済み買い目に実三連複を含んだ。'
  elif conv:q['review']='候補3頭は捕捉したが買い目変換で落とした。'
  elif ax in actual:q['review']=f'軸は馬券内。候補捕捉{cap}/3で相手側の取りこぼし。'
  else:q['review']=f'軸が馬券外。候補捕捉{cap}/3。軸選定または構造判断の失敗。'
  out.append(q);tot['races']+=1;tot['archived_pre_race']+=int(str(p.get('prediction_source','')).startswith('PRE_RACE'));tot['blind_reconstructed']+=int(p.get('prediction_source')=='BLIND_REPLAY_RECONSTRUCTION');tot['axis_survived']+=int(ax in actual);tot['candidate_top3_complete']+=int(cap==3);tot['ticket_conversion_failures']+=int(conv)
  if pas:tot['passes']+=1
  else:tot['bets']+=1;tot['stake']+=int(p.get('stake') or 0);tot['hits']+=int(hit);tot['return']+=ret
 tot['hit_rate_pct']=round(100*tot['hits']/tot['bets'],2) if tot['bets'] else 0;tot['roi_pct']=round(100*tot['return']/tot['stake'],2) if tot['stake'] else 0;tot['axis_survival_pct']=round(100*tot['axis_survived']/tot['races'],2);tot['candidate_top3_complete_pct']=round(100*tot['candidate_top3_complete']/tot['races'],2)
 doc={k:v for k,v in s.items() if k!='races'};doc['mode']='SEALED_THEN_SCORED';doc['evaluation_summary']=tot;doc['races']=out;FULL.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8');STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({'prediction_hash_sha256':s['prediction_hash_sha256'],'summary':tot,'profile_fetch_errors':s.get('profile_fetch_errors',[])},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(tot,ensure_ascii=False,indent=2))
def main():
 s=make_sealed();assert len(s['races'])==72;score(s)
if __name__=='__main__':main()
