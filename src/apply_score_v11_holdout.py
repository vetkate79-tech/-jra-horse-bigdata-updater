#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,itertools,json
from collections import Counter,defaultdict
from pathlib import Path
PRED=Path('docs/data/oral-v10-72-connected-durability-sealed.json')
CFG=Path('status/oral-v11-purchase-gate-config.json')
RES=Path('data/race_results_html_2026.csv')
OUTP=Path('docs/data/oral-v11-72-gated-predictions-sealed.json')
OUTS=Path('docs/data/oral-v11-holdout-scored.json')
STATUS=Path('status/oral-v11-holdout-scored.json')
HOLDOUT='2026-08-30'

def f(v,d=0.0):
    try:return float(v)
    except:return d

def combo(a,b,c):return '-'.join(map(str,sorted(map(int,[a,b,c]))))
def generic_tickets(a):
    axis=str((a.get('axis') or {}).get('horse_no') or '');main=[str(x.get('horse_no')) for x in a.get('role_main_partners',[]) if x.get('horse_no')];holes=[str(x.get('horse_no')) for x in a.get('role_holes',[]) if x.get('horse_no')];out=[]
    for x,y in itertools.combinations(main[:3],2):out.append(combo(axis,x,y))
    for m in main[:3]:
        for h in holes[:4]:
            t=combo(axis,m,h)
            if t not in out:out.append(t)
            if len(out)>=9:return out[:9]
    return out[:9]
def selected(a,rule):
    d=a.get('axis_durability') or {};score=f(d.get('score'));gap=f(d.get('gap_to_second'));unc=f(d.get('uncertainty'),1)
    return rule['score_min']<=score<rule['score_max_exclusive'] and rule['gap_min']<=gap<=rule['gap_max'] and unc<=rule['uncertainty_max']
def norm(v):return str(v or '').strip().replace('競馬場','')
def i(v):
    try:return int(float(str(v).strip()))
    except:return None
def key(d,t,r):return(str(d),norm(t),i(r))

def main():
    p=json.loads(PRED.read_text());cfg=json.loads(CFG.read_text());rule=cfg['selected_rule'];rows=[]
    for r in p['races']:
        a=json.loads(json.dumps(r['analysis'],ensure_ascii=False));buy=selected(a,rule);a['pre_market_decision']='BUY' if buy else 'PASS';a['classification']='B' if buy else 'PASS';a['purchase_gate_version']='V11_HOLDOUT_CALIBRATED_0829';a['purchase_gate_config_hash']=cfg['config_hash_sha256'];a['purchase_gate_rule']=rule;a['trio_tickets']=generic_tickets(a) if buy else [];a['ticket_count']=len(a['trio_tickets']);a['ticket_shape']='V11_GATED_AXIS9' if buy else 'PASS';rows.append({**{k:r.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m')},'analysis':a})
    payload={'version':'ORAL_V11_72_GATED','source_prediction_hash':p['prediction_hash_sha256'],'gate_config_hash':cfg['config_hash_sha256'],'train_date':cfg['train_date'],'holdout_date':HOLDOUT,'holdout_results_used_before_seal':False,'races':rows};canon=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'));payload['prediction_hash_sha256']=hashlib.sha256(canon.encode()).hexdigest();OUTP.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    raw=list(csv.DictReader(RES.open(encoding='utf-8-sig',newline='')));by=defaultdict(list)
    for x in raw:
        k=key(x.get('race_date'),x.get('course'),x.get('race_no'))
        if k[0]==HOLDOUT:by[k].append(x)
    scored=[];g=Counter();tb=th=0
    for r in rows:
        if r['date']!=HOLDOUT:continue
        rr=by.get(key(r['date'],r['track'],r['race_no']),[]);a=r['analysis'];axis=str((a.get('axis') or {}).get('horse_no') or '');ar=next((x for x in rr if str(x.get('horse_no') or '').lstrip('0')==axis.lstrip('0')),None);assert ar is not None
        fin=i(ar.get('finish_position'));grade='HIT' if fin==1 else 'PLACE' if fin and fin<=3 else 'MISS';g[grade]+=1;top3=[x for x in rr if i(x.get('finish_position')) in (1,2,3)];actual=combo(*[x.get('horse_no') for x in top3]) if len(top3)==3 else None;bought=a['pre_market_decision']=='BUY';hit=bool(bought and actual in set(a.get('trio_tickets') or []));tb+=int(bought);th+=int(hit);scored.append({'date':r['date'],'track':r['track'],'race_no':r['race_no'],'decision':a['pre_market_decision'],'axis_finish':fin,'axis_grade':grade,'trio_hit':hit})
    bought_rows=[x for x in scored if x['decision']=='BUY'];bg=Counter(x['axis_grade'] for x in bought_rows);summary={'version':'ORAL_V11_HOLDOUT_SCORE','config_hash':cfg['config_hash_sha256'],'prediction_hash':payload['prediction_hash_sha256'],'holdout_date':HOLDOUT,'holdout_races':len(scored),'holdout_bought_races':tb,'holdout_bought_axis_top3':bg['HIT']+bg['PLACE'],'holdout_bought_axis_top3_rate_pct':round((bg['HIT']+bg['PLACE'])/tb*100,2) if tb else 0,'holdout_bought_axis_win_rate_pct':round(bg['HIT']/tb*100,2) if tb else 0,'holdout_trio_hits':th,'holdout_trio_hit_rate_pct':round(th/tb*100,2) if tb else 0,'holdout_results_opened_after_seal':True};OUTS.write_text(json.dumps({'summary':summary,'races':scored},ensure_ascii=False,indent=2));STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
