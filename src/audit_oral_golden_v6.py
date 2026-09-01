#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
G=Path('docs/data/oral-chat-golden-cases.json');S=Path('docs/data/oral-golden-fast-v6.json');O=Path('status/oral-golden-v6-audit.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''
def nos(xs):return [no(x) for x in (xs or []) if no(x)]
def main():
 g=json.loads(G.read_text());s=json.loads(S.read_text());sm={key(r):r for r in s['races']};rows=[]
 for c in g['cases']:
  r=sm.get(key(c),{});a=r.get('analysis') or {};axis=str((a.get('axis') or {}).get('horse_no') or '')
  exp_partner=set(nos(c.get('partners')));exp_union=set(nos(c.get('partners'))+nos(c.get('holes')))
  sys_main={str(x.get('horse_no') or '') for x in a.get('role_main_partners',[])};sys_union={str(x.get('horse_no') or '') for x in a.get('partner_roles',[])}
  pr=len(exp_partner&sys_union)/len(exp_partner) if exp_partner else 1.0;cr=len(exp_union&sys_union)/len(exp_union) if exp_union else 1.0
  et=set(c.get('tickets') or []);st=set(a.get('trio_tickets') or []);te=(et==st) if c.get('tickets_verified') else None
  rows.append({'date':c['date'],'track':c['track'],'race_no':c['race_no'],'axis_match':axis==no(c.get('axis')),'decision_match':a.get('pre_market_decision')==c.get('decision'),'partner_recall':round(pr,4),'candidate_recall':round(cr,4),'main_expected':sorted(exp_partner,key=int),'main_system':sorted(sys_main,key=int),'candidate_expected':sorted(exp_union,key=int),'candidate_system':sorted(sys_union,key=int),'tickets_verified':bool(c.get('tickets_verified')),'ticket_exact_match':te,'ticket_overlap':len(et&st) if c.get('tickets_verified') else None,'expected_ticket_count':len(et) if c.get('tickets_verified') else None,'system_ticket_count':len(st)})
 axis_ok=all(x['axis_match'] for x in rows);decision_ok=all(x['decision_match'] for x in rows);partner_ok=all(x['partner_recall']>=.66 for x in rows);candidate_ok=all(x['candidate_recall']>=.70 for x in rows);verified=[x for x in rows if x['tickets_verified']];ticket_ok=all(x['ticket_exact_match'] for x in verified)
 no_leak=not bool(s.get('result_data_used')) and not bool(s.get('odds_popularity_used'))
 out={'version':'ORAL_GOLDEN_V6_AUDIT','axis_parity':axis_ok,'decision_parity':decision_ok,'partner_gate':partner_ok,'candidate_gate':candidate_ok,'ticket_parity':ticket_ok,'prediction_input_isolation':no_leak,'golden_certified':bool(axis_ok and decision_ok and partner_ok and candidate_ok and ticket_ok and no_leak),'criteria':{'axis':'100%','decision':'100%','partner_recall':'each >=66%','candidate_recall':'each >=70%','verified_tickets':'100% exact','input_isolation':'target result/odds/popularity unused'},'cases':rows};O.parent.mkdir(exist_ok=True);O.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
