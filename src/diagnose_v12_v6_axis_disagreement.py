#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path

V6=Path('docs/data/oral-v6-72-predictions-sealed.json')
V12=Path('docs/data/oral-v12-72-rank-consensus-sealed.json')
GOLD=Path('docs/data/oral-chat-golden-cases.json')
OUT=Path('status/oral-v12-v6-axis-disagreement.json')

def key(r): return (str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0))
def no(v):
    m=re.match(r'\s*(\d+)',str(v or ''))
    return m.group(1) if m else ''
def axis_no(a): return str((a.get('axis') or {}).get('horse_no') or '')
def compact(a):
    d=a.get('axis_durability') or {}
    return {
      'axis':axis_no(a),'decision':a.get('pre_market_decision'),'classification':a.get('classification'),
      'ticket_count':a.get('ticket_count'),'ticket_shape':a.get('ticket_shape'),
      'durability':{k:d.get(k) for k in ('score','gap_to_second','uncertainty','level','reason') if k in d},
      'main':[str(x.get('horse_no') or '') for x in a.get('role_main_partners',[])],
      'holes':[str(x.get('horse_no') or '') for x in a.get('role_holes',[])],
    }
def runner_rows(r,n):
    out=[]
    for field in ('ranked_snapshot','full_field'):
      for x in r.get(field,[]) or []:
        hn=str(x.get('n') or x.get('horse_no') or '')
        if hn.lstrip('0')==str(n).lstrip('0'):
          keep={k:x.get(k) for k in (
            'n','horse_no','name','horse_name','score','base_score_v1','oral_structure_score','structure_score',
            'recent_top3_rate','same_class_top3_rate','exact_class_top3_rate','exact_track_top3_rate',
            'latest_finish','latest_same_class_finish','latest_exact_class_finish','latest_exact_track_finish',
            'history_rows_before','uncertainty','rank','ability_rank','condition_rank','consensus_rank','consensus_score'
          ) if k in x}
          out.append({'source_field':field,**keep})
    return out

def main():
    v6=json.loads(V6.read_text()); v12=json.loads(V12.read_text()); gold=json.loads(GOLD.read_text())
    m6={key(r):r for r in v6.get('races',[])}; m12={key(r):r for r in v12.get('races',[])}
    golden={key(x):no(x.get('axis')) for x in gold.get('cases',[])}
    rows=[]
    for k,r12 in m12.items():
      r6=m6.get(k)
      if not r6: continue
      a6=r6.get('analysis') or {}; a12=r12.get('analysis') or {}; n6=axis_no(a6); n12=axis_no(a12)
      if n6==n12: continue
      rows.append({
        'date':k[0],'track':k[1],'race_no':k[2],'race_name':r12.get('race_name'),
        'is_golden':k in golden,'golden_axis':golden.get(k),
        'v6':compact(a6),'v12':compact(a12),
        'v6_axis_features_v6':runner_rows(r6,n6),'v6_axis_features_v12':runner_rows(r12,n6),
        'v12_axis_features_v6':runner_rows(r6,n12),'v12_axis_features_v12':runner_rows(r12,n12),
      })
    payload={
      'source':'sealed pre-race V6 and V12 predictions only; no target results used',
      'disagreement_count':len(rows),'golden_disagreement_count':sum(x['is_golden'] for x in rows),
      'rows':rows
    }
    OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));
    print(json.dumps({'disagreement_count':payload['disagreement_count'],'golden_disagreement_count':payload['golden_disagreement_count']},ensure_ascii=False))
if __name__=='__main__': main()
