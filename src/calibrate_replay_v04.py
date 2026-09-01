#!/usr/bin/env python3
import json,itertools,statistics
from pathlib import Path
SRC=Path('docs/data/replay-2026-08-29-30-full.json');OUT=Path('docs/data/model-calibration-v04.json');STATUS=Path('status/model-calibration-v04.json')
def combo(nums):return '-'.join(map(str,sorted(map(int,nums))))
def tickets(r,k):
 q=r.get('ranked_snapshot') or [];n=[str(x.get('n')) for x in q[:7] if str(x.get('n','')).isdigit()]
 if len(n)<3:return []
 if k=='AXIS7':
  p=[(1,2),(1,3),(1,4),(2,3),(2,4),(3,4),(1,5)];return list(dict.fromkeys(combo([n[0],n[i],n[j]]) for i,j in p if j<len(n)))
 if k=='DUAL9':
  out=[]
  for x in n[2:6]:out.append(combo([n[0],n[1],x]))
  for x,y in itertools.combinations(n[2:6],2):
   if len(out)>=9:break
   out.append(combo([n[0],x,y]))
  return list(dict.fromkeys(out))[:9]
 if k=='GROUP10':return [combo(c) for c in itertools.combinations(n[:5],3)][:10]
 return []
def feat(r):
 q=r.get('ranked_snapshot') or []
 if len(q)<2:return 0,1,0
 return float(q[0].get('score',0))-float(q[1].get('score',0)),float(q[0].get('uncertainty',1)),float(q[0].get('starts_before',0))
def decide(r,c):
 gap,unc,starts=feat(r)
 if gap>=c['axis_gap']:k='AXIS7'
 elif gap>=c['dual_gap']:k='DUAL9'
 else:k='GROUP10'
 # only hard PASS when field evidence is extremely thin AND ranking gap is tiny
 if starts==0 and unc>=0.99 and gap<c['zero_history_gap']:return 'PASS',[]
 return k,tickets(r,k)
def score(rows,c):
 s={'races':len(rows),'bets':0,'passes':0,'hits':0,'stake':0,'return':0}
 for r in rows:
  k,t=decide(r,c)
  if k=='PASS' or not t:s['passes']+=1;continue
  s['bets']+=1;s['stake']+=100*len(t)
  if r.get('trio_result') in set(t):s['hits']+=1;s['return']+=int(r.get('trio_payout') or 0)
 s['hit_rate_pct']=round(100*s['hits']/s['bets'],2) if s['bets'] else 0;s['roi_pct']=round(100*s['return']/s['stake'],2) if s['stake'] else 0
 return s
def main():
 d=json.loads(SRC.read_text());rows=[r for r in d.get('races',[]) if r.get('prediction_source')=='BLIND_REPLAY_RECONSTRUCTION'];train=[r for r in rows if r.get('date')=='2026-08-29'];test=[r for r in rows if r.get('date')=='2026-08-30'];tracks=sorted({r.get('track') for r in train})
 cs=[]
 for a in (1.5,2,3,4,5):
  for du in (.5,.8,1.2,1.6):
   if du>=a:continue
   for zg in (.2,.5,.8,1.2):
    c={'axis_gap':a,'dual_gap':du,'zero_history_gap':zg};fold=[]
    for tr in tracks:
     val=[r for r in train if r.get('track')==tr];fold.append(score(val,c))
    avg_hit=statistics.mean(x['hit_rate_pct'] for x in fold);avg_roi=statistics.mean(min(x['roi_pct'],250) for x in fold);bets=sum(x['bets'] for x in fold);passes=sum(x['passes'] for x in fold)
    obj=avg_hit*.7+avg_roi*.12+bets*.18-passes*.08
    cs.append((obj,c,fold))
 cs.sort(key=lambda x:-x[0]);_,best,folds=cs[0];train_s=score(train,best);test_s=score(test,best)
 out={'version':'BLIND_RULE_REPLAY_V0.4_CROSS_TRACK','method':'8/29 cross-track robustness; 8/30 diagnostic','selected_config':best,'folds':[{'track':t,**s} for t,s in zip(tracks,folds)],'calibration_result':train_s,'next_day_diagnostic':test_s,'policy':['same horse-ranking foundation','switch AXIS7 / DUAL9 / GROUP10 by score gap','avoid blanket PASS caused only by sparse profile history','do not promote until future unseen weekends confirm']}
 raw=json.dumps(out,ensure_ascii=False,indent=2);OUT.write_text(raw);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(raw);print(raw)
if __name__=='__main__':main()
