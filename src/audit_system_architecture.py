#!/usr/bin/env python3
from __future__ import annotations
import json
import re
from pathlib import Path

CFG=Path('config/system_architecture.json')
WF=Path('.github/workflows')
OUT=Path('status/system_architecture.json')

REQUIRED={
 'post-jra-meeting-update.yml','register-upcoming-new-horses.yml','horse-master-maintenance.yml',
 'race-week-prediction-seal.yml','jra-market-timing.yml','validate-jra-model.yml',
 'audit-oral-v6-certification.yml','build-word-dictionary.yml','deploy-management-erp.yml',
 'repair-horse-master-integrity.yml','system-architecture-audit.yml'
}

def text(name):
 p=WF/name
 return p.read_text(encoding='utf-8') if p.exists() else ''

def main():
 cfg=json.loads(CFG.read_text(encoding='utf-8'))
 active={p.name for p in WF.glob('*.yml')}|{p.name for p in WF.glob('*.yaml')}
 missing=sorted(REQUIRED-active);unexpected=sorted(active-REQUIRED)
 post=text('post-jra-meeting-update.yml')
 checks={}
 checks['canonical_flow_complete']=cfg.get('production_flow')==[
   'JRA_OFFICIAL_DATA_INGEST','HORSE_MASTER_UPDATE','RACE_WEEK_EXPANSION','PURE_PREDICTION','PREDICTION_SEAL','MARKET_EV_GATE','FINAL_TICKETS','RESULT_INGEST','SCORING','PDCA','HORSE_MASTER_RESULT_MERGE']
 checks['horse_writer_serialized']=all('group: horse-data-writes' in text(x) for x in ('post-jra-meeting-update.yml','register-upcoming-new-horses.yml','horse-master-maintenance.yml'))
 checks['market_independent_group']='group: market-status-writes' in text('jra-market-timing.yml')
 checks['dictionary_independent_group']='group: site-dictionary-writes' in text('build-word-dictionary.yml')
 checks['pages_independent_group']='group: pages' in text('deploy-management-erp.yml')
 checks['validation_read_only']='contents: read' in text('validate-jra-model.yml') and 'contents: write' not in text('validate-jra-model.yml')
 checks['repair_not_scheduled']='schedule:' not in text('repair-horse-master-integrity.yml')
 seal=text('race-week-prediction-seal.yml')
 builder=Path('src/build_live_sealed_predictions.py').read_text(encoding='utf-8') if Path('src/build_live_sealed_predictions.py').exists() else ''
 market=Path('src/market_timing_gate.py').read_text(encoding='utf-8') if Path('src/market_timing_gate.py').exists() else ''
 scorer=Path('src/score_live_sealed_predictions.py').read_text(encoding='utf-8') if Path('src/score_live_sealed_predictions.py').exists() else ''
 pdca=Path('src/build_live_pdca.py').read_text(encoding='utf-8') if Path('src/build_live_pdca.py').exists() else ''
 replay=Path('docs/replay/index.html').read_text(encoding='utf-8') if Path('docs/replay/index.html').exists() else ''
 checks['live_prediction_seal_exists']=bool(seal and builder)
 checks['live_seal_market_firewall']=all(x in builder for x in ("'odds_popularity_used':False","'results_used':False","FORBIDDEN_KEYS"))
 checks['market_reads_only_sealed_races']='live_predictions_sealed.json' in market and "'prediction_sealed':True" in market
 checks['market_final_ticket_honesty']='MARKET_DATA_PENDING' in market and 'never fabricate odds or EV' in market
 checks['market_does_not_run_prediction_engine']='oral_operational_layer' not in text('jra-market-timing.yml') and 'analyze_race' not in text('jra-market-timing.yml')
 checks['post_result_scoring_connected']=bool(scorer) and 'score_live_sealed_predictions.py' in post and 'sealed_predictions_immutable' in scorer
 checks['pdca_connected_and_non_mutating']=bool(pdca) and 'build_live_pdca.py' in post and 'does not automatically rewrite the certified production model' in pdca
 checks['result_score_before_horse_merge']=post.find('score_live_sealed_predictions.py') < post.find('merge_latest_results_into_catalog.py')
 checks['validation_not_in_production_flow']='validate-jra-model.yml' not in post and 'validate-jra-model.yml' not in text('race-week-prediction-seal.yml')
 checks['replay_feature_contract']=all(x in replay for x in ('過去レースのAI予測','data-month="2026-08"','data-month="2026-07"','class="locked"','<details class="result','結果を見る'))
 policy=cfg.get('active_workflow_script_policy',{})
 actual_refs={
   name:sorted(set(re.findall(r'src/([A-Za-z0-9_.-]+\.py)',text(name))))
   for name in sorted(active)
 }
 expected_refs={name:sorted(policy.get(name,[])) for name in sorted(active)}
 script_policy_mismatches={
   name:{'expected':expected_refs[name],'actual':actual_refs[name]}
   for name in sorted(active) if expected_refs[name]!=actual_refs[name]
 }
 checks['active_workflow_scripts_explicitly_allowlisted']=not script_policy_mismatches and set(policy)==REQUIRED
 checks['active_workflow_script_files_exist']=all(
   (Path('src')/script).is_file() for scripts in actual_refs.values() for script in scripts
 )
 blockers=[]
 if missing:blockers.append('required active workflows missing')
 if unexpected:blockers.append('unexpected active workflows remain; archive or explicitly authorize them')
 blockers += [f'check failed: {k}' for k,v in checks.items() if not v]
 status='PASS' if not blockers else 'BLOCKED'
 report={'schema_version':1,'status':status,'active_workflow_count':len(active),'required_workflow_count':len(REQUIRED),'active_workflows':sorted(active),'required_workflows':sorted(REQUIRED),'missing_required':missing,'unexpected_active_workflows':unexpected,'checks':checks,'active_workflow_script_refs':actual_refs,'script_policy_mismatches':script_policy_mismatches,'blockers':blockers,'independent_subsystems':cfg.get('independent_subsystems'),'production_flow':cfg.get('production_flow'),'known_external_boundary':'Real market odds/EV acquisition is an external-data boundary. Until actual market data is connected, final tickets remain MARKET_DATA_PENDING rather than fabricated.','note':'PASS means orchestration shape, handoffs, subsystem boundaries, and protected replay-site features are intact. It does not claim model predictive accuracy or live odds availability.'}
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))
 if status!='PASS':raise SystemExit(2)
if __name__=='__main__':main()
