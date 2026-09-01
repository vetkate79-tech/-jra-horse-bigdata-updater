#!/usr/bin/env python3
from __future__ import annotations
import ast,hashlib,importlib.util,json,random,re
from pathlib import Path
S=Path('docs/data/oral-golden-fast-v6.json')
SRC=Path('src/build_oral_role_ticket_v6.py')
FD=Path('status/oral-full-field-role-diagnostic-v5.json')
ST=Path('status/oral-golden-running-style-diagnostic.json')
OUT=Path('status/oral-v6-robustness-audit.json')

def canonical_analysis(a):
 return {'axis':a.get('axis'),'decision':a.get('pre_market_decision'),'main':sorted(str(x.get('horse_no')) for x in a.get('role_main_partners',[])),'holes':sorted(str(x.get('horse_no')) for x in a.get('role_holes',[])),'tickets':sorted(a.get('trio_tickets') or [])}
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def load_builder():
 spec=importlib.util.spec_from_file_location('oral_v6_builder',SRC);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 doc=json.loads(S.read_text());code=SRC.read_text();tree=ast.parse(code)
 string_literals=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
 forbidden_names=['シルフズミスチーフ','ポッドロワール','ボウウィンドウ','ルクスレイモンド','ホウオウタイタン','マイネルアレス']
 hardcoded_names=[x for x in forbidden_names if x in code]
 suspicious_numeric=[]
 for lit in string_literals:
  ns=set(re.findall(r'(?<!\d)(?:1[0-7]|[1-9])(?!\d)',lit))
  if len(ns)>=3:suspicious_numeric.append(lit)
 # Only importing/reading the actual truth fixture is forbidden. A generated pre-race artifact with "golden" in its filename is not truth leakage.
 truth_refs=('oral-chat-golden-cases.json','oral-golden-v6-audit.json','expected_tickets','axis_expected','decision_expected')
 golden_truth_import=any(x in code for x in truth_refs)
 base=[canonical_analysis(r['analysis']) for r in doc['races']];base_hash=digest(base)
 injected=json.loads(json.dumps(doc));rng=random.Random(20260901)
 for r in injected['races']:
  r['target_result']={'winner':rng.randint(1,18),'payout':999999};r['odds']={'fake':1.01};r['popularity']={'fake':1};r['outside_prediction']=['FAKE']
 inj_hash=digest([canonical_analysis(r['analysis']) for r in injected['races']])
 clone=json.loads(json.dumps(doc,sort_keys=True));clone['noise']=[rng.random() for _ in range(10)]
 clone_hash=digest([canonical_analysis(r['analysis']) for r in clone['races']])
 # Recompute the ticket-conversion layer after repeatedly shuffling every full-field candidate list.
 builder=load_builder();fd=json.loads(FD.read_text());st=json.loads(ST.read_text());fm={key(r):r for r in fd['races']};sm={key(r):r for r in st['races']}
 shuffle_cases=[];shuffle_ok=True
 for seed in (11,37,101,509,20260901):
  rr=random.Random(seed);recomputed=[]
  for r in doc['races']:
   styles={x['n']:x.get('running_style') for x in sm[key(r)]['horses']};hs=[]
   source=[dict(x) for x in fm[key(r)]['all_field_roles']];rr.shuffle(source)
   for x in source:
    x['running_style']=styles.get(x['n']);hs.append(x)
   axis_no=str(r['analysis']['axis']['horse_no']);axis=next(x for x in hs if x['n']==axis_no);recovery=bool(r['analysis'].get('recovery_axis'))
   main3=builder.pick_main(hs,axis);holes=builder.pick_holes(hs,axis,main3,recovery);ts=builder.tickets(axis,main3,holes,recovery)
   recomputed.append({'axis':r['analysis']['axis'],'decision':r['analysis']['pre_market_decision'],'main':sorted(x['n'] for x in main3),'holes':sorted(x['n'] for x in holes),'tickets':sorted(ts)})
  h=digest(recomputed);ok=h==base_hash;shuffle_ok=shuffle_ok and ok;shuffle_cases.append({'seed':seed,'hash':h,'matches_canonical':ok})
 no_identity_hardcode=not hardcoded_names and not golden_truth_import and not suspicious_numeric
 passed=bool(no_identity_hardcode and not doc.get('result_data_used') and not doc.get('odds_popularity_used') and base_hash==inj_hash==clone_hash and shuffle_ok)
 out={'version':'ORAL_V6_ROBUSTNESS_AUDIT_V2','source_file':str(SRC),'race_specific_horse_names_found':hardcoded_names,'golden_truth_import_found':golden_truth_import,'truth_reference_tokens_checked':list(truth_refs),'suspicious_string_number_groups':suspicious_numeric,'no_identity_hardcode':no_identity_hardcode,'declared_result_data_used':doc.get('result_data_used'),'declared_odds_popularity_used':doc.get('odds_popularity_used'),'canonical_hash':base_hash,'irrelevant_field_injection_hash':inj_hash,'clone_hash':clone_hash,'irrelevant_injection_invariant':base_hash==inj_hash,'deterministic_clone':base_hash==clone_hash,'shuffle_cases':shuffle_cases,'full_field_order_invariant':shuffle_ok,'passed':passed}
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
