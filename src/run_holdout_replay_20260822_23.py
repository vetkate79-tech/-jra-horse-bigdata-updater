#!/usr/bin/env python3
"""Strict holdout replay for all JRA races on 2026-08-22/23.

Stages are intentionally separate:
  prepare: read historical result export only to extract race-card fields, then exit.
  predict: read sanitized cards + pre-target horse history only, run current V1.2,
           and write a SHA256 sealed prediction file. Target results/payouts are not opened.
  score: require the sealed file, then open target results/payouts and evaluate.

No model parameter is changed from holdout outcomes.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, 'src')
from collect_active_elite_horses import request_profile, normalized_tables
from oral_operational_layer import analyze_race, MODEL_VERSION

TARGET={'2026-08-22','2026-08-23'}
RAW=Path('data/race_results_html_2026_holdout_0822_23.csv')
PAYOUT=Path('data/race_payouts_2026_holdout_0822_23.csv')
CARDS=Path('validation/holdout_20260822_23_cards.json')
PROFILE25=Path('data/horse_profiles_2025.csv')
RESULTS25=Path('data/race_results_html_2025.csv')
SEALED=Path('validation/holdout_20260822_23_v12_sealed.json')
FULL=Path('docs/data/replay-holdout-2026-08-22-23.json')
AXIS=Path('docs/data/replay-axis-results-holdout-2026-08-22-23.json')
STATUS=Path('status/holdout-2026-08-22-23-v12.json')

FORBIDDEN={'finish_position','popularity','time','margin','last3f','corner_positions','body_weight_delta','source_url'}

def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def num(v,d=None):
    try:return float(str(v).replace(',',''))
    except:return d
def integer(v,d=None):
    m=re.search(r'\d+',str(v or ''));return int(m.group()) if m else d
def ndate(v):
    s=str(v or '').replace('年','-').replace('月','-').replace('日','').replace('/','-').replace('.','-')
    m=re.search(r'(20\d{2})-(\d{1,2})-(\d{1,2})',s)
    return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''
def val(row,keys):
    for c,v in row.items():
        if any(k in str(c) for k in keys) and str(v).strip() not in ('','nan','None'):return str(v).strip()
    return ''
def surf_dist(row):
    text=' '.join(row.values());m=re.search(r'(芝|ダート|ダ)\s*([0-9]{3,4})',text)
    return (('ダート' if m.group(1)!='芝' else '芝'),int(m.group(2))) if m else ('',None)

def prepare():
    raw=rows(RAW)
    grouped=defaultdict(list)
    for x in raw:
        if x.get('race_date') not in TARGET:continue
        key=(x.get('race_id'),x.get('race_date'),x.get('course'),integer(x.get('race_no')))
        grouped[key].append(x)
    races=[]
    for (rid,date,track,rn),rs in grouped.items():
        if not rid or not date or not track or not rn:continue
        first=rs[0]
        horses=[]
        for x in sorted(rs,key=lambda z:integer(z.get('horse_no'),99)):
            h={'n':str(integer(x.get('horse_no'),'')),'name':x.get('horse_name',''),'horse_id':x.get('horse_id',''),'jockey':x.get('jockey',''),'trainer':x.get('trainer','')}
            if h['n'] and h['name']:horses.append(h)
        races.append({'race_id':rid,'date':date,'track':track,'race_no':rn,'race_name':first.get('race_name',''),'surface':first.get('surface',''),'distance_m':integer(first.get('distance_m')),'race_class':first.get('race_class',''),'race_category':first.get('race_category',''),'horses':horses})
    races.sort(key=lambda r:(r['date'],r['track'],r['race_no']))
    if len(races)!=72:raise RuntimeError(f'holdout card gate expected 72 races, got {len(races)}')
    if any(len(r['horses'])<3 for r in races):raise RuntimeError('invalid holdout runner coverage')
    payload={'mode':'SANITIZED_HOLDOUT_CARDS','dates':sorted(TARGET),'race_count':len(races),'forbidden_result_fields':sorted(FORBIDDEN),'source_note':'Historical JRA result export was used only by prepare stage to reconstruct entrant/race-card fields. The predict stage cannot read the target result or payout export.','races':races}
    CARDS.parent.mkdir(parents=True,exist_ok=True);CARDS.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'stage':'prepare','race_count':len(races),'cards':str(CARDS)},ensure_ascii=False))

def parse_profile_rows(html):
    out=[]
    for table in normalized_tables(html):
        if not any(('レース名' in c or '競走名' in c) for c in table.columns):continue
        for _,rr in table.iterrows():
            r={str(c):str(v).strip() for c,v in rr.items()};date=ndate(val(r,['年月日','日付']));finish=integer(val(r,['着順']))
            if not date or finish is None:continue
            s,d=surf_dist(r);out.append({'date':date,'finish':finish,'surface':s,'distance_m':d,'last3f':num(val(r,['上り3F','上がり3F','上り']))})
    return sorted(out,key=lambda x:x['date'],reverse=True)
def fetch_histories(races):
    ids=sorted({h['horse_id'] for r in races for h in r['horses'] if h.get('horse_id')});out={};errors=[]
    def one(hid):return hid,parse_profile_rows(request_profile(hid))
    with ThreadPoolExecutor(max_workers=16) as ex:
        fs={ex.submit(one,h):h for h in ids}
        for i,f in enumerate(as_completed(fs),1):
            hid=fs[f]
            try:k,v=f.result();out[k]=v
            except Exception as e:out[hid]=[];errors.append({'horse_id':hid,'error':repr(e)})
            if i%100==0:print(f'profiles {i}/{len(ids)} errors={len(errors)}',flush=True)
    return out,errors
def base25():return {r.get('horse_id',''):r for r in rows(PROFILE25)}
def people25():
    jockey=defaultdict(lambda:[0,0]);trainer=defaultdict(lambda:[0,0])
    for r in rows(RESULTS25):
        f=integer(r.get('finish_position'))
        if f is None:continue
        for key,b in ((r.get('jockey',''),jockey),(r.get('trainer',''),trainer)):
            if key:b[key][0]+=1;b[key][1]+=int(f<=3)
    def rate(b,k):
        n,x=b.get(k,[0,0]);return (x+2)/(n+8) if n else .25
    return lambda k:rate(jockey,k),lambda k:rate(trainer,k)
def features(h,r,hist,b,jr,tr):
    starts25=int(num(b.get('starts'),0) or 0);top325=int(num(b.get('top3'),0) or 0);starts26=len(hist);top326=sum(x['finish']<=3 for x in hist)
    starts=starts25+starts26;show=(top325+top326+1.5)/(starts+5) if starts else .30;recent=hist[:5]
    if recent:
        ws=[5,4,3,2,1][:len(recent)];rec=sum(w*(1/max(1,min(18,x['finish']))) for w,x in zip(ws,recent))/sum(ws);rec=min(1,rec*3.2)
    else:
        av=num(b.get('avg_finish'));rec=max(0,min(1,(12-(av or 12))/11)) if av else .35
    matches=[x for x in hist if x['surface']==r.get('surface') and x['distance_m'] and abs(x['distance_m']-int(r.get('distance_m') or 0))<=300]
    cond=(sum(x['finish']<=3 for x in matches)+1)/(len(matches)+3) if matches else show
    ls=[x['last3f'] for x in recent if x.get('last3f')];l3=.5 if not ls else max(0,min(1,(40-min(ls))/8));j=jr(h.get('jockey',''));tt=tr(h.get('trainer',''));unc=1-min(1,starts/5)
    score=45*show+25*rec+10*cond+8*j+7*tt+5*l3-8*unc
    return {'score':round(score,3),'starts_before':starts,'show_rate_prior':round(show,4),'recent_form':round(rec,4),'condition_fit':round(cond,4),'uncertainty':round(unc,4)}

def predict():
    # Leakage firewall: this stage deliberately has no RAW/PAYOUT read.
    cards=json.loads(CARDS.read_text(encoding='utf-8'))
    races=cards['races'];base=base25();jr,tr=people25();histories,errors=fetch_histories(races);excluded=0;pred=[]
    for i,r in enumerate(races,1):
        rank=[]
        for h in r['horses']:
            rawhist=histories.get(h.get('horse_id',''),[]);hist=[x for x in rawhist if x['date']<r['date']];excluded+=sum(x['date']>=r['date'] for x in rawhist)
            rank.append({'n':h['n'],'name':h['name'],'horse_id':h.get('horse_id',''),'running_style':'UNKNOWN',**features(h,r,hist,base.get(h.get('horse_id',''),{}),jr,tr)})
        rank.sort(key=lambda x:(-x['score'],int(x['n'])));race={**r,'ranked_snapshot':rank[:10]};a=analyze_race(race)
        axis=a.get('axis',{});roles=a.get('partner_roles',[]);intr=a.get('third_place_intrusion',[])
        partners=[f"{x['horse_no']} {x.get('horse_name','')}" for x in roles[:3]]
        holes=[f"{x['horse_no']} {x.get('horse_name','')}" for x in intr[:2]] or [f"{x['n']} {x['name']}" for x in rank[4:6]]
        p={k:r.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')}
        p.update({'prediction_source':'V1.2_STRICT_HOLDOUT','type_label':'V1.2 結果遮断検証','decision':a.get('classification'),'pre_market_decision':a.get('pre_market_decision'),'axis':f"{axis.get('horse_no','')} {axis.get('horse_name','')}".strip(),'partners':partners,'holes':holes,'pre_note':f"軸耐久性 {a.get('axis_durability',{}).get('status','')} / データ品質 {a.get('data_quality','')}。人気・オッズ・当該レース結果は不使用。",'formation':a.get('ticket_shape'),'tickets':a.get('trio_tickets',[]),'ticket_count':a.get('ticket_count',0),'stake':100*int(a.get('ticket_count',0)),'analysis':a,'ranked_snapshot':rank[:10]})
        pred.append(p)
        if i%12==0:print(f'prediction {i}/72',flush=True)
    core={'mode':'STRICT_HOLDOUT_V12_PRE_RESULT','dates':sorted(TARGET),'race_count':len(pred),'model_version':MODEL_VERSION,'leakage_policy':'Target results, popularity, odds and payouts are unread by predict stage. Current profile histories are filtered strictly to dates before each target race.','profile_fetch_errors':errors,'excluded_profile_rows_at_or_after_target':excluded,'races':pred}
    raw=json.dumps(core,ensure_ascii=False,separators=(',',':'));core['prediction_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest();SEALED.parent.mkdir(parents=True,exist_ok=True);SEALED.write_text(json.dumps(core,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'stage':'predict','race_count':len(pred),'model_version':MODEL_VERSION,'hash':core['prediction_hash_sha256'],'profile_errors':len(errors),'excluded_future_rows':excluded},ensure_ascii=False))

def score():
    if not SEALED.exists():raise RuntimeError('sealed prediction required before score stage')
    sealed=json.loads(SEALED.read_text(encoding='utf-8'));rr=[x for x in rows(RAW) if x.get('race_date') in TARGET];pp=[x for x in rows(PAYOUT) if x.get('race_date') in TARGET and x.get('bet_type') in ('3連複','三連複')]
    byid=defaultdict(list)
    for x in rr:byid[x.get('race_id')].append(x)
    pay={x.get('race_id'):x for x in pp}
    summary={'races':0,'A':0,'B':0,'C':0,'PASS':0,'buy_races':0,'caution_races':0,'axis_top3':0,'axis_first':0,'trio_hits_all_nonpass':0,'trio_hits_buy':0,'stake_buy':0,'return_buy':0,'hedged_axis_fail_rescues':0,'candidate_top3_complete':0,'ticket_conversion_failures':0}
    out=[];axisrows=[];venue=defaultdict(lambda:{'races':0,'axis_top3':0,'buy_races':0,'trio_hits_buy':0})
    for p in sealed['races']:
        actual=byid.get(p['race_id'],[]);finished=sorted([(integer(x.get('finish_position'),99),str(integer(x.get('horse_no'),'')),x.get('horse_name',''),integer(x.get('popularity'))) for x in actual if integer(x.get('finish_position')) and integer(x.get('finish_position'))<=3]);topset={n for _,n,_,_ in finished}
        ax=str(p.get('axis','')).split()[0];axrow=next((x for x in actual if str(integer(x.get('horse_no'),''))==ax),{});axfinish=integer(axrow.get('finish_position'));axpop=integer(axrow.get('popularity'))
        pr=pay.get(p['race_id'],{});sel=re.findall(r'\d+',pr.get('winning_selection',''));winning='-'.join(map(str,sorted(map(int,sel)))) if len(sel)>=3 else '';tickets=set(p.get('tickets') or []);hit=bool(winning and winning in tickets);cls=p.get('decision','PASS');buy=p.get('pre_market_decision')=='BUY';caution=p.get('pre_market_decision')=='CAUTION';ret=int(num(pr.get('payout_per_100_yen'),0) or 0) if hit else 0
        cand={str(x.get('n')) for x in p.get('ranked_snapshot',[])[:6]};captured=len(topset&cand);conv=(captured==3 and not hit and cls!='PASS');axisfree_hit=hit and ax not in topset and any(ax not in t.split('-') and t==winning for t in tickets)
        q=dict(p);q.update({'result_top3':[f'{n} {name}' for _,n,name,_ in finished],'trio_result':winning,'trio_payout':int(num(pr.get('payout_per_100_yen'),0) or 0),'hit':hit,'axis_finish':axfinish,'axis_popularity':axpop,'axis_survived':ax in topset,'candidate_top3_captured':captured,'ticket_conversion_failure':conv,'hedged_axis_fail_rescue':axisfree_hit})
        if cls=='PASS':q['review']='PASS。封印後に結果を開封。予想順位・判定は変更していない。'
        elif hit and ax not in topset:q['review']='的中。軸飛びをHEDGEDの軸なし買い目で救済。'
        elif hit:q['review']='的中。封印済み買い目に実三連複を含んだ。'
        elif conv:q['review']='上位候補6頭内に馬券内3頭を捕捉したが、買い目変換で落とした。'
        elif ax in topset:q['review']=f'軸は馬券内。候補捕捉{captured}/3で相手側の取りこぼし。'
        else:q['review']=f'軸が馬券外。候補捕捉{captured}/3。軸選定または構造判断の失敗。'
        out.append(q);summary['races']+=1;summary[cls]=summary.get(cls,0)+1;summary['buy_races']+=int(buy);summary['caution_races']+=int(caution);summary['axis_top3']+=int(ax in topset);summary['axis_first']+=int(axfinish==1);summary['trio_hits_all_nonpass']+=int(hit and cls!='PASS');summary['trio_hits_buy']+=int(hit and buy);summary['stake_buy']+=int(p.get('stake') or 0) if buy else 0;summary['return_buy']+=ret if buy else 0;summary['hedged_axis_fail_rescues']+=int(axisfree_hit);summary['candidate_top3_complete']+=int(captured==3);summary['ticket_conversion_failures']+=int(conv)
        v=venue[p['track']];v['races']+=1;v['axis_top3']+=int(ax in topset);v['buy_races']+=int(buy);v['trio_hits_buy']+=int(hit and buy)
        ev='HIT' if axfinish==1 else ('PLACE' if axfinish and axfinish<=3 else 'MISS');symbol='◎' if ev=='HIT' else ('△' if ev=='PLACE' else '×');label='軸馬1着' if ev=='HIT' else ('軸馬2〜3着' if ev=='PLACE' else '軸馬4着以下')
        axisrows.append({'date':p['date'],'track':p['track'],'race_no':p['race_no'],'matched':bool(axrow),'evaluation':ev,'symbol':symbol,'label':label,'horse_name':axrow.get('horse_name') or str(p.get('axis','')).partition(' ')[2],'axis_horse_name':str(p.get('axis','')).partition(' ')[2],'finish':axfinish,'popularity':axpop})
    summary['axis_top3_rate_pct']=round(100*summary['axis_top3']/summary['races'],2) if summary['races'] else 0;summary['buy_hit_rate_pct']=round(100*summary['trio_hits_buy']/summary['buy_races'],2) if summary['buy_races'] else 0;summary['buy_roi_pct']=round(100*summary['return_buy']/summary['stake_buy'],2) if summary['stake_buy'] else 0;summary['venue_breakdown']=dict(venue);summary['model_tuned_after_holdout']=False
    FULL.parent.mkdir(parents=True,exist_ok=True);FULL.write_text(json.dumps({'mode':'STRICT_HOLDOUT_V12_SCORED','dates':sorted(TARGET),'model_version':MODEL_VERSION,'prediction_hash_sha256':sealed.get('prediction_hash_sha256'),'summary':summary,'races':out},ensure_ascii=False,separators=(',',':')),encoding='utf-8');AXIS.write_text(json.dumps({'rows':axisrows},ensure_ascii=False,separators=(',',':')),encoding='utf-8');STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'stage':'score',**summary},ensure_ascii=False,indent=2))

def main():
    if len(sys.argv)!=2 or sys.argv[1] not in ('prepare','predict','score'):raise SystemExit('usage: prepare|predict|score')
    {'prepare':prepare,'predict':predict,'score':score}[sys.argv[1]]()
if __name__=='__main__':main()
