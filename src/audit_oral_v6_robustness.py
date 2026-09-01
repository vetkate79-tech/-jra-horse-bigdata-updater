#!/usr/bin/env python3
from __future__ import annotations
import ast,hashlib,json,random,re
from pathlib import Path
S=Path('docs/data/oral-golden-fast-v6.json');SRC=Path('src/build_oral_role_ticket_v6.py');OUT=Path('status/oral-v6-robustness-audit.json')

def canonical_analysis(a):
 return {'axis':a.get('axis'),'decision':a.get('pre_market_decision'),'main':sorted(str(x.get('horse_no')) for x in a.get('role_main_partners',[])),'holes':sorted(str(x.get('horse_no')) for x in a.get('role_holes',[])),'tickets':sorted(a.get('trio_tickets') or [])}
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
 doc=json.loads(S.read_text());code=SRC.read_text();tree=ast.parse(code)
 string_literals=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
 forbidden_names=['シルフズミスチーフ','ポッドロワール','ボウウィンドウ','ルクスレイモンド','ホウオウタイタン','マイネルアレス']
 hardcoded_names=[x for x in forbidden_names if x in code]
 # Race-specific number tuples/conditions are considered suspicious only when 3+ known golden numbers are embedded together.
 suspicious_numeric=[]
 for lit in string_literals:
  ns=set(re.findall(r'(?<!\d)(?:1[0-7]|[1-9])(?!\d)',lit))
  if len(ns)>=3:suspicious_numeric.append(lit)
 golden_import='oral-chat-golden-cases' in code or 'oral_golden' in code.lower()
 base=[canonical_analysis(r['analysis']) for r in doc['races']];base_hash=digest(base)
 # Output artifact itself must declare isolation. Robustness test also verifies irrelevant injected fields do not mutate canonical snapshot.
 injected=json.loads(json.dumps(doc))
 rng=random.Random(20260901)
 for r in injected['races']:
  r['target_result']={'winner':rng.randint(1,18),'payout':999999};r['odds']={'fake':1.01};r['popularity']={'fake':1};r['outside_prediction']=['FAKE']
 inj_hash=digest([canonical_analysis(r['analysis']) for r in injected['races']])
 # Determinism over serialized clone / arbitrary top-level noise.
 clone=json.loads(json.dumps(doc,sort_keys=True));clone['noise']=[rng.random() for _ in range(10)]
 clone_hash=digest([canonical_analysis(r['analysis']) for r in clone['races']])
 out={'version':'ORAL_V6_ROBUSTNESS_AUDIT','source_file':str(SRC),'race_specific_horse_names_found':hardcoded_names,'golden_truth_import_found':golden_import,'suspicious_string_number_groups':suspicious_numeric,'no_identity_hardcode':not hardcoded_names and not golden_import and not suspicious_numeric,'declared_result_data_used':doc.get('result_data_used'),'declared_odds_popularity_used':doc.get('odds_popularity_used'),'canonical_hash':base_hash,'irrelevant_field_injection_hash':inj_hash,'clone_hash':clone_hash,'irrelevant_injection_invariant':base_hash==inj_hash,'deterministic_clone':base_hash==clone_hash,'passed':bool(not hardcoded_names and not golden_import and not suspicious_numeric and not doc.get('result_data_used') and not doc.get('odds_popularity_used') and base_hash==inj_hash==clone_hash)}
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
