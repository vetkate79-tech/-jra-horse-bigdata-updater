#!/usr/bin/env python3
"""Reconstruct 2026-08-29/30 pre-race predictions with result leakage blocked.

Phase 1 reads only race cards + information available strictly before each target
race date. It writes a sealed prediction snapshot and hash before any 2026-08-29/30
result or payout file is opened. Phase 2 then scores the frozen snapshot.

Existing PRE_RACE_CONVERSATION_LOG records are preserved where available. All
other records are explicitly labelled BLIND_REPLAY_RECONSTRUCTION and are not
presented as historical chat predictions.
"""
from __future__ import annotations
import csv, hashlib, itertools, json, math, re, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables

ROOT=Path('.')
CARDS=Path('docs/data/race_cards.json')
ARCHIVE=Path('docs/data/replay-demo-2026-08-29-30.json')
PROFILE_2025=Path('data/horse_profiles_2025.csv')
RESULTS_2025=Path('data/race_results_html_2025.csv')
RESULTS_2026=Path('data/race_results_html_2026.csv')
PAYOUTS_2026=Path('data/race_payouts_2026.csv')
SEALED=Path('docs/data/replay-2026-08-29-30-sealed.json')
FULL=Path('docs/data/replay-2026-08-29-30-full.json')
STATUS=Path('status/replay-2026-08-29-30-evaluation.json')
TARGET_DATES={'2026-08-29','2026-08-30'}
MODEL='BLIND_RULE_REPLAY_V0.1'


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def fnum(v,default=None):
    try:return float(str(v).replace(',',''))
    except:return default

def inum(v,default=None):
    try:return int(re.sub(r'[^0-9]','',str(v)))
    except:return default

def norm_date(v):
    s=str(v or '').strip().replace('年','-').replace('月','-').replace('日','').replace('/','-').replace('.','-')
    m=re.search(r'(20\d{2})-(\d{1,2})-(\d{1,2})',s)
    return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''

def parse_surface_distance(vals):
    text=' '.join(str(x) for x in vals)
    m=re.search(r'(芝|ダート|ダ)\s*([0-9]{3,4})',text)
    if not m:return '',None
    return ('ダート' if m.group(1) in ('ダ','ダート') else '芝'),int(m.group(2))

def find_val(vals,needles):
    for c,v in vals.items():
        if any(n in str(c) for n in needles) and str(v).strip() not in ('','nan','None'):
            return str(v).strip()
    return ''

def profile_history(hid,target_date):
    """Read current JRA profile but expose only rows dated strictly before target."""
    try: html=request_profile(hid)
    except Exception:return [],0
    rows=[];excluded=0
    for table in normalized_tables(html):
        if not any(('レース名' in c or '競走名' in c) for c in table.columns):continue
        for _,row in table.iterrows():
            vals={str(c):str(v).strip() for c,v in row.items()}
            date=norm_date(find_val(vals,['年月日','日付']))
            if not date:continue
            if date>=target_date:
                excluded+=1;continue
            race_name=find_val(vals,['レース名','競走名'])
            finish=inum(find_val(vals,['着順']))
            if finish is None:continue
            surface,distance=parse_surface_distance(vals.values())
            last3f=fnum(find_val(vals,['上り3F','上がり3F','上り']))
            corners=find_val(vals,['通過','コーナー'])
            rows.append({'date':date,'race_name':race_name,'finish':finish,'surface':surface,'distance_m':distance,'last3f':last3f,'corners':corners})
    rows.sort(key=lambda x:x['date'],reverse=True)
    return rows,excluded

def stats_2025():
    by={}
    for r in read_csv(PROFILE_2025):by[r.get('horse_id','')]=r
    return by

def people_stats_2025():
    jockey=defaultdict(lambda:[0,0]);trainer=defaultdict(lambda:[0,0])
    for r in read_csv(RESULTS_2025):
        fin=inum(r.get('finish_position'))
        if fin is None:continue
        for key,bucket in ((r.get('jockey',''),jockey),(r.get('trainer',''),trainer)):
            if not key:continue
            bucket[key][0]+=1;bucket[key][1]+=int(fin<=3)
    def rate(bucket,key):
        n,t=bucket.get(key,[0,0]);return (t+2)/(n+8) if n else 0.25
    return lambda key:rate(jockey,key),lambda key:rate(trainer,key)

def blended_features(horse,race,hist,base,j_rate,t_rate):
    starts25=int(fnum(base.get('starts'),0) or 0);top325=int(fnum(base.get('top3'),0) or 0)
    starts26=len(hist);top326=sum(1 for x in hist if x['finish']<=3)
    starts=starts25+starts26; top3=top325+top326
    show=(top3+1.5)/(starts+5) if starts else 0.30
    recent=hist[:5]
    if recent:
        ws=[5,4,3,2,1][:len(recent)]
        quality=sum(w*(1/max(1,min(18,x['finish']))) for w,x in zip(ws,recent))/sum(ws)
        recency=min(1.0,quality*3.2)
    else:
        avg=fnum(base.get('avg_finish'))
        recency=max(0.0,min(1.0,(12-(avg or 12))/11)) if avg else 0.35
    match=[x for x in hist if x['surface']==race.get('surface') and x['distance_m'] and abs(x['distance_m']-int(race.get('distance_m') or 0))<=300]
    cond=((sum(1 for x in match if x['finish']<=3)+1)/(len(match)+3)) if match else show
    l3=[x['last3f'] for x in recent if x.get('last3f')]
    last3f=0.5 if not l3 else max(0.0,min(1.0,(40-min(l3))/8))
    jr=j_rate(horse.get('jockey','')); tr=t_rate(horse.get('trainer',''))
    uncertainty=1.0-min(1.0,starts/5)
    score=45*show+25*recency+10*cond+8*jr+7*tr+5*last3f-8*uncertainty
    return {'score':round(score,3),'starts_before':starts,'show_rate_prior':round(show,4),'recent_form':round(recency,4),'condition_fit':round(cond,4),'jockey_prior':round(jr,4),'trainer_prior':round(tr,4),'uncertainty':round(uncertainty,4)}

def seven_tickets(ranked):
    nums=[str(x['n']) for x in ranked[:6]]
    if len(nums)<3:return []
    a=nums[0];patterns=[(1,2),(1,3),(1,4),(2,3),(2,4),(3,4),(1,5)]
    out=[]
    for i,j in patterns:
        if i<len(nums) and j<len(nums):out.append('-'.join(map(str,sorted(map(int,[a,nums[i],nums[j]])))))
    return list(dict.fromkeys(out))

def formation_tickets(rec):
    axis_no=str(rec.get('axis','')).split()[0]
    p=[str(x).split()[0] for x in rec.get('partners',[])];h=[str(x).split()[0] for x in rec.get('holes',[])]
    if not axis_no.isdigit():return []
    second=[x for x in p if x.isdigit()];third=[x for x in p+h if x.isdigit()]
    combos=set()
    for b in second:
        for c in third:
            if len({axis_no,b,c})<3:continue
            combos.add('-'.join(map(str,sorted(map(int,[axis_no,b,c])))))
    return sorted(combos,key=lambda s:tuple(map(int,s.split('-'))))

def archived_map():
    doc=json.loads(ARCHIVE.read_text(encoding='utf-8'))
    return {(r.get('date'),r.get('track'),int(r.get('race_no') or 0)):r for r in doc.get('races',[]) if r.get('date') in TARGET_DATES}

def build_predictions():
    cards=json.loads(CARDS.read_text(encoding='utf-8'))
    base25=stats_2025();j_rate,t_rate=people_stats_2025();arch=archived_map()
    profile_cache={};excluded_total=0;out=[]
    races=[r for r in cards.get('races',[]) if r.get('date') in TARGET_DATES]
    races.sort(key=lambda r:(r['date'],r['track'],int(r['race_no'])))
    for idx,race in enumerate(races,1):
        ranked=[]
        for h in race.get('horses',[]):
            key=(h.get('horse_id',''),race['date'])
            if key not in profile_cache:profile_cache[key]=profile_history(h.get('horse_id',''),race['date'])
            hist,excluded=profile_cache[key];excluded_total+=excluded
            feat=blended_features(h,race,hist,base25.get(h.get('horse_id',''),{}),j_rate,t_rate)
            ranked.append({'n':str(h.get('n')),'name':h.get('name',''),'horse_id':h.get('horse_id',''),**feat})
        ranked.sort(key=lambda x:(-x['score'],int(x['n'])))
        k=(race['date'],race['track'],int(race['race_no']))
        actual=arch.get(k)
        if actual:
            tickets=formation_tickets(actual)
            pred={**{x:race.get(x) for x in ('race_id','date','track','race_no','race_name','surface','distance_m')},
                  'prediction_source':actual.get('prediction_source','PRE_RACE_CONVERSATION_LOG'),'type_label':actual.get('type_label','事前予想'),
                  'decision':actual.get('decision','BUY'),'axis':actual.get('axis'),'partners':actual.get('partners',[]),'holes':actual.get('holes',[]),
                  'formation':actual.get('formation'),'ticket_count':len(tickets) or actual.get('ticket_count',0),'stake':actual.get('stake',100*(len(tickets) or actual.get('ticket_count',0))),
                  'tickets':tickets,'model_version':'ARCHIVED_PRE_RACE','ranked_snapshot':ranked[:10]}
        else:
            top=ranked[0] if ranked else None;second=ranked[1] if len(ranked)>1 else None
            all_no_history=bool(ranked) and all(x['starts_before']==0 for x in ranked)
            gap=(top['score']-second['score']) if top and second else 0
            avg_starts=sum(x['starts_before'] for x in ranked[:5])/max(1,min(5,len(ranked)))
            if all_no_history:decision='PASS';reason='全頭で事前実走データ不足'
            elif avg_starts<1.5:decision='PASS';reason='上位候補の事前データ不足'
            elif gap>=7:decision='A';reason='上位1頭の評価差が大きい'
            elif gap>=3.5:decision='B';reason='中心候補は明確だが固定し過ぎない'
            elif gap>=1.5:decision='C';reason='上位差が小さく展開依存度が高い'
            else:decision='PASS';reason='軸候補の評価差が小さい'
            tickets=[] if decision=='PASS' else seven_tickets(ranked)
            axis=f"{top['n']} {top['name']}" if top else '判定不能'
            partners=[f"{x['n']} {x['name']}" for x in ranked[1:4]]
            holes=[f"{x['n']} {x['name']}" for x in ranked[4:6]]
            pred={**{x:race.get(x) for x in ('race_id','date','track','race_no','race_name','surface','distance_m')},
                  'prediction_source':'BLIND_REPLAY_RECONSTRUCTION','type_label':'結果遮断再現','decision':decision,'axis':axis,'partners':partners,'holes':holes,
                  'pre_note':f'{reason}。人気・オッズ・当該レース結果は予想生成に不使用。','formation':('PASS' if not tickets else '三連複 1頭軸・再現7点'),
                  'ticket_count':len(tickets),'stake':100*len(tickets),'tickets':tickets,'model_version':MODEL,'ranked_snapshot':ranked[:10]}
        out.append(pred)
        if idx%12==0:print(f'prediction phase {idx}/{len(races)}',flush=True)
    payload={'mode':'BLIND_PRE_RACE_RECONSTRUCTION','dates':sorted(TARGET_DATES),'race_count':len(out),'model_version':MODEL,
      'leakage_policy':'No 2026-08-29/30 result or payout file is opened before this snapshot is written. Current JRA horse profiles are filtered to rows strictly earlier than each target race date.',
      'historical_prediction_policy':'Existing pre-race conversation records are preserved; all other races are labelled BLIND_REPLAY_RECONSTRUCTION.',
      'excluded_profile_rows_at_or_after_target':excluded_total,'races':out}
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
    payload['prediction_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest()
    SEALED.parent.mkdir(parents=True,exist_ok=True);SEALED.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    return payload

def evaluate(sealed):
    # Result files are intentionally opened only after SEALED exists.
    if not SEALED.exists():raise RuntimeError('sealed snapshot missing')
    result_rows=[r for r in read_csv(RESULTS_2026) if r.get('race_date') in TARGET_DATES]
    payout_rows=[r for r in read_csv(PAYOUTS_2026) if r.get('race_date') in TARGET_DATES and r.get('bet_type') in ('3連複','三連複')]
    finish=defaultdict(list)
    for r in result_rows:
        p=inum(r.get('finish_position'))
        if p and p<=3:finish[r.get('race_id')].append((p,str(r.get('horse_no')),r.get('horse_name','')))
    payout={r.get('race_id'):r for r in payout_rows}
    evaluated=[]
    totals={'races':0,'bets':0,'passes':0,'hits':0,'stake':0,'return':0,'axis_survived':0,'candidate_top3_complete':0,'ticket_conversion_failures':0,'archived_pre_race':0,'blind_reconstructed':0}
    for p in sealed['races']:
        q=dict(p);rid=p.get('race_id');top=sorted(finish.get(rid,[]));res=[f'{n} {name}' for _,n,name in top]
        pay=payout.get(rid,{});win=pay.get('winning_selection','');win_norm='-'.join(map(str,sorted(map(int,re.findall(r'\d+',win))))) if win else ''
        tickets=set(p.get('tickets') or []);is_pass=p.get('decision')=='PASS' or not tickets;hit=(win_norm in tickets) if not is_pass else False
        axis_no=str(p.get('axis','')).split()[0];candidate_nos={str(x).split()[0] for x in [p.get('axis',''),*(p.get('partners') or []),*(p.get('holes') or [])]}
        actual_nos={n for _,n,_ in top};axis_survived=axis_no in actual_nos;captured=len(actual_nos & candidate_nos)
        conversion=(captured==3 and not hit and not is_pass)
        ret=int(fnum(pay.get('payout_per_100_yen'),0) or 0) if hit else 0
        q.update({'result_top3':res,'trio_result':win_norm,'trio_payout':int(fnum(pay.get('payout_per_100_yen'),0) or 0),'hit':hit,'return_amount':ret,
                  'axis_survived':axis_survived,'candidate_top3_captured':captured,'ticket_conversion_failure':conversion})
        if is_pass:q['review']='PASS。結果は評価用にのみ開封し、事前順位・候補・買い目は変更していない。'
        elif hit:q['review']='的中。封印済み買い目に実三連複が含まれた。'
        elif conversion:q['review']='候補3頭は全て拾えていたが、買い目変換で組み合わせを落とした。'
        elif axis_survived:q['review']=f'軸は馬券内。候補捕捉は3頭中{captured}頭で、相手側の取りこぼし。'
        else:q['review']=f'軸が馬券外。候補捕捉は3頭中{captured}頭。軸選定またはレース構造判断の失敗。'
        evaluated.append(q)
        totals['races']+=1;totals['archived_pre_race']+=int(str(p.get('prediction_source','')).startswith('PRE_RACE'));totals['blind_reconstructed']+=int(p.get('prediction_source')=='BLIND_REPLAY_RECONSTRUCTION')
        if is_pass:totals['passes']+=1
        else:
            totals['bets']+=1;totals['stake']+=int(p.get('stake') or 0);totals['hits']+=int(hit);totals['return']+=ret
        totals['axis_survived']+=int(axis_survived);totals['candidate_top3_complete']+=int(captured==3);totals['ticket_conversion_failures']+=int(conversion)
    totals['hit_rate_pct']=round(100*totals['hits']/totals['bets'],2) if totals['bets'] else 0
    totals['roi_pct']=round(100*totals['return']/totals['stake'],2) if totals['stake'] else 0
    totals['axis_survival_pct']=round(100*totals['axis_survived']/totals['races'],2) if totals['races'] else 0
    totals['candidate_top3_complete_pct']=round(100*totals['candidate_top3_complete']/totals['races'],2) if totals['races'] else 0
    doc={k:v for k,v in sealed.items() if k!='races'};doc['mode']='SEALED_THEN_SCORED';doc['evaluation_summary']=totals;doc['races']=evaluated
    FULL.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps({'prediction_hash_sha256':sealed.get('prediction_hash_sha256'),'summary':totals},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(totals,ensure_ascii=False,indent=2))


def main():
    sealed=build_predictions()
    if sealed.get('race_count')!=72:raise SystemExit(f"expected 72 races, got {sealed.get('race_count')}")
    evaluate(sealed)

if __name__=='__main__':main()
