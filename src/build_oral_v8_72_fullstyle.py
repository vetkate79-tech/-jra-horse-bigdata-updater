#!/usr/bin/env python3
from __future__ import annotations
import hashlib,itertools,json,re,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,'src')
from oral_operational_layer import analyze_race

V7=Path('docs/data/oral-v7-72-style-predictions-sealed.json')
CACHE=Path('docs/data/pretarget-corner-cache.json')
CARDS=Path('docs/data/race_cards.json')
OUT=Path('docs/data/oral-v8-72-fullstyle-predictions-sealed.json')
STATUS=Path('status/oral-v8-72-fullstyle-predictions-sealed.json')
MODEL='ORAL_V8_72_FULL_PRETARGET_STYLE'
STYLE_LABEL={'ESCAPE':'逃げ','FRONT':'先行','STALK':'好位差し','CLOSER':'差し','DEEP_CLOSER':'追込','UNKNOWN':'判定待ち'}

def parse(v):return [int(x) for x in re.findall(r'\d+',str(v or ''))]
def f(v,d=0.0):
    try:return float(v)
    except:return d

def style_from_samples(samples):
    ss=[]
    for x in samples:
        cp=parse(x.get('corner_positions'))
        if not cp:continue
        # result page does not always expose field size in cache; approximate ordinal tendency from absolute positions.
        first,last=cp[0],cp[-1]
        ss.append((first,last))
    if not ss:return {'running_style':'UNKNOWN','running_style_label':'判定待ち','style_sample_starts':0,'avg_first_corner':None,'avg_last_corner':None,'position_variance':None}
    n=len(ss);avgf=sum(x[0] for x in ss)/n;avgl=sum(x[1] for x in ss)/n;esc=sum(x[0]==1 for x in ss)/n
    mean=(avgf+avgl)/2
    if esc>=.5 or mean<=1.8:code='ESCAPE'
    elif mean<=4.0:code='FRONT'
    elif mean<=6.5:code='STALK'
    elif mean<=10.0:code='CLOSER'
    else:code='DEEP_CLOSER'
    vals=[(a+b)/2 for a,b in ss];m=sum(vals)/len(vals);var=sum((x-m)**2 for x in vals)/len(vals)
    return {'running_style':code,'running_style_label':STYLE_LABEL[code],'style_sample_starts':n,'avg_first_corner':round(avgf,2),'avg_last_corner':round(avgl,2),'position_variance':round(var,3)}

def combo(a,b,c):return '-'.join(map(str,sorted(map(int,[a,b,c]))))
def role_score(h):
    s=f(h.get('role_score'),f(h.get('score')))
    st=h.get('running_style')
    # small role-only adjustment; never changes base ability score.
    if st in ('ESCAPE','FRONT'):s+=2.5
    elif st=='DEEP_CLOSER':s+=1.0
    if int(h.get('style_sample_starts') or 0)>=3:s+=1.0
    if f(h.get('position_variance'),99)<=2.5:s+=1.0
    return s

def diversified_main(cands,axis_no):
    xs=[dict(x) for x in cands if str(x.get('horse_no'))!=str(axis_no)]
    for x in xs:x['_r']=role_score(x)
    xs.sort(key=lambda x:(-x['_r'],int(x.get('horse_no') or 999)))
    out=[];used_styles=Counter()
    # first pass: role diversity
    for x in xs:
        st=x.get('running_style') or 'UNKNOWN'
        if st!='UNKNOWN' and used_styles[st]>=1 and len(out)<2:continue
        out.append(x);used_styles[st]+=1
        if len(out)>=3:break
    for x in xs:
        if len(out)>=3:break
        if x not in out:out.append(x)
    return out[:3]

def holes(cands,axis_no,main):
    used={str(axis_no),*[str(x.get('horse_no')) for x in main]}
    xs=[dict(x) for x in cands if str(x.get('horse_no')) not in used]
    for x in xs:
        sc=role_score(x)
        if x.get('running_style') in ('ESCAPE','DEEP_CLOSER'):sc+=2.0
        x['_h']=sc
    xs.sort(key=lambda x:(-x['_h'],int(x.get('horse_no') or 999)))
    return xs[:4]

def tickets(axis,main,holes):
    a=str(axis);out=[]
    for x,y in itertools.combinations(main,2):out.append(combo(a,x['horse_no'],y['horse_no']))
    # prioritize cross-style scenarios
    pairs=[]
    for m in main:
        for h in holes:
            diff=(m.get('running_style')!=h.get('running_style')) and m.get('running_style')!='UNKNOWN' and h.get('running_style')!='UNKNOWN'
            pairs.append((0 if diff else 1,-role_score(m)-role_score(h),m,h))
    pairs.sort(key=lambda z:(z[0],z[1],int(z[2]['horse_no']),int(z[3]['horse_no'])))
    for _,__,m,h in pairs:
        t=combo(a,m['horse_no'],h['horse_no'])
        if t not in out:out.append(t)
        if len(out)>=9:break
    return out[:9]

def main():
    v7=json.loads(V7.read_text());cache=json.loads(CACHE.read_text());cards=json.loads(CARDS.read_text())
    styles={hid:style_from_samples(xs) for hid,xs in cache.get('horses',{}).items()}
    cardmap={(r['date'],r['track'],int(r['race_no'])):r for r in cards.get('races',[])}
    rows=[];resolved=0;unknown=0
    for r in v7.get('races',[]):
        a=json.loads(json.dumps(r.get('analysis') or {},ensure_ascii=False))
        key=(r['date'],r['track'],int(r['race_no']));cr=cardmap.get(key,{})
        by_no={str(h.get('n')):h for h in cr.get('horses',[])}
        # candidate union from v7 main+holes+axis and card field fallback
        axis_no=str((a.get('axis') or {}).get('horse_no') or '')
        candidates=[]
        for item in (a.get('role_main_partners') or [])+(a.get('role_holes') or []):
            no=str(item.get('horse_no') or '');ch=by_no.get(no,{})
            hid=str(ch.get('horse_id') or '')
            st=styles.get(hid,{'running_style':'UNKNOWN','running_style_label':'判定待ち','style_sample_starts':0})
            x={**item,**st}
            # preserve V7 order strength as role_score baseline
            x['role_score']=100-len(candidates)*5
            candidates.append(x)
            if st.get('running_style')=='UNKNOWN':unknown+=1
            else:resolved+=1
        if a.get('pre_market_decision')!='PASS' and candidates:
            mainp=diversified_main(candidates,axis_no);hp=holes(candidates,axis_no,mainp);ts=tickets(axis_no,mainp,hp)
            a['role_main_partners']=[{k:x.get(k) for k in ('horse_no','horse_name','running_style','running_style_label','style_sample_starts')} for x in mainp]
            a['role_holes']=[{k:x.get(k) for k in ('horse_no','horse_name','running_style','running_style_label','style_sample_starts')} for x in hp]
            a['partner_roles']=a['role_main_partners']+a['role_holes'];a['trio_tickets']=ts;a['ticket_count']=len(ts);a['ticket_shape']='ROLE_DIVERSIFIED_AXIS_V8'
        a['model_version']=MODEL;a['running_style_replay_policy']='JRA official result URLs, target-date-exclusive corner history only';a['corner_cache_cutoff']=cache.get('cutoff_exclusive')
        rows.append({**{k:r.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'analysis':a})
    payload={'version':MODEL,'mode':'SEALED_PRE_RESULT_REPLAY','race_count':len(rows),'result_data_used':False,'odds_popularity_used':False,'post_target_running_style_used':False,'corner_cache_cutoff':cache.get('cutoff_exclusive'),'corner_cache_horses_resolved':cache.get('horse_with_corner_history'),'role_style_assignments_resolved':resolved,'role_style_assignments_unknown':unknown,'races':rows}
    canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();txt=json.dumps(payload,ensure_ascii=False,indent=2);OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({k:payload[k] for k in ('version','race_count','corner_cache_cutoff','corner_cache_horses_resolved','role_style_assignments_resolved','role_style_assignments_unknown','prediction_hash_sha256')},ensure_ascii=False,indent=2));print(json.dumps({'races':len(rows),'resolved':resolved,'unknown':unknown,'hash':payload['prediction_hash_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
