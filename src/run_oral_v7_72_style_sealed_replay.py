#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,csv,hashlib,itertools,json,re,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile
from oral_operational_layer import analyze_race
from run_oral_v6_72_sealed_replay import key,f,parse_profile,hist_features,effective,combo

CARDS=Path('docs/data/race_cards.json')
BASE=Path('docs/data/replay-2026-08-29-30-sealed.json')
STYLE_SOURCES=(Path('data/race_results_html_2025.csv'),Path('data/race_results_html_2026.csv'))
STYLE_CUTOFF='2026-08-29'
OUT=Path('docs/data/oral-v7-72-style-predictions-sealed.json')
STATUS=Path('status/oral-v7-72-style-predictions-sealed.json')
MODEL='ORAL_V7_72_PRETARGET_STYLE_SEALED_REPLAY'

STYLE_LABELS={'ESCAPE':'逃げ','FRONT':'先行','STALK':'好位差し','CLOSER':'差し','DEEP_CLOSER':'追込','UNKNOWN':'判定待ち'}
def parse_corners(v):return[int(x) for x in re.findall(r'\d+',str(v or ''))]

def load_pre_target_styles():
 rows=[];max_date='';excluded_target_or_later=0
 for p in STYLE_SOURCES:
  if not p.exists():continue
  with p.open(encoding='utf-8-sig',newline='') as fh:
   for r in csv.DictReader(fh):
    d=str(r.get('race_date') or '')
    if d and d>=STYLE_CUTOFF:
     excluded_target_or_later+=1;continue
    if d:max_date=max(max_date,d)
    rows.append(r)
 field_sizes=defaultdict(int)
 for r in rows:
  rid=str(r.get('race_id') or '')
  if rid and r.get('horse_id'):field_sizes[rid]+=1
 samples=defaultdict(list)
 for r in rows:
  hid=str(r.get('horse_id') or '');rid=str(r.get('race_id') or '');corners=parse_corners(r.get('corner_positions'));n=field_sizes.get(rid,0)
  if not hid or not corners or n<3:continue
  first,last=corners[0],corners[-1]
  fr=max(0.0,min(1.0,(first-1)/max(1,n-1)));lr=max(0.0,min(1.0,(last-1)/max(1,n-1)))
  samples[hid].append((first,last,fr,lr))
 styles={}
 for hid,ss in samples.items():
  starts=len(ss);escape=sum(1 for a,_,_,_ in ss if a==1)/starts;avg=sum((a+b)/2 for _,_,a,b in ss)/starts
  if escape>=.5 or avg<=.07:code='ESCAPE'
  elif avg<=.28:code='FRONT'
  elif avg<=.45:code='STALK'
  elif avg<=.70:code='CLOSER'
  else:code='DEEP_CLOSER'
  styles[hid]={'running_style':code,'running_style_label':STYLE_LABELS[code],'running_style_sample_starts':starts,'running_style_provisional':starts<3,'escape_rate':round(escape,4),'average_position_ratio':round(avg,4)}
 return styles,{'cutoff_exclusive':STYLE_CUTOFF,'source_rows_used':len(rows),'max_source_date_used':max_date,'excluded_target_or_later_rows':excluded_target_or_later,'horse_styles_resolved':len(styles)}

def main_score(h):
 s=f(h.get('score'))*.52+f(h.get('oral_structure_score'))
 if int(h.get('latest_exact_course_finish') or 99)<=5:s+=8
 if int(h.get('latest_finish') or 99)<=5:s+=4
 if f(h.get('exact_distance_top3_rate'))>=.50:s+=7
 return s

def pick_main(hs,axis):
 elig=[]
 for h in hs:
  if h['n']==axis['n']:continue
  if int(h.get('latest_finish') or 99)<=7 or int(h.get('latest_exact_course_finish') or 99)<=5 or f(h.get('exact_distance_top3_rate'))>=.50:
   x=dict(h);x['main_score']=round(main_score(x),3);elig.append(x)
 elig.sort(key=lambda x:(-x['main_score'],int(x['n'])))
 diff=[x for x in elig if x.get('running_style')!='UNKNOWN' and x.get('running_style')!=axis.get('running_style')]
 out=diff[:3]
 for x in elig:
  if len(out)>=3:break
  if x['n'] not in {y['n'] for y in out}:out.append(x)
 return out

def pick_holes(hs,axis,main,recovery):
 used={axis['n'],*[x['n'] for x in main]};rest=[dict(x) for x in hs if x['n'] not in used]
 if recovery:
  cand=[x for x in rest if int(x.get('latest_finish') or 99) in (3,4)]
  cand.sort(key=lambda x:(int(x.get('latest_finish') or 99),-main_score(x),int(x['n'])))
  if len(cand)<2:
   extra=[x for x in rest if int(x.get('latest_finish') or 99)<=4 and x['n'] not in {y['n'] for y in cand}]
   extra.sort(key=lambda x:(int(x.get('latest_finish') or 99),-main_score(x),int(x['n'])));cand+=extra
  return cand[:2]
 rest.sort(key=lambda x:(-f(x.get('score')),-f(x.get('oral_structure_score')),int(x['n'])))
 holes=rest[:3]
 if 'ESCAPE' not in {x.get('running_style') for x in main+holes}:
  esc=[x for x in rest if x.get('running_style')=='ESCAPE' and x['n'] not in {y['n'] for y in holes}]
  esc.sort(key=lambda x:(-f(x.get('score')),-f(x.get('oral_structure_score')),int(x['n'])))
  if esc:holes.append(esc[0])
 return holes[:4]

def compatible(m,h,axis_style):
 ms=m.get('running_style');hs=h.get('running_style');latest=int(m.get('latest_finish') or 99)
 if ms=='UNKNOWN' or hs=='UNKNOWN':return True
 if latest>7:return hs=='ESCAPE'
 if ms in ('FRONT','ESCAPE'):return hs!=axis_style
 if ms in ('CLOSER','DEEP_CLOSER'):return hs in ('CLOSER','STALK') and hs!=ms
 if ms=='STALK':return hs in ('FRONT','ESCAPE','DEEP_CLOSER')
 return ms!=hs

def make_tickets(axis,main,holes,recovery):
 out=[];a=axis['n']
 for x,y in itertools.combinations(main,2):out.append(combo(a,x['n'],y['n']))
 if recovery:
  for m in main:
   for h in holes:out.append(combo(a,m['n'],h['n']))
 else:
  for m in main:
   for h in holes:
    if compatible(m,h,axis.get('running_style')):out.append(combo(a,m['n'],h['n']))
 return list(dict.fromkeys(out))[:9]

def main():
 cards=json.loads(CARDS.read_text());base=json.loads(BASE.read_text());bm={key(r):r for r in base.get('races',[])}
 styles,style_audit=load_pre_target_styles()
 assert not style_audit['max_source_date_used'] or style_audit['max_source_date_used']<STYLE_CUTOFF,style_audit
 ids=sorted({str(h.get('horse_id') or '') for r in cards.get('races',[]) for h in r.get('horses',[]) if h.get('horse_id')});hist={};errs=[]
 def one(i):return i,parse_profile(request_profile(i))
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(one,i):i for i in ids}
  for n,fu in enumerate(concurrent.futures.as_completed(fs),1):
   i=fs[fu]
   try:k,v=fu.result();hist[k]=v
   except Exception as e:hist[i]=[];errs.append({'horse_id':i,'error':repr(e)})
   if n%100==0:print(f'profiles {n}/{len(ids)} errors={len(errs)}',flush=True)
 rows=[];style_used=0;style_unknown=0
 for r in cards.get('races',[]):
  b=bm.get(key(r),{});base_by_id={str(x.get('horse_id') or ''):x for x in b.get('ranked_snapshot',[])};base_floor=min([f(x.get('score'),20) for x in b.get('ranked_snapshot',[])] or [20.0]);hs=[]
  for idx,h in enumerate(r.get('horses',[])):
   hid=str(h.get('horse_id') or '');old=base_by_id.get(hid,{});feat=hist_features(hist.get(hid,[]),str(r['date']),int(r.get('distance_m') or 0),str(r.get('track') or ''))
   base_score=f(old.get('score'),max(12.0,base_floor-.20*(idx+1)));unc=f(old.get('uncertainty'),1.0 if feat['history_rows_before']==0 else max(0.0,1-min(5,feat['history_rows_before'])/5));score=effective(base_score,feat['oral_structure_score'],unc)
   st=styles.get(hid,{'running_style':'UNKNOWN','running_style_label':'判定待ち','running_style_sample_starts':0,'running_style_provisional':True})
   if st['running_style']=='UNKNOWN':style_unknown+=1
   else:style_used+=1
   x={'n':str(h.get('n')),'name':h.get('name'),'horse_id':hid,'base_score_v1':round(base_score,3),'uncertainty':round(unc,3),'score':score,**st,**feat};hs.append(x)
  hs.sort(key=lambda x:(-f(x['score']),int(x['n'])))
  rr={**b,'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'ranked_snapshot':hs}
  a=analyze_race(rr);axis=next((x for x in hs if x['n']==str((a.get('axis') or {}).get('horse_no'))),hs[0] if hs else {})
  recovery=bool(axis.get('latest_finish') and int(axis['latest_finish'])>3 and f(axis.get('exact_distance_top3_rate'))>=.60)
  if recovery and a.get('pre_market_decision')=='BUY':a['pre_market_decision']='CAUTION';a['classification']='C';a['decision_override_reason']='過去同距離実績は高いが直近馬券外のため復調前提軸として慎重化'
  mains=pick_main(hs,axis);holes=pick_holes(hs,axis,mains,recovery);ts=make_tickets(axis,mains,holes,recovery) if a.get('pre_market_decision')!='PASS' else []
  a['model_version']=MODEL;a['recovery_axis']=recovery;a['axis_running_style']=axis.get('running_style');a['axis_running_style_label']=axis.get('running_style_label');a['role_main_partners']=[{'horse_no':x['n'],'horse_name':x['name'],'running_style':x.get('running_style'),'running_style_label':x.get('running_style_label')} for x in mains];a['role_holes']=[{'horse_no':x['n'],'horse_name':x['name'],'running_style':x.get('running_style'),'running_style_label':x.get('running_style_label')} for x in holes];a['partner_roles']=a['role_main_partners']+a['role_holes'];a['trio_tickets']=ts;a['ticket_count']=len(ts);a['ticket_shape']='ROLE_DIVERSIFIED_AXIS_V7_PRETARGET_STYLE' if ts else 'PASS';a['running_style_replay_policy']='JRA corner positions from races strictly before 2026-08-29 only';a['leakage_policy']='profile rows date < target; running-style rows date < 2026-08-29; no target result/popularity/odds used'
  rows.append({'race_id':r.get('race_id'),'date':r['date'],'track':r['track'],'race_no':r['race_no'],'race_name':r.get('race_name'),'surface':r.get('surface'),'distance_m':r.get('distance_m'),'analysis':a})
 payload={'version':MODEL,'mode':'SEALED_PRE_RESULT_REPLAY_WITH_PRETARGET_STYLE','race_count':len(rows),'profile_count':len(ids),'profile_fetch_errors':errs,'result_data_used':False,'target_result_rows_used':False,'odds_popularity_used':False,'post_target_running_style_used':False,'running_style_source_audit':style_audit,'runner_style_assignments_resolved':style_used,'runner_style_assignments_unknown':style_unknown,'races':rows}
 canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();txt=json.dumps(payload,ensure_ascii=False,indent=2);OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({'version':MODEL,'race_count':len(rows),'profile_count':len(ids),'errors':len(errs),'running_style_source_audit':style_audit,'runner_style_assignments_resolved':style_used,'runner_style_assignments_unknown':style_unknown,'prediction_hash_sha256':payload['prediction_hash_sha256']},ensure_ascii=False,indent=2));print(json.dumps({'race_count':len(rows),'profiles':len(ids),'errors':len(errs),'style_audit':style_audit,'style_resolved':style_used,'style_unknown':style_unknown,'prediction_hash_sha256':payload['prediction_hash_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
