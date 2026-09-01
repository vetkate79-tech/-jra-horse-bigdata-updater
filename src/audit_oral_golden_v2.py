#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path

GOLD=Path('docs/data/oral-chat-golden-cases.json')
SYS=Path('docs/data/oral-integrated-v2-rich-sealed.json')
OUT=Path('docs/data/oral-golden-v2-audit.json')
STATUS=Path('status/oral-golden-v2-audit.json')

def key(r):return (str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0))
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def nos(xs):return [no(x) for x in (xs or []) if no(x)]

def main():
 gold=json.loads(GOLD.read_text());sys=json.loads(SYS.read_text());sm={key(r):r for r in sys.get('races',[])}
 rows=[]
 for g in gold['cases']:
  s=sm.get(key(g),{});a=s.get('analysis') or {};axis=str((a.get('axis') or {}).get('horse_no') or '')
  actual_axis=no(g.get('axis'));actual_dec=g.get('decision');sys_dec=a.get('pre_market_decision')
  actual_part=nos(g.get('partners'));sys_part=[str(x.get('horse_no') or '') for x in a.get('partner_roles',[])[:7]]
  part_recall=round(len(set(actual_part)&set(sys_part))/len(set(actual_part)),4) if actual_part else None
  actual_t=sorted(set(g.get('tickets') or []));sys_t=sorted(set(a.get('trio_tickets') or []));ticket_exact=(actual_t==sys_t) if g.get('tickets_verified') else None
  rows.append({'date':g['date'],'track':g['track'],'race_no':g['race_no'],'race_name':g.get('race_name'),'axis_actual':actual_axis,'axis_system':axis,'axis_match':axis==actual_axis,'decision_actual':actual_dec,'decision_system':sys_dec,'decision_match':actual_dec==sys_dec,'partner_actual':actual_part,'partner_system_top7':sys_part,'partner_recall':part_recall,'tickets_verified':bool(g.get('tickets_verified')),'ticket_exact_match':ticket_exact,'ticket_count_actual':g.get('ticket_count_original_display'),'ticket_count_system':a.get('ticket_count'),'system_ticket_shape':a.get('ticket_shape'),'system_classification':a.get('classification'),'system_ranked_top10':[{'n':x.get('n'),'name':x.get('name'),'score':x.get('score'),'base_score_v1':x.get('base_score_v1'),'latest_finish':x.get('latest_finish'),'latest_same_distance_finish':x.get('latest_same_distance_finish'),'same_distance_top3_rate':x.get('same_distance_top3_rate'),'structural_history_boost':x.get('structural_history_boost')} for x in s.get('ranked_snapshot',[])]})
 axis_ok=all(x['axis_match'] for x in rows);dec_ok=all(x['decision_match'] for x in rows);part_ok=all((x['partner_recall'] or 0)>=0.66 for x in rows);ticket_rows=[x for x in rows if x['tickets_verified']];tickets_ok=all(x['ticket_exact_match'] for x in ticket_rows) if ticket_rows else False
 out={'audit_version':'ORAL_GOLDEN_V2_AUDIT','system_version':sys.get('version'),'golden_case_count':len(rows),'axis_parity':axis_ok,'decision_parity':dec_ok,'partner_recall_gate':part_ok,'ticket_parity_verified_cases':tickets_ok,'certified':bool(axis_ok and dec_ok and part_ok and tickets_ok),'criteria':{'axis':'100%','decision':'100%','partners':'at least 66% recall in every case','tickets':'100% exact on cases where original final tickets are verified'},'cases':rows}
 txt=json.dumps(out,ensure_ascii=False,indent=2);OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(txt);print(json.dumps({'certified':out['certified'],'axis_parity':axis_ok,'decision_parity':dec_ok,'partner_gate':part_ok,'ticket_parity':tickets_ok},ensure_ascii=False))
if __name__=='__main__':main()
