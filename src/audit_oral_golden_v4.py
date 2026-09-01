#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
G=Path('docs/data/oral-chat-golden-cases.json');S=Path('docs/data/oral-golden-fast-v4.json');O=Path('status/oral-golden-v4-audit.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def nos(xs):return [no(x) for x in (xs or []) if no(x)]
def main():
 g=json.loads(G.read_text());s=json.loads(S.read_text());sm={key(r):r for r in s['races']};rows=[]
 for c in g['cases']:
  r=sm.get(key(c),{});a=r.get('analysis') or {};axis=str((a.get('axis') or {}).get('horse_no') or '')
  expected_part=nos(c.get('partners'));expected_all=sorted(set(expected_part+nos(c.get('holes'))));sys_roles=[str(x.get('horse_no') or '') for x in a.get('partner_roles',[])];sys_all=sorted(set(sys_roles[:7]))
  part_recall=round(len(set(expected_part)&set(sys_roles[:7]))/len(set(expected_part)),4) if expected_part else None
  candidate_recall=round(len(set(expected_all)&set(sys_all))/len(set(expected_all)),4) if expected_all else None
  et=sorted(set(c.get('tickets') or []));st=sorted(set(a.get('trio_tickets') or []));ticket_exact=(et==st) if c.get('tickets_verified') else None
  rows.append({'date':c['date'],'track':c['track'],'race_no':c['race_no'],'axis_expected':no(c.get('axis')),'axis_system':axis,'axis_match':axis==no(c.get('axis')),'decision_expected':c.get('decision'),'decision_system':a.get('pre_market_decision'),'decision_match':a.get('pre_market_decision')==c.get('decision'),'expected_partners':expected_part,'system_partner_top7':sys_roles[:7],'partner_recall':part_recall,'expected_candidate_union':expected_all,'system_candidate_union_top7':sys_all,'candidate_recall':candidate_recall,'tickets_verified':bool(c.get('tickets_verified')),'expected_tickets':et,'system_tickets':st,'ticket_exact_match':ticket_exact,'ticket_overlap':len(set(et)&set(st)) if c.get('tickets_verified') else None})
 axis_ok=all(x['axis_match'] for x in rows);decision_ok=all(x['decision_match'] for x in rows);partner_ok=all((x['partner_recall'] or 0)>=.66 for x in rows);cand_ok=all((x['candidate_recall'] or 0)>=.70 for x in rows);tv=[x for x in rows if x['tickets_verified']];tickets_ok=all(x['ticket_exact_match'] for x in tv) if tv else False
 out={'version':'ORAL_GOLDEN_V4_AUDIT','axis_parity':axis_ok,'decision_parity':decision_ok,'partner_gate':partner_ok,'candidate_gate':cand_ok,'ticket_parity':tickets_ok,'certified':bool(axis_ok and decision_ok and partner_ok and cand_ok and tickets_ok),'criteria':{'axis':'100%','decision':'100%','partner_recall':'each case >=66%','candidate_union_recall':'each case >=70%','tickets':'100% exact on verified-ticket cases'},'cases':rows};O.parent.mkdir(exist_ok=True);O.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
