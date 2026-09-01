#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
from oral_operational_layer import MODEL_VERSION,analyze_race

BASE=Path('docs/data/replay-2026-08-29-30-sealed.json')
RESULTS=Path('docs/data/replay-2026-08-29-30-full.json')
SEALED=Path('docs/data/oral-integrated-v1-shadow-sealed.json')
EVAL=Path('docs/data/oral-integrated-v1-shadow-evaluation.json')
STATUS=Path('status/oral-integrated-v1-shadow.json')

def key(r):return (r.get('date'),r.get('track'),int(r.get('race_no') or 0))

def seal():
    base=json.loads(BASE.read_text())
    rows=[]
    for r in base.get('races',[]):
        a=analyze_race(r)
        rows.append({
          'race_id':r.get('race_id'),'date':r.get('date'),'track':r.get('track'),'race_no':r.get('race_no'),'race_name':r.get('race_name'),
          'surface':r.get('surface'),'distance_m':r.get('distance_m'),'base_prediction_source':r.get('prediction_source'),
          'analysis':a
        })
    payload={
      'version':MODEL_VERSION,
      'mode':'ORAL_OPERATIONAL_LAYER_SHADOW_PRE_RESULT',
      'result_data_used':False,
      'odds_popularity_used':False,
      'base_prediction_hash':base.get('prediction_hash_sha256'),
      'policy':['ability ranking first','oral operational layer second','market isolated until after seal','missing evidence lowers data quality instead of zero-filling'],
      'race_count':len(rows),'races':rows
    }
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
    payload['prediction_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest()
    SEALED.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
    return payload

def score(sealed):
    # Results are opened only after the shadow snapshot has been written and hashed.
    full=json.loads(RESULTS.read_text())
    outcomes={key(r):r for r in full.get('races',[])}
    s={'races':0,'bets':0,'cautions':0,'passes':0,'hits':0,'stake':0,'return':0,'axis_survived':0,'candidate_top3_complete':0,'ticket_conversion_failures':0,'by_class':{}}
    detail=[]
    for row in sealed['races']:
        a=row['analysis'];o=outcomes.get(key(row),{});tickets=set(a.get('trio_tickets') or []);decision=a.get('pre_market_decision','PASS')
        winner=o.get('trio_result','');hit=bool(tickets and winner in tickets);actual={str(x).split()[0] for x in o.get('result_top3',[]) if str(x).split()}
        axis=str(a.get('axis',{}).get('horse_no',''));cand={axis}
        cand|={str(x.get('horse_no')) for x in a.get('partner_roles',[])[:5]};cand|={str(x.get('horse_no')) for x in a.get('third_place_intrusion',[])}
        cap=len(actual&cand);conv=bool(decision!='PASS' and cap==3 and not hit);ret=int(o.get('trio_payout') or 0) if hit else 0
        s['races']+=1;s['axis_survived']+=int(axis in actual);s['candidate_top3_complete']+=int(cap==3);s['ticket_conversion_failures']+=int(conv)
        cls=a.get('classification','PASS');bc=s['by_class'].setdefault(cls,{'races':0,'bets':0,'hits':0,'stake':0,'return':0});bc['races']+=1
        if decision=='PASS':s['passes']+=1
        else:
            if decision=='CAUTION':s['cautions']+=1
            s['bets']+=1;s['stake']+=100*len(tickets);bc['bets']+=1;bc['stake']+=100*len(tickets)
            if hit:s['hits']+=1;s['return']+=ret;bc['hits']+=1;bc['return']+=ret
        detail.append({**{k:row.get(k) for k in ('date','track','race_no','race_name')},'classification':cls,'decision':decision,'axis':a.get('axis'),'axis_durability':a.get('axis_durability'),'ticket_shape':a.get('ticket_shape'),'ticket_count':len(tickets),'trio_result':winner,'trio_payout':int(o.get('trio_payout') or 0),'hit':hit,'axis_survived':axis in actual,'candidate_top3_captured':cap,'ticket_conversion_failure':conv,'data_quality':a.get('data_quality')})
    s['hit_rate_pct']=round(100*s['hits']/s['bets'],2) if s['bets'] else 0
    s['roi_pct']=round(100*s['return']/s['stake'],2) if s['stake'] else 0
    s['axis_survival_pct']=round(100*s['axis_survived']/s['races'],2) if s['races'] else 0
    s['candidate_top3_complete_pct']=round(100*s['candidate_top3_complete']/s['races'],2) if s['races'] else 0
    for v in s['by_class'].values():
        v['hit_rate_pct']=round(100*v['hits']/v['bets'],2) if v['bets'] else 0;v['roi_pct']=round(100*v['return']/v['stake'],2) if v['stake'] else 0
    out={'version':MODEL_VERSION,'prediction_hash_sha256':sealed['prediction_hash_sha256'],'result_opened_after_seal':True,'summary':s,'truth_note':'Shadow replay evaluates the newly systemized oral operational layer. It is not an unbiased future estimate because the oral rules were designed from prior operating experience; promote only after future sealed weekends.','races':detail}
    EVAL.write_text(json.dumps(out,ensure_ascii=False,indent=2));STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(json.dumps(out,ensure_ascii=False,indent=2));return out

def main():
    sealed=seal()
    assert SEALED.exists() and sealed.get('prediction_hash_sha256')
    out=score(sealed)
    print(json.dumps({'prediction_hash_sha256':sealed['prediction_hash_sha256'],'summary':out['summary']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
