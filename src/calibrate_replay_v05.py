#!/usr/bin/env python3
import json,itertools,hashlib,statistics
from pathlib import Path
BASE=Path('docs/data/replay-2026-08-29-30-sealed.json')
RESULT=Path('docs/data/replay-2026-08-29-30-full.json')
CFG=Path('docs/data/model-v05-sealed.json')
PRED=Path('docs/data/replay-v05-predictions-sealed.json')
OUT=Path('docs/data/replay-v05-evaluation.json')
STATUS=Path('status/replay-v05-evaluation.json')

def combo(xs): return '-'.join(map(str,sorted(map(int,xs))))
def nums(r): return [str(x.get('n')) for x in (r.get('ranked_snapshot') or [])[:7] if str(x.get('n','')).isdigit()]
def feats(r):
 q=r.get('ranked_snapshot') or []
 if len(q)<5:return {'g1':0,'g2':0,'spread5':0,'unc':1,'starts':0,'avg_unc':1}
 sc=[float(x.get('score',0)) for x in q[:5]]
 return {'g1':sc[0]-sc[1],'g2':sc[1]-sc[2],'spread5':sc[0]-sc[4],'unc':float(q[0].get('uncertainty',1)),'starts':float(q[0].get('starts_before',0)),'avg_unc':sum(float(x.get('uncertainty',1)) for x in q[:3])/3}
def make_tickets(r,shape):
 n=nums(r)
 if len(n)<5:return []
 if shape=='AXIS9':
  pairs=list(itertools.combinations(n[1:6],2))
  return [combo([n[0],a,b]) for a,b in pairs[:-1]][:9]
 if shape=='DUAL9':
  out=[combo([n[0],n[1],x]) for x in n[2:6]]
  for a,b in itertools.combinations(n[2:6],2):
   if len(out)>=9:break
   out.append(combo([n[0],a,b]))
  return list(dict.fromkeys(out))[:9]
 if shape=='GROUP10': return [combo(c) for c in itertools.combinations(n[:5],3)]
 return []
def decide(r,c):
 f=feats(r)
 if f['starts']==0 and f['avg_unc']>=.99 and f['spread5']<c['sparse_spread_pass']: return 'PASS',[]
 if f['g1']>=c['axis_gap'] and f['unc']<=c['axis_unc']: shape='AXIS9'
 elif f['g2']>=c['dual_gap'] or f['spread5']>=c['dual_spread']: shape='DUAL9'
 else: shape='GROUP10'
 return shape,make_tickets(r,shape)
def score(rows,c,outcomes):
 s={'races':len(rows),'bets':0,'passes':0,'hits':0,'stake':0,'return':0}
 byshape={'AXIS9':0,'DUAL9':0,'GROUP10':0,'PASS':0}
 for r in rows:
  shape,t=decide(r,c);byshape[shape]=byshape.get(shape,0)+1
  if shape=='PASS' or not t:s['passes']+=1;continue
  s['bets']+=1;s['stake']+=100*len(t)
  o=outcomes.get((r.get('date'),r.get('track'),int(r.get('race_no') or 0)),{})
  if o.get('trio_result') in set(t):s['hits']+=1;s['return']+=int(o.get('trio_payout') or 0)
 s['hit_rate_pct']=round(100*s['hits']/s['bets'],2) if s['bets'] else 0
 s['roi_pct']=round(100*s['return']/s['stake'],2) if s['stake'] else 0
 s['shapes']=byshape
 return s
def main():
 base=json.loads(BASE.read_text())
 result=json.loads(RESULT.read_text())
 base_rows=[r for r in base.get('races',[]) if r.get('prediction_source')=='BLIND_REPLAY_RECONSTRUCTION']
 result_rows=[r for r in result.get('races',[]) if r.get('prediction_source')=='BLIND_REPLAY_RECONSTRUCTION']
 outcomes={(r.get('date'),r.get('track'),int(r.get('race_no') or 0)):r for r in result_rows}
 train=[r for r in base_rows if r.get('date')=='2026-08-29' or (r.get('date')=='2026-08-30' and int(r.get('race_no') or 0)<=6)]
 hold=[r for r in base_rows if r.get('date')=='2026-08-30' and int(r.get('race_no') or 0)>=7]
 candidates=[]
 for ag in (1.2,1.5,2,2.5,3):
  for au in (.4,.6,.8,1.0):
   for dg in (.3,.5,.8,1.1):
    for ds in (1.5,2.5,3.5,5):
     for sp in (.4,.8,1.2,1.8):
      c={'axis_gap':ag,'axis_unc':au,'dual_gap':dg,'dual_spread':ds,'sparse_spread_pass':sp}
      folds=[]
      for key in sorted({(r.get('date'),r.get('track')) for r in train}):
       rows=[r for r in train if (r.get('date'),r.get('track'))==key]
       if rows:folds.append(score(rows,c,outcomes))
      bets=sum(x['bets'] for x in folds);passes=sum(x['passes'] for x in folds)
      if bets<max(18,int(len(train)*.4)):continue
      mh=statistics.mean(x['hit_rate_pct'] for x in folds);mr=statistics.mean(min(x['roi_pct'],200) for x in folds)
      worst=min((x['hit_rate_pct'] for x in folds),default=0)
      obj=mh*1.0+mr*.10+worst*.35+bets*.08-passes*.04
      candidates.append((obj,c))
 candidates.sort(key=lambda x:-x[0]);best=candidates[0][1]
 cfg={'version':'BLIND_RULE_REPLAY_V0.5_SEALED','training_scope':'2026-08-29 all reconstructed + 2026-08-30 R1-6 reconstructed','holdout_scope':'2026-08-30 R7-12 reconstructed','base_prediction_hash':base.get('prediction_hash_sha256'),'selected_config':best,'policy':['horse ranking foundation unchanged','AXIS9 / DUAL9 / GROUP10 switch','sparse history alone does not force PASS','holdout outcomes are not used to select config']}
 raw=json.dumps(cfg,ensure_ascii=False,separators=(',',':'));cfg['config_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest();CFG.write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
 sealed=[]
 for r in base_rows:
  shape,t=decide(r,best);sealed.append({'date':r.get('date'),'track':r.get('track'),'race_no':r.get('race_no'),'race_name':r.get('race_name'),'axis':r.get('axis'),'shape':shape,'tickets':t,'ticket_count':len(t),'ranked_snapshot':r.get('ranked_snapshot')})
 pp={'version':'BLIND_RULE_REPLAY_V0.5_SEALED','config_hash_sha256':cfg['config_hash_sha256'],'result_data_used':False,'races':sealed}
 praw=json.dumps(pp,ensure_ascii=False,separators=(',',':'));pp['prediction_hash_sha256']=hashlib.sha256(praw.encode()).hexdigest();PRED.write_text(json.dumps(pp,ensure_ascii=False,separators=(',',':')))
 train_s=score(train,best,outcomes);hold_s=score(hold,best,outcomes);all_s=score(base_rows,best,outcomes)
 out={'version':'BLIND_RULE_REPLAY_V0.5_SEALED_THEN_SCORED','config_hash_sha256':cfg['config_hash_sha256'],'prediction_hash_sha256':pp['prediction_hash_sha256'],'training_result':train_s,'holdout_result':hold_s,'full_replay_result':all_s,'comparison_v04':json.loads(Path('docs/data/model-calibration-v04.json').read_text()).get('next_day_diagnostic',{}),'truth_note':'Only holdout_result is treated as unseen after v0.5 sealing. Full replay includes tuning races and is not an unbiased estimate.'}
 txt=json.dumps(out,ensure_ascii=False,indent=2);OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(txt);print(txt)
if __name__=='__main__':main()
