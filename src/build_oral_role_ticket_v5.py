#!/usr/bin/env python3
from __future__ import annotations
import itertools,json
from pathlib import Path
V4=Path('docs/data/oral-golden-fast-v4.json');FD=Path('status/oral-full-field-role-diagnostic-v5.json');ST=Path('status/oral-golden-running-style-diagnostic.json');OUT=Path('docs/data/oral-golden-fast-v5.json')

def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def f(v,d=0.0):
 try:return float(v)
 except:return d
def combo(axis,a,b):return '-'.join(map(str,sorted(map(int,[axis,a,b]))))

def main_score(h):
 s=f(h.get('secondary_role_score'))+.5*f(h.get('v4_score'))
 if int(h.get('exact_class_top3_count') or 0)>=2:s+=10
 if f(h.get('exact_track_top3_rate'))>=.5:s+=8
 if h.get('latest_finish') and int(h['latest_finish'])<=5:s+=4
 return s

def choose_main(horses,axis_no,axis_style,n=3):
 eligible=[]
 for h in horses:
  if h['n']==axis_no:continue
  latest=int(h.get('latest_finish') or 99);course=f(h.get('exact_track_top3_rate'))
  if latest<=7 or course>=.5:
   x=dict(h);x['main_score']=round(main_score(x),3);eligible.append(x)
 eligible.sort(key=lambda x:(-x['main_score'],int(x['n'])))
 diverse=[x for x in eligible if x.get('running_style')!=axis_style]
 chosen=diverse[:n]
 if len(chosen)<n:
  for x in eligible:
   if x['n'] not in {y['n'] for y in chosen}:chosen.append(x)
   if len(chosen)>=n:break
 return chosen

def choose_holes(horses,axis_no,main,recovery,axis_style):
 used={axis_no,*[x['n'] for x in main]};rest=[dict(x) for x in horses if x['n'] not in used]
 if recovery:
  near=[]
  for x in rest:
   lf=int(x.get('latest_same_class_finish') or 99)
   if lf in (3,4):near.append(x)
  near.sort(key=lambda x:(int(x.get('latest_same_class_finish') or 99),-f(x.get('secondary_role_score')),int(x['n'])))
  if len(near)<2:
   more=[x for x in rest if int(x.get('latest_finish') or 99)<=4 and x['n'] not in {y['n'] for y in near}]
   more.sort(key=lambda x:(int(x.get('latest_finish') or 99),-f(x.get('secondary_role_score')),int(x['n'])));near+=more
  return near[:2]
 rest.sort(key=lambda x:(-f(x.get('v4_score')),-f(x.get('secondary_role_score')),int(x['n'])))
 holes=rest[:3]
 styles={x.get('running_style') for x in main+holes}
 if 'ESCAPE' not in styles:
  esc=[x for x in rest if x.get('running_style')=='ESCAPE' and x['n'] not in {y['n'] for y in holes}]
  esc.sort(key=lambda x:(-f(x.get('v4_score')),-f(x.get('secondary_role_score')),int(x['n'])))
  if esc:holes.append(esc[0])
 return holes[:4]

def compatible(main_h,hole,axis_style):
 ms=main_h.get('running_style');hs=hole.get('running_style');latest=int(main_h.get('latest_same_class_finish') or main_h.get('latest_finish') or 99)
 if latest>7:return hs=='ESCAPE'
 if ms in ('FRONT','ESCAPE'):
  return hs!=axis_style
 if ms in ('CLOSER','DEEP_CLOSER'):
  return hs in ('CLOSER','STALK') and hs!=ms
 if ms=='STALK':return hs in ('FRONT','ESCAPE','DEEP_CLOSER')
 return ms!=hs

def make_tickets(axis,main,holes,recovery):
 a=axis;out=[]
 for x,y in itertools.combinations(main,2):out.append(combo(a,x['n'],y['n']))
 if recovery:
  for m in main:
   for h in holes:out.append(combo(a,m['n'],h['n']))
  return list(dict.fromkeys(out))[:9]
 for m in main:
  for h in holes:
   if compatible(m,h,axis.get('running_style')):out.append(combo(a['n'],m['n'],h['n']))
 return list(dict.fromkeys(out))[:9]

def main():
 v=json.loads(V4.read_text());fd=json.loads(FD.read_text());st=json.loads(ST.read_text());fm={key(r):r for r in fd['races']};sm={key(r):r for r in st['races']};rows=[];summary=[]
 for r in v['races']:
  k=key(r);diag=fm[k];styles={x['n']:x.get('running_style') for x in sm[k]['horses']};horses=[]
  for x in diag['all_field_roles']:
   y=dict(x);y['running_style']=styles.get(y['n']);horses.append(y)
  axis_no=str(r['analysis']['axis']['horse_no']);axis=next(x for x in horses if x['n']==axis_no);recovery=bool(r['analysis'].get('recovery_axis'));mains=choose_main(horses,axis_no,axis.get('running_style'),3);holes=choose_holes(horses,axis_no,mains,recovery,axis.get('running_style'));tickets=make_tickets(axis,mains,holes,recovery)
  a=dict(r['analysis']);a['role_main_partners']=[{'horse_no':x['n'],'horse_name':x['name'],'running_style':x.get('running_style'),'main_score':x.get('main_score')} for x in mains];a['role_holes']=[{'horse_no':x['n'],'horse_name':x['name'],'running_style':x.get('running_style'),'latest_same_class_finish':x.get('latest_same_class_finish')} for x in holes];a['partner_roles']=a['role_main_partners']+[{**x,'role':'HOLE'} for x in a['role_holes']];a['trio_tickets']=tickets;a['ticket_count']=len(tickets);a['ticket_shape']='ROLE_DIVERSIFIED_AXIS';a['ticket_conversion_policy']='full-field role scan -> 3 main partners -> scenario holes -> position-role compatibility; no target result/popularity/odds';rows.append({**r,'analysis':a,'full_field_role_candidates':horses})
  summary.append({'track':r['track'],'race_no':r['race_no'],'axis':a['axis'],'decision':a['pre_market_decision'],'main':[x['n'] for x in mains],'holes':[x['n'] for x in holes],'tickets':tickets})
 OUT.write_text(json.dumps({'version':'ORAL_GOLDEN_FAST_V5_ROLE_DIVERSIFIED','result_data_used':False,'odds_popularity_used':False,'summary':summary,'races':rows},ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
