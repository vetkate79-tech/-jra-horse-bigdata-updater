#!/usr/bin/env python3
from __future__ import annotations
import itertools,json
from pathlib import Path
V4=Path('docs/data/oral-golden-fast-v4.json');FD=Path('status/oral-full-field-role-diagnostic-v5.json');ST=Path('status/oral-golden-running-style-diagnostic.json');OUT=Path('docs/data/oral-golden-fast-v6.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def f(v,d=0.0):
 try:return float(v)
 except:return d
def combo(a,b,c):return '-'.join(map(str,sorted(map(int,[a,b,c]))))
def mscore(h):
 s=f(h.get('secondary_role_score'))+.5*f(h.get('v4_score'))
 if int(h.get('exact_class_top3_count') or 0)>=2:s+=10
 if int(h.get('latest_exact_track_finish') or 99)<=5:s+=8
 if int(h.get('latest_finish') or 99)<=5:s+=4
 return s
def pick_main(hs,axis):
 elig=[]
 for h in hs:
  if h['n']==axis['n']:continue
  if int(h.get('latest_finish') or 99)<=7 or int(h.get('latest_exact_track_finish') or 99)<=5:
   x=dict(h);x['main_score']=round(mscore(x),3);elig.append(x)
 elig.sort(key=lambda x:(-x['main_score'],int(x['n'])))
 diff=[x for x in elig if x.get('running_style')!=axis.get('running_style')]
 out=diff[:3]
 for x in elig:
  if len(out)>=3:break
  if x['n'] not in {y['n'] for y in out}:out.append(x)
 return out
def pick_holes(hs,axis,main,recovery):
 used={axis['n'],*[x['n'] for x in main]};rest=[dict(x) for x in hs if x['n'] not in used]
 if recovery:
  cand=[x for x in rest if int(x.get('latest_same_class_finish') or 99) in (3,4)]
  cand.sort(key=lambda x:(int(x.get('latest_same_class_finish') or 99),-f(x.get('secondary_role_score')),int(x['n'])))
  if len(cand)<2:
   extra=[x for x in rest if int(x.get('latest_finish') or 99)<=4 and x['n'] not in {y['n'] for y in cand}]
   extra.sort(key=lambda x:(int(x.get('latest_finish') or 99),-f(x.get('secondary_role_score')),int(x['n'])));cand+=extra
  return cand[:2]
 rest.sort(key=lambda x:(-f(x.get('v4_score')),-f(x.get('secondary_role_score')),int(x['n'])))
 holes=rest[:3]
 if 'ESCAPE' not in {x.get('running_style') for x in main+holes}:
  esc=[x for x in rest if x.get('running_style')=='ESCAPE' and x['n'] not in {y['n'] for y in holes}]
  esc.sort(key=lambda x:(-f(x.get('v4_score')),-f(x.get('secondary_role_score')),int(x['n'])))
  if esc:holes.append(esc[0])
 return holes[:4]
def compatible(m,h,axis_style):
 ms=m.get('running_style');hs=h.get('running_style');latest=int(m.get('latest_same_class_finish') or m.get('latest_finish') or 99)
 if latest>7:return hs=='ESCAPE'
 if ms in ('FRONT','ESCAPE'):return hs!=axis_style
 if ms in ('CLOSER','DEEP_CLOSER'):return hs in ('CLOSER','STALK') and hs!=ms
 if ms=='STALK':return hs in ('FRONT','ESCAPE','DEEP_CLOSER')
 return ms!=hs
def tickets(axis,main,holes,recovery):
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
 v=json.loads(V4.read_text());fd=json.loads(FD.read_text());st=json.loads(ST.read_text());fm={key(r):r for r in fd['races']};sm={key(r):r for r in st['races']};rows=[];summary=[]
 for r in v['races']:
  styles={x['n']:x.get('running_style') for x in sm[key(r)]['horses']};hs=[]
  for x in fm[key(r)]['all_field_roles']:
   y=dict(x);y['running_style']=styles.get(y['n']);hs.append(y)
  axis=next(x for x in hs if x['n']==str(r['analysis']['axis']['horse_no']));recovery=bool(r['analysis'].get('recovery_axis'));main3=pick_main(hs,axis);holes=pick_holes(hs,axis,main3,recovery);ts=tickets(axis,main3,holes,recovery);a=dict(r['analysis']);a['role_main_partners']=[{'horse_no':x['n'],'horse_name':x['name'],'running_style':x.get('running_style')} for x in main3];a['role_holes']=[{'horse_no':x['n'],'horse_name':x['name'],'running_style':x.get('running_style')} for x in holes];a['partner_roles']=a['role_main_partners']+a['role_holes'];a['trio_tickets']=ts;a['ticket_count']=len(ts);a['ticket_shape']='ROLE_DIVERSIFIED_AXIS_V6';a['ticket_conversion_policy']='main promotion requires recent form or recent same-course evidence; full-field role diversity; no target result/popularity/odds';rows.append({**r,'analysis':a});summary.append({'track':r['track'],'race_no':r['race_no'],'axis':a['axis'],'decision':a['pre_market_decision'],'main':[x['n'] for x in main3],'holes':[x['n'] for x in holes],'tickets':ts})
 OUT.write_text(json.dumps({'version':'ORAL_GOLDEN_FAST_V6','result_data_used':False,'odds_popularity_used':False,'summary':summary,'races':rows},ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
