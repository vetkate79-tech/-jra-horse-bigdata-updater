#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, itertools, json, math, re, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables
from oral_operational_layer import analyze_race, MODEL_VERSION

DATES=['2026-08-01','2026-08-02','2026-08-08','2026-08-09','2026-08-15','2026-08-16']
RAW_FILES=[Path('data/race_results_html_2026_evo_0801_02.csv'),Path('data/race_results_html_2026_evo_0808_09.csv'),Path('data/race_results_html_2026_evo_0815_16.csv')]
PAYOUT_FILES=[Path('data/race_payouts_2026_evo_0801_02.csv'),Path('data/race_payouts_2026_evo_0808_09.csv'),Path('data/race_payouts_2026_evo_0815_16.csv')]
CARDS=Path('validation/august_evolution_216r_cards.json')
SEALED=Path('validation/august_evolution_216r_base_sealed.json')
REPORT=Path('status/august-evolution-216r.json')
DETAIL=Path('validation/august_evolution_216r_scored.json')
PROFILE25=Path('data/horse_profiles_2025.csv')
RESULTS25=Path('data/race_results_html_2025.csv')
FORBIDDEN={'finish_position','popularity','time','margin','last3f','corner_positions','body_weight_delta','source_url'}

def rows(path):
    if not path.exists(): return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
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
    raw=[]
    for p in RAW_FILES: raw.extend(rows(p))
    grouped=defaultdict(list)
    for x in raw:
        if x.get('race_date') not in DATES: continue
        key=(x.get('race_id'),x.get('race_date'),x.get('course'),integer(x.get('race_no')))
        grouped[key].append(x)
    races=[]
    for (rid,date,track,rn),rs in grouped.items():
        if not rid or not date or not track or not rn:continue
        first=rs[0]; horses=[]
        for x in sorted(rs,key=lambda z:integer(z.get('horse_no'),99)):
            h={'n':str(integer(x.get('horse_no'),'')),'name':x.get('horse_name',''),'horse_id':x.get('horse_id',''),'jockey':x.get('jockey',''),'trainer':x.get('trainer','')}
            if h['n'] and h['name']:horses.append(h)
        races.append({'race_id':rid,'date':date,'track':track,'race_no':rn,'race_name':first.get('race_name',''),'surface':first.get('surface',''),'distance_m':integer(first.get('distance_m')),'race_class':first.get('race_class',''),'race_category':first.get('race_category',''),'horses':horses})
    races.sort(key=lambda r:(r['date'],r['track'],r['race_no']))
    counts={d:sum(r['date']==d for r in races) for d in DATES}
    if len(races)!=216 or any(v!=36 for v in counts.values()):raise RuntimeError(f'expected 216 races / 36 each, got {len(races)} {counts}')
    if any(len(r['horses'])<3 for r in races):raise RuntimeError('invalid runner coverage')
    CARDS.parent.mkdir(parents=True,exist_ok=True)
    CARDS.write_text(json.dumps({'mode':'SANITIZED_EVOLUTION_CARDS','dates':DATES,'race_count':216,'race_count_by_date':counts,'forbidden_result_fields':sorted(FORBIDDEN),'races':races},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'stage':'prepare','races':216,'by_date':counts},ensure_ascii=False))

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
    cards=json.loads(CARDS.read_text(encoding='utf-8'));races=cards['races'];base=base25();jr,tr=people25();histories,errors=fetch_histories(races);excluded=0;pred=[]
    for i,r in enumerate(races,1):
        rank=[]
        for h in r['horses']:
            rawhist=histories.get(h.get('horse_id',''),[]);hist=[x for x in rawhist if x['date']<r['date']];excluded+=sum(x['date']>=r['date'] for x in rawhist)
            rank.append({'n':h['n'],'name':h['name'],'horse_id':h.get('horse_id',''),'running_style':'UNKNOWN',**features(h,r,hist,base.get(h.get('horse_id',''),{}),jr,tr)})
        rank.sort(key=lambda x:(-x['score'],int(x['n'])));pred.append({**{k:r[k] for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'ranked_snapshot':rank[:10]})
        if i%36==0:print(f'prediction {i}/216',flush=True)
    core={'mode':'STRICT_EVOLUTION_PRE_RESULT','dates':DATES,'race_count':216,'base_model_version':MODEL_VERSION,'leakage_policy':'Target results, popularity, odds and payouts are unread by predict stage. Profile histories filtered strictly before target race date.','profile_fetch_errors':errors,'excluded_profile_rows_at_or_after_target':excluded,'races':pred}
    raw=json.dumps(core,ensure_ascii=False,separators=(',',':'));core['prediction_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest();SEALED.parent.mkdir(parents=True,exist_ok=True);SEALED.write_text(json.dumps(core,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'stage':'predict','races':216,'hash':core['prediction_hash_sha256'],'errors':len(errors),'excluded_future_rows':excluded},ensure_ascii=False))

def reliability(h):
    return 0.42*float(h.get('show_rate_prior',.3))+0.28*float(h.get('condition_fit',.3))+0.20*float(h.get('recent_form',.35))+0.10*(1-float(h.get('uncertainty',1)))
def choose_axis(q,policy):
    if not q:return q
    q=list(q)
    if policy=='safe_swap' and len(q)>1:
        a,b=q[0],q[1]
        if float(a['score'])-float(b['score'])<=2.0 and reliability(b)>=reliability(a)+.07:q[0],q[1]=q[1],q[0]
    elif policy=='safe_top3':
        top=float(q[0]['score']);eligible=[(i,h) for i,h in enumerate(q[:3]) if top-float(h['score'])<=2.5]
        if eligible:
            i,_=max(eligible,key=lambda z:(reliability(z[1]),-z[0]))
            if i:q[0],q[i]=q[i],q[0]
    return q
def structure(q):
    if len(q)<6:return {'axis_gap':0,'boundary_gap':0,'spread6':0,'avg_unc':1}
    return {'axis_gap':float(q[0]['score'])-float(q[1]['score']),'boundary_gap':float(q[2]['score'])-float(q[3]['score']),'spread6':float(q[0]['score'])-float(q[5]['score']),'avg_unc':sum(float(x.get('uncertainty',1)) for x in q[:3])/3}
def add_intrusion(q,a,mode):
    if mode=='base':return a
    existing={x['horse_no'] for x in a.get('third_place_intrusion',[])};extra=[]
    for rank,h in enumerate(q[4:10],5):
        merit=(float(h.get('condition_fit',.3))-.3)*1.8+(float(h.get('recent_form',.35))-.35)*1.3+(float(h.get('show_rate_prior',.3))-.3)*.8+(1-float(h.get('uncertainty',1)))*.3
        if str(h['n']) not in existing and merit>=.12:extra.append((merit,rank,h))
    extra.sort(reverse=True,key=lambda z:z[0])
    a=dict(a);a['third_place_intrusion']=list(a.get('third_place_intrusion',[]))+[{'horse_no':str(h['n']),'horse_name':h['name'],'rank':rank,'intrusion_score':round(m,3)} for m,rank,h in extra[:2]]
    return a
def combo(xs):return '-'.join(map(str,sorted(map(int,xs))))
def reticket(q,a,mode):
    if a.get('classification')=='PASS':return []
    if mode=='base':return list(a.get('trio_tickets') or [])
    axis=str(a.get('axis',{}).get('horse_no',''));ns=[str(x['n']) for x in q[:8]];intr=[x['horse_no'] for x in a.get('third_place_intrusion',[]) if x.get('horse_no') in ns]
    if mode=='coverage':
        pool=list(dict.fromkeys(ns[1:6]+intr))[:6];cand=[]
        for x,y in itertools.combinations(pool,2):cand.append(combo([axis,x,y]))
        cand.sort(key=lambda t:(0 if any(z in intr for z in t.split('-')) else 1,sum(ns.index(z) if z in ns else 9 for z in t.split('-'))))
        return list(dict.fromkeys(cand))[:9]
    if mode=='two_core':
        core=ns[:2];others=list(dict.fromkeys(ns[2:7]+intr));out=[]
        for x in others[:5]:out.append(combo([core[0],core[1],x]))
        for x,y in itertools.combinations(others[:4],2):
            out.append(combo([core[0],x,y]))
            if len(out)>=9:break
        return list(dict.fromkeys(out))[:9]
    if mode=='rank_combo':
        pool=ns[:6];triples=list(itertools.combinations(pool,3));triples.sort(key=lambda c:sum(ns.index(x) for x in c))
        return [combo(c) for c in triples[:10]]
    return list(a.get('trio_tickets') or [])
def apply_gate(q,a,gate):
    if gate=='base':return a
    a=dict(a);s=structure(q);cls=a.get('classification','PASS')
    if gate=='structure' and cls in ('A','B'):
        if s['avg_unc']>.55 or s['spread6']<5 or (s['axis_gap']<1.0 and s['boundary_gap']<.8):cls='C'
    elif gate=='axis_strict' and cls in ('A','B'):
        if s['axis_gap']<2.0 or s['avg_unc']>.50:cls='C'
    a['classification']=cls;a['pre_market_decision']='BUY' if cls in ('A','B') else ('CAUTION' if cls=='C' else 'PASS')
    return a

def predict_model(race,genes):
    q=choose_axis(race['ranked_snapshot'],genes['axis']);safe={**race,'ranked_snapshot':q};a=analyze_race(safe);a=add_intrusion(q,a,genes['intrusion']);a=apply_gate(q,a,genes['gate']);tickets=reticket(q,a,genes['ticket'])
    if a.get('classification')=='PASS':tickets=[]
    candidate=list(dict.fromkeys([str(x['n']) for x in q[:6]]+[x['horse_no'] for x in a.get('third_place_intrusion',[])]))[:7]
    return {'axis':str(a.get('axis',{}).get('horse_no','')),'classification':a.get('classification'),'decision':a.get('pre_market_decision'),'tickets':tickets,'candidate':candidate,'q':q}
def fitness(m):
    roi=min(150,max(0,m['roi_pct']));buy=m['buy_races'];thin=max(0,4-buy)*2.0
    return round(.35*m['axis_top3_pct']+.25*m['candidate_complete_pct']+.20*m['buy_hit_pct']+.20*roi-thin,3)
def score_model(races,actual,payouts,genes):
    byid=actual; metrics={'races':len(races),'axis_top3':0,'candidate_complete':0,'buy_races':0,'hits_buy':0,'stake':0,'return':0};details=[]
    for r in races:
        p=predict_model(r,genes);ars=byid.get(r['race_id'],[]);top3={str(integer(x.get('horse_no'),'')) for x in ars if integer(x.get('finish_position')) and integer(x.get('finish_position'))<=3};win='-'.join(map(str,sorted(map(int,top3)))) if len(top3)==3 else ''
        ax=p['axis'];metrics['axis_top3']+=int(ax in top3);metrics['candidate_complete']+=int(top3.issubset(set(p['candidate'])));buy=p['decision']=='BUY';hit=buy and win in set(p['tickets'])
        if buy:
            metrics['buy_races']+=1;metrics['stake']+=100*len(p['tickets']);metrics['hits_buy']+=int(hit)
            if hit:metrics['return']+=int(payouts.get(r['race_id'],0) or 0)
        details.append({'date':r['date'],'track':r['track'],'race_no':r['race_no'],'axis':ax,'decision':p['decision'],'tickets':p['tickets'],'candidate':p['candidate'],'actual_top3':sorted(top3,key=lambda x:int(x)),'hit':hit})
    n=max(1,metrics['races']);b=max(1,metrics['buy_races']);metrics.update({'axis_top3_pct':round(metrics['axis_top3']/n*100,2),'candidate_complete_pct':round(metrics['candidate_complete']/n*100,2),'buy_hit_pct':round(metrics['hits_buy']/b*100,2) if metrics['buy_races'] else 0.0,'roi_pct':round(metrics['return']/metrics['stake']*100,2) if metrics['stake'] else 0.0});metrics['fitness']=fitness(metrics)
    return metrics,details
def mutate(genes):
    options={'axis':['rank1','safe_swap','safe_top3'],'intrusion':['base','wide'],'ticket':['base','coverage','two_core','rank_combo'],'gate':['base','structure','axis_strict']};out=[]
    for k,vals in options.items():
        for v in vals:
            if v==genes[k]:continue
            g=dict(genes);g[k]=v;out.append((f'{k}:{genes[k]}->{v}',g))
    return out
def acceptable(parent,cand):
    if cand['axis_top3_pct'] < parent['axis_top3_pct']-2.78:return False
    if cand['candidate_complete_pct'] < parent['candidate_complete_pct']-2.78:return False
    if cand['buy_races']<3 and parent['buy_races']>=3:return False
    return cand['fitness']>=parent['fitness']+1.0

def score_evolve():
    sealed=json.loads(SEALED.read_text(encoding='utf-8'));actual_rows=[];pay_rows=[]
    for p in RAW_FILES:actual_rows.extend(rows(p))
    for p in PAYOUT_FILES:pay_rows.extend(rows(p))
    byid=defaultdict(list)
    for x in actual_rows:byid[x.get('race_id')].append(x)
    payouts={}
    for x in pay_rows:
        if x.get('bet_type') in ('3連複','三連複'):payouts[x.get('race_id')]=int(num(x.get('payout_per_100_yen'),0) or 0)
    genes={'axis':'rank1','intrusion':'base','ticket':'base','gate':'base'};reports=[];all_details=[]
    baseline_genes=dict(genes)
    for idx,date in enumerate(DATES,1):
        block=[r for r in sealed['races'] if r['date']==date]
        before,det=score_model(block,byid,payouts,genes);start_genes=dict(genes);selected=[]
        baseline,_=score_model(block,byid,payouts,baseline_genes)
        if idx<6:
            for _ in (1,2):
                candidates=[]
                for label,g in mutate(genes):
                    m,_=score_model(block,byid,payouts,g);candidates.append((m['fitness'],label,g,m))
                candidates.sort(reverse=True,key=lambda x:x[0]);best=next((x for x in candidates if acceptable(before,x[3])),None)
                if not best:break
                _,label,genes,newm=best;selected.append(label);before=newm
            after,det=score_model(block,byid,payouts,genes)
        else:
            after=before
        reports.append({'generation':idx,'date':date,'role':'FINAL_UNSEEN_VALIDATION' if idx==6 else 'DEVELOPMENT_AND_SELECTION','genes_entering':start_genes,'baseline_v12':baseline,'champion_entering':score_model(block,byid,payouts,start_genes)[0],'selected_mutations':selected,'genes_leaving':dict(genes),'champion_after_selection':after})
        all_details.extend(det)
        print(json.dumps({'generation':idx,'date':date,'selected':selected,'genes':genes,'before':reports[-1]['champion_entering'],'after':after},ensure_ascii=False),flush=True)
    final_validation=reports[-1]['champion_entering'];base_final=reports[-1]['baseline_v12']
    promote=(final_validation['fitness']>=base_final['fitness'] and final_validation['axis_top3_pct']>=base_final['axis_top3_pct']-2.78 and final_validation['candidate_complete_pct']>=base_final['candidate_complete_pct']-2.78 and (final_validation['roi_pct']>=base_final['roi_pct'] or final_validation['buy_hit_pct']>=base_final['buy_hit_pct']))
    out={'mode':'SEQUENTIAL_36R_EVOLUTION','dates':DATES,'race_count':216,'base_prediction_hash_sha256':sealed['prediction_hash_sha256'],'leakage_policy':sealed['leakage_policy'],'evolution_policy':'Each 36R block compares champion vs one-gene mutations. Only mutations improving fitness with axis/candidate guardrails are inherited. Final 8/16 block is unseen validation and cannot mutate model.','reports':reports,'final_genes':genes,'promotion_recommended':promote}
    REPORT.parent.mkdir(exist_ok=True);DETAIL.parent.mkdir(exist_ok=True);REPORT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');DETAIL.write_text(json.dumps({'reports':reports,'details':all_details},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'stage':'score_evolve','promotion_recommended':promote,'final_genes':genes},ensure_ascii=False))

if __name__=='__main__':
    stage=sys.argv[1] if len(sys.argv)>1 else ''
    {'prepare':prepare,'predict':predict,'score':score_evolve}.get(stage,lambda:(_ for _ in ()).throw(SystemExit('usage: prepare|predict|score')))()
