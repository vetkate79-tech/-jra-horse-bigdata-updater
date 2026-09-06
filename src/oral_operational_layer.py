#!/usr/bin/env python3
from __future__ import annotations
import itertools

MODEL_VERSION='ORAL_INTEGRATED_V1_3_ROLE_SPLIT'

def _f(v,d=0.0):
    try:return float(v)
    except:return d

def _combo(xs):
    return '-'.join(map(str,sorted(map(int,xs))))

def _rank(race):
    return list(race.get('ranked_snapshot') or [])

def _data_quality(q):
    if not q:return 'LOW'
    starts=sum(_f(x.get('starts_before')) for x in q[:5])
    resolved=sum(1 for x in q[:5] if _f(x.get('uncertainty'),1)<=.70)
    if starts>=15 and resolved>=4:return 'HIGH'
    if starts>=8 and resolved>=3:return 'MID'
    return 'LOW'

def _axis_durability(q):
    if not q:return {'score':0,'status':'LOW','reasons':['軸候補データなし']}
    top=q[0]; second=q[1] if len(q)>1 else top
    gap=_f(top.get('score'))-_f(second.get('score'))
    unc=_f(top.get('uncertainty'),1)
    show=_f(top.get('show_rate_prior'),.3)
    cond=_f(top.get('condition_fit'),.3)
    recent=_f(top.get('recent_form'),.35)
    starts=_f(top.get('starts_before'))
    score=(
        30*min(1,max(0,show))+
        22*min(1,max(0,cond))+
        18*min(1,max(0,recent))+
        10*min(1,max(0,gap/8))+
        12*(1-min(1,max(0,unc)))+
        8*min(1,max(0,starts/5))
    )
    reasons=[]
    if gap>=4:reasons.append('能力評価で2位との差が大きい')
    elif gap<1.5:reasons.append('上位評価差が小さい')
    if unc<=.4:reasons.append('事前データの不確実性が低い')
    elif unc>=.8:reasons.append('事前データの不確実性が高い')
    if cond>=.45:reasons.append('条件適性が比較的高い')
    if recent>=.5:reasons.append('近走再現性が比較的高い')
    if starts<2:reasons.append('出走履歴が少なく耐久性は暫定')
    high=(score>=62 and gap>=1.5 and unc<=.55 and starts>=3 and show>=.32 and (cond>=.38 or recent>=.45))
    mid=(score>=49 and unc<=.70 and starts>=2 and show>=.27 and (cond>=.34 or recent>=.40))
    status='HIGH' if high else ('MID' if mid else 'LOW')
    return {'score':round(score,1),'status':status,'gap_to_second':round(gap,3),'uncertainty':unc,'starts_before':starts,'reasons':reasons}

def _roles(q):
    out=[]
    for i,h in enumerate(q[1:9],start=2):
        rec=_f(h.get('recent_form'),.35); cond=_f(h.get('condition_fit'),.3); unc=_f(h.get('uncertainty'),1); show=_f(h.get('show_rate_prior'),.3)
        roles=[]
        if i<=3:roles.append('能力上位')
        if rec>=.55:roles.append('近走上昇')
        if cond>=max(.42,show+.05):roles.append('条件適性')
        if show>=.38 and unc<=.6:roles.append('安定型')
        if i>=5 and (cond>=.38 or rec>=.48 or (show>=.34 and unc<=.65)):roles.append('3着侵入')
        style=h.get('running_style') or h.get('style')
        if style:roles.append(str(style))
        if not roles:roles=['順位補完']
        out.append({'horse_no':str(h.get('n')),'horse_name':h.get('name',''),'rank':i,'roles':roles,'uncertainty':unc,'running_style':style or 'UNKNOWN'})
    return out

def _axis_win_flow(q):
    if not q:return {'axis_style':'UNKNOWN','front_count':0,'flow':'標準','favored_styles':[],'reason':'脚質データ不足'}
    axis_style=str(q[0].get('running_style') or q[0].get('style') or 'UNKNOWN')
    top=q[:8]
    styles=[str(x.get('running_style') or x.get('style') or 'UNKNOWN') for x in top]
    front=sum(s in ('ESCAPE','FRONT') for s in styles)
    if axis_style in ('ESCAPE','FRONT'):
        if front<=2:return {'axis_style':axis_style,'front_count':front,'flow':'前残り','favored_styles':['FRONT','STALK'],'reason':'軸が前で勝ち切るなら、前受け・好位の残存を重視'}
        return {'axis_style':axis_style,'front_count':front,'flow':'前競合を軸が耐える','favored_styles':['CLOSER','STALK'],'reason':'前が多い中で軸が勝つなら、後方から差す馬と好位耐久馬が連動しやすい'}
    if axis_style=='STALK':
        if front>=3:return {'axis_style':axis_style,'front_count':front,'flow':'先行勢を好位軸が差す','favored_styles':['CLOSER','STALK'],'reason':'前が流れて好位の軸が抜ける展開では、差し・好位の連動を重視'}
        return {'axis_style':axis_style,'front_count':front,'flow':'好位前残り','favored_styles':['FRONT','STALK'],'reason':'前が少なく好位の軸が勝つなら、前受け組の残存を重視'}
    if axis_style in ('CLOSER','DEEP_CLOSER'):
        return {'axis_style':axis_style,'front_count':front,'flow':'差し決着','favored_styles':['CLOSER','DEEP_CLOSER','STALK'],'reason':'差し・追込の軸が勝つ展開では、同じ流れを使える差し勢を重視'}
    return {'axis_style':axis_style,'front_count':front,'flow':'標準','favored_styles':['STALK','CLOSER','FRONT'],'reason':'脚質確度が低いため条件・近走を優先'}

def _intrusion(q,roles):
    rs={x['horse_no']:x for x in roles};out=[];flow=_axis_win_flow(q)
    favored=set(flow['favored_styles'])
    # 能力順位そのものではなく、軸勝利シナリオへの適合度を独立加点する。
    for rank,h in enumerate(q[3:12],start=4):
        n=str(h.get('n')); r=rs.get(n,{}); cond=_f(h.get('condition_fit'),.3); rec=_f(h.get('recent_form'),.35); unc=_f(h.get('uncertainty'),1); show=_f(h.get('show_rate_prior'),.3); starts=_f(h.get('starts_before'))
        style=str(h.get('running_style') or h.get('style') or 'UNKNOWN')
        scenario_fit=.0
        if style in favored:scenario_fit+=.24
        if style!='UNKNOWN' and style!=flow['axis_style']:scenario_fit+=.05
        if flow['flow']=='差し決着' and style in ('CLOSER','DEEP_CLOSER'):scenario_fit+=.08
        if flow['flow'] in ('前残り','好位前残り') and style in ('FRONT','STALK'):scenario_fit+=.08
        if cond>=.42:scenario_fit+=.08
        if rec>=.50:scenario_fit+=.07
        if unc<=.55:scenario_fit+=.05
        base=(cond-.3)*1.15+(rec-.35)*.95+(show-.3)*.45+(1-unc)*.18+min(starts,5)*.010
        merit=base+scenario_fit
        if merit>=.22 or ('3着侵入' in r.get('roles',[]) and scenario_fit>=.20):
            reason=f"{flow['reason']}。{style if style!='UNKNOWN' else '脚質不明'}・条件適性・近走から展開穴として評価"
            out.append({'horse_no':n,'horse_name':h.get('name',''),'rank':rank,'running_style':style,'axis_win_flow':flow['flow'],'scenario_fit':round(scenario_fit,3),'reason':reason,'intrusion_score':round(merit,3)})
    out.sort(key=lambda x:(-x['intrusion_score'],-x.get('scenario_fit',0)))
    return out[:3]

def _scenarios(axis,roles,intrusion):
    same_side=[x for x in roles if any(k in x['roles'] for k in ('安定型','能力上位'))][:3]
    return [
        {'id':'BASE','label':'基本成立','covered_horses':[x['horse_no'] for x in same_side]},
        {'id':'AXIS_FAIL','label':'軸だけ飛ぶ','covered_horses':[x['horse_no'] for x in roles[:5]],'note':'MIDは買い目の約半数を軸なしで監査'},
        {'id':'THIRD_INTRUSION','label':'3着低順位馬侵入','covered_horses':[x['horse_no'] for x in intrusion]},
        {'id':'STRUCTURE_FLIP','label':'想定展開反転','covered_horses':[x['horse_no'] for x in roles if '条件適性' in x['roles'] or '近走上昇' in x['roles']][:3]},
    ]

def _diverse_partner_pool(roles,intrusion,limit=5):
    intr={x['horse_no'] for x in intrusion}
    chosen=[]; seen_styles=set(); seen_role_families=set()
    def family(x):
        for k in ('安定型','条件適性','近走上昇','3着侵入','能力上位'):
            if k in x.get('roles',[]):return k
        return '順位補完'
    for x in roles:
        style=x.get('running_style') or 'UNKNOWN'; fam=family(x)
        if style!='UNKNOWN' and style in seen_styles and fam in seen_role_families and x['horse_no'] not in intr:continue
        chosen.append(x['horse_no']); seen_styles.add(style); seen_role_families.add(fam)
        if len(chosen)>=limit:return chosen
    for x in roles:
        if x['horse_no'] not in chosen:chosen.append(x['horse_no'])
        if len(chosen)>=limit:break
    for x in intrusion:
        if x['horse_no'] not in chosen:
            if len(chosen)>=limit:chosen[-1]=x['horse_no']
            else:chosen.append(x['horse_no'])
    return list(dict.fromkeys(chosen))[:limit]

def _partner_tiers(q,roles,intrusion):
    ns=[str(x.get('n')) for x in q[:10] if str(x.get('n','')).isdigit()]
    axis=ns[0] if ns else ''
    role_by_no={str(x.get('horse_no')):x for x in roles}
    # 2列目は「2着まで来る現実性」を能力順に優先する。
    second=[]
    for h in q[1:7]:
        n=str(h.get('n') or '')
        if not n or n==axis:continue
        r=role_by_no.get(n,{})
        if len(second)<3:
            second.append(n)
    # 3列目は2列目を包含し、独立した3着侵入候補を優先して追加する。
    third=list(second)
    for x in intrusion:
        n=str(x.get('horse_no') or '')
        if n and n in ns and n!=axis and n not in third:
            third.append(n)
    # 穴候補が少ない時だけ能力順の次点を補完する。
    for h in q[1:9]:
        n=str(h.get('n') or '')
        if n and n!=axis and n not in third:
            third.append(n)
        if len(third)>=6:break
    return second[:3],third[:6]

def _tickets(q,dur,roles,intrusion):
    ns=[str(x.get('n')) for x in q[:10] if str(x.get('n','')).isdigit()]
    if len(ns)<5:return 'PASS',[],{'first':[],'second':[],'third':[]}
    axis=ns[0]
    second,third=_partner_tiers(q,roles,intrusion)
    intr=[x['horse_no'] for x in intrusion if x['horse_no'] in ns]
    formation={'first':[axis],'second':second,'third':third}
    out=[]
    if dur['status']=='HIGH':
        # 本線同士を先に確保し、その後に3着侵入候補との組合せを優先する。
        for a,b in itertools.combinations(second,2):
            out.append(_combo([axis,a,b]))
        for h in intr:
            if h not in third:continue
            for a in second:
                if a!=h:out.append(_combo([axis,a,h]))
        for a in second:
            for b in third:
                if a!=b:out.append(_combo([axis,a,b]))
        shape='AXIS';out=list(dict.fromkeys(out))[:9]
    elif dur['status']=='MID':
        # MIDは固定軸として扱わない。約半数を1位軸あり、約半数を1位軸なしにする。
        alternatives=list(dict.fromkeys(second+third+intr+ns[1:7]))
        alternatives=[x for x in alternatives if x!=axis and x in ns][:6]
        anchored=[]
        for a in second:
            for b in third:
                if a==b:continue
                anchored.append(_combo([axis,a,b]))
                if len(dict.fromkeys(anchored))>=4:break
            if len(dict.fromkeys(anchored))>=4:break
        axis_free=[]
        triples=list(itertools.combinations(alternatives,3))
        triples.sort(key=lambda c:(
            0 if any(x in intr for x in c) else 1,
            sum(alternatives.index(x) for x in c)
        ))
        for cc in triples:
            axis_free.append(_combo(cc))
            if len(axis_free)>=4:break
        out=list(dict.fromkeys(anchored+axis_free))[:8]
        shape='HEDGED'
    else:
        shape='GROUP'
        pool=list(dict.fromkeys([axis]+second+third+intr))[:6]
        for cc in itertools.combinations(pool,3):out.append(_combo(cc))
        out=list(dict.fromkeys(out))[:10]
    return shape,out,formation

def _classification(dur,q,tickets,data_quality):
    if not q or not tickets or data_quality=='LOW':return 'PASS'
    avg_unc=sum(_f(x.get('uncertainty'),1) for x in q[:3])/max(1,min(3,len(q)))
    spread=_f(q[0].get('score'))-_f(q[min(4,len(q)-1)].get('score'))
    if dur['status']=='HIGH' and data_quality=='HIGH' and avg_unc<=.50:return 'A'
    if dur['status']=='HIGH' and avg_unc<=.60 and spread>=2.5:return 'B'
    # MIDは軸固定の信頼度が不足しているためBUYへ昇格させない。
    if dur['status']=='MID' and avg_unc<=.65 and spread>=2:return 'C'
    return 'PASS'

def _derived(axis,roles,dur,cls):
    a={'horse_no':axis.get('n'),'horse_name':axis.get('name','')}
    second=roles[0] if roles else None
    return {
      'PLACE':{'decision':'BUY_CANDIDATE' if dur['status']=='HIGH' and cls!='PASS' else ('CAUTION' if dur['status']=='MID' and cls!='PASS' else 'PASS'),'primary_horses':[a],'reason':'軸耐久性を3着以内残存へ読み替える'},
      'WIDE':{'decision':'BUY_CANDIDATE' if cls in ('A','B') and second else ('CAUTION' if cls=='C' and second else 'PASS'),'primary_horses':[a]+([{'horse_no':second['horse_no'],'horse_name':second['horse_name']}] if second else []),'reason':'軸と相手が同時に馬券内へ残る組合せを優先'},
      'QUINELLA':{'decision':'CAUTION' if cls in ('A','B') and second else 'PASS','primary_horses':[a]+([{'horse_no':second['horse_no'],'horse_name':second['horse_name']}] if second else []),'reason':'3着耐久性より1・2着到達力を要求'},
      'WIN':{'decision':'BUY_CANDIDATE' if cls=='A' and dur.get('gap_to_second',0)>=4 else 'PASS','primary_horses':[a],'reason':'安定性とは別に1着を取り切る評価差が必要'},
      'TRIFECTA':{'decision':'CAUTION' if cls=='A' and dur['status']=='HIGH' else 'PASS','primary_horses':[a],'reason':'三連複候補に加え着順再現性が必要'}
    }

def analyze_race(race):
    q=_rank(race);axis=q[0] if q else {}
    data_quality=_data_quality(q)
    dur=_axis_durability(q); roles=_roles(q); intrusion=_intrusion(q,roles); scenarios=_scenarios(axis,roles,intrusion); axis_win_flow=_axis_win_flow(q)
    shape,tickets,formation_columns=_tickets(q,dur,roles,intrusion); cls=_classification(dur,q,tickets,data_quality)
    if cls=='PASS':tickets=[];shape='PASS'
    return {
      'model_version':MODEL_VERSION,
      'axis':{'horse_no':str(axis.get('n','')),'horse_name':axis.get('name','')},
      'axis_durability':dur,
      'partner_roles':roles,
      'third_place_intrusion':intrusion,
      'axis_win_flow':axis_win_flow,
      'failure_scenarios':scenarios,
      'ticket_shape':shape,
      'formation_columns':formation_columns,
      'trio_tickets':tickets,
      'ticket_count':len(tickets),
      'classification':cls,
      'pre_market_decision':'BUY' if cls in ('A','B') else ('CAUTION' if cls=='C' else 'PASS'),
      'data_quality':data_quality,
      'derived_ticket_analysis':_derived(axis,roles,dur,cls),
      'market_isolation':'NO_ODDS_OR_POPULARITY_USED',
      'implementation_note':'V1.3 role split: second-line finish-strength partners are separated from third-line intrusion candidates; third line contains independent scenario/condition hole coverage without using odds or popularity.'
    }
