#!/usr/bin/env python3
"""Re-score the already sealed 2026-08-29/30 replay without changing predictions.

Some public race-card IDs and JRA result IDs use different access prefixes. This
script joins labels by (date, track, race_no), preserving the sealed prediction
hash and every pre-race field exactly as written.
"""
import csv,json,re
from collections import defaultdict
from pathlib import Path
SEALED=Path('docs/data/replay-2026-08-29-30-sealed.json')
RESULTS=Path('data/race_results_html_2026.csv')
PAYOUTS=Path('data/race_payouts_2026.csv')
FULL=Path('docs/data/replay-2026-08-29-30-full.json')
STATUS=Path('status/replay-2026-08-29-30-evaluation.json')
TARGET={'2026-08-29','2026-08-30'}

def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def integer(v,d=None):
 m=re.search(r'\d+',str(v or ''));return int(m.group()) if m else d
def money(v):
 try:return int(float(str(v or '0').replace(',','')))
 except:return 0
def key(date,track,race_no):return (str(date or ''),str(track or '').strip(),integer(race_no,0))

def main():
 sealed=json.loads(SEALED.read_text(encoding='utf-8'))
 rr=[r for r in rows(RESULTS) if r.get('race_date') in TARGET]
 pp=[r for r in rows(PAYOUTS) if r.get('race_date') in TARGET and r.get('bet_type') in ('3連複','三連複')]
 finish=defaultdict(list);rid_to_key={}
 for r in rr:
  k=key(r.get('race_date'),r.get('course'),r.get('race_no'));rid_to_key[r.get('race_id')]=k
  f=integer(r.get('finish_position'))
  if f and f<=3:finish[k].append((f,str(r.get('horse_no')),r.get('horse_name','')))
 payout={}
 for p in pp:
  k=rid_to_key.get(p.get('race_id'))
  if k:payout[k]=p
 totals={'races':0,'result_matched_races':0,'payout_matched_races':0,'bets':0,'passes':0,'hits':0,'stake':0,'return':0,'axis_survived':0,'candidate_top3_complete':0,'ticket_conversion_failures':0,'archived_pre_race':0,'blind_reconstructed':0}
 out=[]
 for p in sealed.get('races',[]):
  q=dict(p);k=key(p.get('date'),p.get('track'),p.get('race_no'));top=sorted(finish.get(k,[]));pr=payout.get(k,{})
  if len(top)==3:totals['result_matched_races']+=1
  if pr:totals['payout_matched_races']+=1
  actual={n for _,n,_ in top};sel=pr.get('winning_selection','');nums=re.findall(r'\d+',sel);win='-'.join(map(str,sorted(map(int,nums)))) if len(nums)==3 else ''
  tickets=set(p.get('tickets') or []);pas=p.get('decision')=='PASS' or not tickets;hit=bool(win and win in tickets and not pas);axis=str(p.get('axis','')).split()[0]
  cand={str(x).split()[0] for x in [p.get('axis',''),*(p.get('partners') or []),*(p.get('holes') or [])]};cap=len(actual&cand);conv=(len(top)==3 and cap==3 and not hit and not pas);ret=money(pr.get('payout_per_100_yen')) if hit else 0
  q.update({'result_top3':[f'{n} {name}' for _,n,name in top],'trio_result':win,'trio_payout':money(pr.get('payout_per_100_yen')),'hit':hit,'return_amount':ret,'axis_survived':axis in actual,'candidate_top3_captured':cap,'ticket_conversion_failure':conv,'result_join_key':{'date':k[0],'track':k[1],'race_no':k[2]}})
  if len(top)!=3:q['review']='結果照合不成立。予想は封印状態のまま保持。'
  elif pas:q['review']='PASS。結果開封後も事前順位・候補は変更していない。'
  elif hit:q['review']='的中。封印済み買い目に実三連複を含んだ。'
  elif conv:q['review']='候補3頭は捕捉したが買い目変換で落とした。'
  elif axis in actual:q['review']=f'軸は馬券内。候補捕捉{cap}/3で相手側の取りこぼし。'
  else:q['review']=f'軸が馬券外。候補捕捉{cap}/3。軸選定または構造判断の失敗。'
  out.append(q);totals['races']+=1;totals['archived_pre_race']+=int(str(p.get('prediction_source','')).startswith('PRE_RACE'));totals['blind_reconstructed']+=int(p.get('prediction_source')=='BLIND_REPLAY_RECONSTRUCTION');totals['axis_survived']+=int(axis in actual);totals['candidate_top3_complete']+=int(len(top)==3 and cap==3);totals['ticket_conversion_failures']+=int(conv)
  if pas:totals['passes']+=1
  else:totals['bets']+=1;totals['stake']+=int(p.get('stake') or 0);totals['hits']+=int(hit);totals['return']+=ret
 if totals['result_matched_races']!=72:raise SystemExit(f"result match incomplete: {totals['result_matched_races']}/72")
 if totals['payout_matched_races']!=72:raise SystemExit(f"payout match incomplete: {totals['payout_matched_races']}/72")
 totals['hit_rate_pct']=round(100*totals['hits']/totals['bets'],2) if totals['bets'] else 0;totals['roi_pct']=round(100*totals['return']/totals['stake'],2) if totals['stake'] else 0;totals['axis_survival_pct']=round(100*totals['axis_survived']/72,2);totals['candidate_top3_complete_pct']=round(100*totals['candidate_top3_complete']/72,2)
 doc={k:v for k,v in sealed.items() if k!='races'};doc['mode']='SEALED_THEN_SCORED_BY_DATE_TRACK_RACE';doc['evaluation_summary']=totals;doc['races']=out
 FULL.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8');STATUS.write_text(json.dumps({'prediction_hash_sha256':sealed.get('prediction_hash_sha256'),'result_join_policy':'date+track+race_no; sealed prediction content unchanged','summary':totals,'profile_fetch_errors':sealed.get('profile_fetch_errors',[])},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(totals,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
