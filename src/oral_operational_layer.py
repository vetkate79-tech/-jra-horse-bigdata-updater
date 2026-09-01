#!/usr/bin/env python3
from __future__ import annotations
import itertools

MODEL_VERSION='ORAL_INTEGRATED_V1_SHADOW'

def _f(v,d=0.0):
    try:return float(v)
    except:return d

def _combo(xs):
    return '-'.join(map(str,sorted(map(int,xs))))

def _rank(race):
    return list(race.get('ranked_snapshot') or [])

def _axis_durability(q):
    if not q:return {'score':0,'status':'LOW','reasons':['軸候補データなし']}
    top=q[0]; second=q[1] if len(q)>1 else top
    gap=_f(top.get('score'))-_f(second.get('score'))
    unc=_f(top.get('uncertainty'),1)
    show=_f(top.get('show_rate_prior'),.3)
    cond=_f(top.get('condition_fit'),.3)
    recent=_f(top.get('recent_form'),.35)
    starts=_f(top.get('starts_before'))
    score=35*min(1,max(0,show))+20*min(1,max(0,cond))+15*min(1,max(0,recent))+20*min(1,max(0,gap/8))+10*(1-min(1,max(0,unc)))
    reasons=[]
    if gap>=4:reasons.append('能力評価で2位との差が大きい')
    elif gap<1.5:reasons.append('上位評価差が小さい')
    if unc<=.4:reasons.append('事前データの不確実性が低い')
    elif unc>=.8:reasons.append('事前データの不確実性が高い')
    if cond>=.45:reasons.append('条件適性が比較的高い')
    if starts<2:reasons.append('出走履歴が少なく耐久性は暫定')
    status='HIGH' if score>=64 and gap>=2 and unc<=.6 else ('MID' if score>=48 else 'LOW')
    return {'score':round(score,1),'status':status,'gap_to_second':round(gap,3),'uncertainty':unc,'reasons':reasons}

def _roles(q):
    out=[]
    for i,h in enumerate(q[1:7],start=2):
        rec=_f(h.get('recent_form'),.35); cond=_f(h.get('condition_fit'),.3); unc=_f(h.get('uncertainty'),1); show=_f(h.get('show_rate_prior'),.3)
        roles=[]
        if i<=3:roles.append('能力上位')
        if rec>=.55:roles.append('近走上昇')
        if cond>=max(.42,show+.05):roles.append('条件適性')
        if show>=.38 and unc<=.6:roles.append('安定型')
        if i>=4 and (cond>=.38 or rec>=.48):roles.append('3着侵入')
        style=h.get('running_style') or h.get('style')
        if style:roles.append(str(style))
        if not roles:roles=['順位補完']
        out.append({'horse_no':str(h.get('n')),'horse_name':h.get('name',''),'rank':i,'roles':roles,'uncertainty':unc})
    return out

def _intrusion(q,roles):
    rs={x['horse_no']:x for x in roles};out=[]
    for h in q[3:8]:
        n=str(h.get('n')); r=rs.get(n,{}); cond=_f(h.get('condition_fit'),.3); rec=_f(h.get('recent_form'),.35); unc=_f(h.get('uncertainty'),1)
        merit=(cond-.3)*2+(rec-.35)*1.4+(1-unc)*.25
        if '3着侵入' in r.get('roles',[]) or merit>=.18:
            out.append({'horse_no':n,'horse_name':h.get('name',''),'reason':'能力順位より条件/近走面の上振れ余地','intrusion_score':round(merit,3)})
    return out[:3]

def _scenarios(axis,roles,intrusion):
    same_side=[x for x in roles if any(k in x['roles'] for k in ('安定型','能力上位'))][:3]
    return [
        {'id':'BASE','label':'基本成立','covered_horses':[x['horse_no'] for x in same_side]},
        {'id':'AXIS_FAIL','label':'軸だけ飛ぶ','covered_horses':[x['horse_no'] for x in roles[:4]],'note':'相手内完結を最低1組監査'},
        {'id':'THIRD_INTRUSION','label':'3着低順位馬侵入','covered_horses':[x['horse_no'] for x in intrusion]},
        {'id':'STRUCTURE_FLIP','label':'想定展開反転','covered_horses':[x['horse_no'] for x in roles if '条件適性' in x['roles'] or '近走上昇' in x['roles']][:3]},
    ]

def _tickets(q,dur,roles,intrusion):
    ns=[str(x.get('n')) for x in q[:7] if str(x.get('n','')).isdigit()]
    if len(ns)<5:return 'PASS',[]
    axis=ns[0]; partners=[x['horse_no'] for x in roles[:5] if x['horse_no'] in ns]
    intr=[x['horse_no'] for x in intrusion if x['horse_no'] in ns]
    out=[]
    if dur['status']=='HIGH':
        # 1頭軸。上位相手を中心にしつつ侵入候補を同数入替。
        pool=list(dict.fromkeys(partners+intr))[:5]
        for a,b in itertools.combinations(pool,2):out.append(_combo([axis,a,b]))
        shape='AXIS'
        out=out[:9]
    elif dur['status']=='MID':
        core=ns[:2]; pool=list(dict.fromkeys(ns[2:6]+intr))[:4]
        for x in pool:out.append(_combo([core[0],core[1],x]))
        for a,b in itertools.combinations(pool,2):
            if len(out)>=9:break
            out.append(_combo([core[0],a,b]))
        # 軸だけ飛ぶ相手内完結を1本確保
        if len(pool)>=3:out.append(_combo(pool[:3]))
        shape='DUAL'
        out=list(dict.fromkeys(out))[:9]
    else:
        shape='GROUP'
        for c in itertools.combinations(ns[:5],3):out.append(_combo(c))
        # 3着侵入候補が6位以下なら上位5頭の最弱組合せと入替
        if intr:
            x=intr[0]
            candidate=_combo([ns[0],ns[1],x])
            if candidate not in out:out[-1]=candidate
        out=list(dict.fromkeys(out))[:10]
    return shape,out

def _classification(dur,q,tickets):
    if not q or not tickets:return 'PASS'
    avg_unc=sum(_f(x.get('uncertainty'),1) for x in q[:3])/max(1,min(3,len(q)))
    spread=_f(q[0].get('score'))-_f(q[min(4,len(q)-1)].get('score'))
    if dur['status']=='HIGH' and avg_unc<=.55:return 'A'
    if dur['status'] in ('HIGH','MID') and spread>=4:return 'B'
    if dur['status']=='MID' and avg_unc<=.75:return 'C'
    return 'PASS'

def _derived(axis,roles,dur,cls):
    a={'horse_no':axis.get('n'),'horse_name':axis.get('name','')}
    second=roles[0] if roles else None
    return {
      'PLACE':{'decision':'BUY_CANDIDATE' if dur['status']=='HIGH' else ('CAUTION' if dur['status']=='MID' else 'PASS'),'primary_horses':[a],'reason':'軸耐久性を3着以内残存へ読み替える'},
      'WIDE':{'decision':'BUY_CANDIDATE' if dur['status'] in ('HIGH','MID') and second else 'PASS','primary_horses':[a]+([{'horse_no':second['horse_no'],'horse_name':second['horse_name']}] if second else []),'reason':'軸と相手が同時に馬券内へ残る組合せを優先'},
      'QUINELLA':{'decision':'CAUTION' if cls in ('A','B') and second else 'PASS','primary_horses':[a]+([{'horse_no':second['horse_no'],'horse_name':second['horse_name']}] if second else []),'reason':'3着耐久性より1・2着到達力を要求'},
      'WIN':{'decision':'BUY_CANDIDATE' if dur['status']=='HIGH' and dur.get('gap_to_second',0)>=4 else 'PASS','primary_horses':[a],'reason':'安定性とは別に1着を取り切る評価差が必要'},
      'TRIFECTA':{'decision':'CAUTION' if cls=='A' and dur['status']=='HIGH' else 'PASS','primary_horses':[a],'reason':'三連複候補に加え着順再現性が必要'}
    }

def analyze_race(race):
    q=_rank(race);axis=q[0] if q else {}
    dur=_axis_durability(q); roles=_roles(q); intrusion=_intrusion(q,roles); scenarios=_scenarios(axis,roles,intrusion)
    shape,tickets=_tickets(q,dur,roles,intrusion); cls=_classification(dur,q,tickets)
    if cls=='PASS':tickets=[];shape='PASS'
    data_quality='LOW' if q and sum(_f(x.get('starts_before')) for x in q[:5])<5 else ('MID' if q and sum(_f(x.get('starts_before')) for x in q[:5])<12 else 'HIGH')
    return {
      'model_version':MODEL_VERSION,
      'axis':{'horse_no':str(axis.get('n','')),'horse_name':axis.get('name','')},
      'axis_durability':dur,
      'partner_roles':roles,
      'third_place_intrusion':intrusion,
      'failure_scenarios':scenarios,
      'ticket_shape':shape,
      'trio_tickets':tickets,
      'ticket_count':len(tickets),
      'classification':cls,
      'pre_market_decision':'BUY' if cls in ('A','B') else ('CAUTION' if cls=='C' else 'PASS'),
      'data_quality':data_quality,
      'derived_ticket_analysis':_derived(axis,roles,dur,cls),
      'market_isolation':'NO_ODDS_OR_POPULARITY_USED',
      'implementation_note':'Phase1 rule-based oral-operation shadow; richer running-style/pace fields are consumed when available.'
    }
