#!/usr/bin/env python3
from __future__ import annotations
import csv,json,math,random,re
from collections import defaultdict,deque
from pathlib import Path
P=Path('data/race_results_html_2025.csv');OUT=Path('status/rolling-axis-validation-2025.json')
TRAIN_START='2025-05-01';TRAIN_END='2025-08-31';HOLD_START='2025-09-01'
FEATURES=['recent_top3','recent_win','near_distance_top3','same_course_top3','same_surface_top3','latest_strength','recent_strength','last3f_strength','position_stability','history_confidence']
def fv(v,d=None):
 try:return float(str(v).strip())
 except:return d
def iv(v,d=None):
 try:return int(float(str(v).strip()))
 except:return d
def corners(v):return [int(x) for x in re.findall(r'\d+',str(v or ''))]
def safe_rate(xs,pred):return sum(1 for x in xs if pred(x))/len(xs) if xs else .3
def feat(hist,row):
 recent=list(hist)[-5:][::-1];dist=iv(row.get('distance_m'),0);course=row.get('course');surface=row.get('surface');near=[x for x in hist if abs((x.get('distance_m') or 0)-dist)<=200][-8:];sc=[x for x in hist if x.get('course')==course][-8:];ss=[x for x in hist if x.get('surface')==surface][-8:]
 top3=safe_rate(recent,lambda x:x['finish']<=3);win=safe_rate(recent,lambda x:x['finish']==1);nd=safe_rate(near,lambda x:x['finish']<=3);cr=safe_rate(sc,lambda x:x['finish']<=3);sr=safe_rate(ss,lambda x:x['finish']<=3)
 latest=recent[0] if recent else None;latest_strength=latest['finish_strength'] if latest else .35;recent_strength=sum(x['finish_strength'] for x in recent)/len(recent) if recent else .35;last3=[x['last3f_strength'] for x in recent if x.get('last3f_strength') is not None];l3=sum(last3)/len(last3) if last3 else .5;pos=[x['front_strength'] for x in recent if x.get('front_strength') is not None];pos_stability=(1-(max(pos)-min(pos))) if len(pos)>=2 else .5;conf=min(1,len(hist)/5)
 return [top3,win,nd,cr,sr,latest_strength,recent_strength,l3,max(0,min(1,pos_stability)),conf]
def score_group(rows,w):return max(range(len(rows)),key=lambda i:(sum(a*b for a,b in zip(rows[i]['x'],w)), -int(rows[i]['horse_no'] or 999)))
def eval_groups(groups,w):
 n=top=wins=0
 for g in groups:
  if len(g)<5:continue
  i=score_group(g,w);n+=1;top+=int(g[i]['finish']<=3);wins+=int(g[i]['finish']==1)
 return {'races':n,'top3':top,'wins':wins,'top3_rate':top/n if n else 0,'win_rate':wins/n if n else 0}
def main():
 with P.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
 by=defaultdict(list)
 for r in raw:by[(r['race_date'],r['race_id'])].append(r)
 # Precompute target-race relative last3f and result-normalized strength only for storage AFTER each race.
 history=defaultdict(lambda:deque(maxlen=20));train=[];hold=[];coverage={'train':0,'hold':0}
 for (date,rid),rr in sorted(by.items()):
  # Pre-race features from history only.
  group=[]
  for r in rr:
   hid=r.get('horse_id');x=feat(history[hid],r);finish=iv(r.get('finish_position'),99);group.append({'horse_id':hid,'horse_no':r.get('horse_no'),'x':x,'finish':finish})
  if TRAIN_START<=date<=TRAIN_END:train.append(group)
  elif date>=HOLD_START:hold.append(group)
  # Open this race's outcome only after all target features were formed.
  l3vals=[(idx,fv(r.get('last3f'))) for idx,r in enumerate(rr) if fv(r.get('last3f')) is not None];l3rank={}
  if l3vals:
   ordered=sorted(l3vals,key=lambda z:z[1]);den=max(1,len(ordered)-1)
   for rank,(idx,_) in enumerate(ordered):l3rank[idx]=1-rank/den
  field=len(rr)
  for idx,r in enumerate(rr):
   finish=iv(r.get('finish_position'),field);strength=max(0,1-(finish-1)/max(1,field-1));cp=corners(r.get('corner_positions'));front=(1-(cp[0]-1)/max(1,field-1)) if cp else None
   history[r.get('horse_id')].append({'date':date,'course':r.get('course'),'surface':r.get('surface'),'distance_m':iv(r.get('distance_m'),0),'finish':finish,'finish_strength':strength,'last3f_strength':l3rank.get(idx),'front_strength':front})
 assert train and hold
 rng=random.Random(20260902);candidates=[]
 # Include interpretable baselines plus deterministic random nonnegative weight vectors.
 candidates.append([1,0,0,0,0,0,0,0,0,0]);candidates.append([0,0,0,0,0,0,1,0,0,0]);candidates.append([1,.5,.6,.5,.3,.4,.6,.2,.1,.2])
 for _ in range(1500):candidates.append([rng.randint(0,10)/10 for _ in FEATURES])
 best=None
 for w in candidates:
  ev=eval_groups(train,w);obj=ev['top3_rate']+.22*ev['win_rate']
  if best is None or obj>best['objective']:best={'weights':w,'objective':obj,'train':ev}
 hold_ev=eval_groups(hold,best['weights']);base_recent=eval_groups(hold,[1,0,0,0,0,0,0,0,0,0]);base_strength=eval_groups(hold,[0,0,0,0,0,0,1,0,0,0])
 payload={'version':'ROLLING_AXIS_VALIDATION_2025_V1','market_features_used':False,'target_result_used_in_features':False,'train_period':[TRAIN_START,TRAIN_END],'holdout_start':HOLD_START,'feature_names':FEATURES,'candidate_weight_vectors':len(candidates),'best_weights':dict(zip(FEATURES,best['weights'])),'train_result':best['train'],'holdout_result':hold_ev,'holdout_baseline_recent_top3':base_recent,'holdout_baseline_recent_strength':base_strength,'policy':'Every target row is featurized before its race result is appended to horse history. Popularity is never read by this script.'};OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print(json.dumps(payload,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
