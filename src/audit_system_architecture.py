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
 horse_writers=('post-jra-meeting-update.yml','register-upcoming-new-horses.yml','horse-master-maintenance.yml','repair-horse-master-integrity.yml')
 checks['horse_writer_serialized']=all(
   'group: horse-data-writes' in text(x)
   and 'cancel-in-progress: false' in text(x)
   for x in horse_writers
 )
 checks['market_independent_group']='group: market-status-writes' in text('jra-market-timing.yml')
 checks['dictionary_independent_group']='group: site-dictionary-writes' in text('build-word-dictionary.yml')
 checks['pages_independent_group']='group: pages' in text('deploy-management-erp.yml')
 deploy=text('deploy-management-erp.yml')
 checks['producer_to_pages_redeploy_connected']=(
   'workflow_run:' in deploy
   and 'Race-week pure prediction seal' in deploy
   and 'JRA market timing monitor' in deploy
   and 'Post JRA meeting data update' in deploy
   and 'Register upcoming JRA debut horses and race-week details' in deploy
   and 'Build word dictionary and global links' in deploy
   and "ref: main" in deploy
 )
 checks['validation_read_only']='contents: read' in text('validate-jra-model.yml') and 'contents: write' not in text('validate-jra-model.yml')
 checks['repair_not_scheduled']=('schedule:' not in text('repair-horse-master-integrity.yml') and 'push:' not in text('repair-horse-master-integrity.yml') and 'workflow_dispatch:' in text('repair-horse-master-integrity.yml'))
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
 ui=cfg.get('ui_constitution') or {}
 checks['ui_constitution_locked']=(
   ui.get('status')=='USER_LOCKED'
   and ui.get('priority')=='CONSTITUTIONAL'
   and ui.get('explicit_user_override_required') is True
   and 'display format must never be changed' in str(ui.get('rule',''))
 )
 checks['replay_canonical_format_pinned']=ui.get('canonical_replay_format_ref')=='src/build_replay_page.py'
 checks['replay_generated_not_patched']=(
   'python src/build_replay_page.py' in text('deploy-management-erp.yml')
   and ui.get('direct_page_edit_policy')=='PROHIBITED_FOR_NORMAL_FIXES'
 )
 checks['replay_hidden_state_guard']=(
   '[hidden]{display:none!important}' in Path('src/build_replay_page.py').read_text(encoding='utf-8')
   and "assert '[hidden]{display:none!important}' in p" in text('deploy-management-erp.yml')
 )
 checks['prediction_seal_single_owner']=(
   'build_live_sealed_predictions.py' in text('race-week-prediction-seal.yml')
   and 'build_live_sealed_predictions.py' not in text('register-upcoming-new-horses.yml')
 )
 seal=text('race-week-prediction-seal.yml')
 checks['runner_refresh_to_prediction_seal_connected']=(
   'workflow_run:' in seal
   and 'Register upcoming JRA debut horses and race-week details' in seal
   and "ref: main" in seal
 )
 checks['management_erp_single_owner']=(
   'build_management_erp.py' in text('race-week-prediction-seal.yml')
   and 'build_management_erp.py' not in text('post-jra-meeting-update.yml')
 )
 checks['post_archive_date_generic']=(
   "TARGET_DATE: '2026-09-05'" not in post
   and 'COMPLETE_DATES' in post
   and 'publish_archive_results.py' in post
 )
 checks['immutable_prediction_archive_guard']=(
   'hashlib.sha256' in post
   and 'immutable prediction archive changed' in post
   and 'prediction-archive-' in post
 )
 expire=Path('src/expire_weekly_runner_details.py').read_text(encoding='utf-8') if Path('src/expire_weekly_runner_details.py').exists() else ''
 checks['race_week_rollover_preserves_detail']=(
   'weekly_runner_archive' in expire
   and 'archive count mismatch' in expire
   and 'weekly_runner_archive/*.json' in post
 )
 runner_collector=Path('src/collect_upcoming_runner_details.py').read_text(encoding='utf-8') if Path('src/collect_upcoming_runner_details.py').exists() else ''
 pre_feature_builder=Path('src/build_race_week_pre_race_features.py').read_text(encoding='utf-8') if Path('src/build_race_week_pre_race_features.py').exists() else ''
 register_week=text('register-upcoming-new-horses.yml')
 checks['race_week_refresh_history_preserved']=(
   'weekly_runner_history' in runner_collector
   and 'archive_existing_weekly' in runner_collector
   and 'pre_race_feature_history' in pre_feature_builder
   and 'archive_existing_features' in pre_feature_builder
   and 'weekly_runner_history' in register_week
   and 'pre_race_feature_history' in register_week
 )
 checks['live_seal_history_preserved']=(
   'prediction-seal-history' in builder
   and '_archive_seal_payload' in builder
   and 'prediction-seal-history' in seal
 )
 checks['score_history_preserved']=(
   'prediction-score-history' in scorer
   and 'score history verification failed' in scorer
   and 'prediction-score-history' in post
 )
 checks['pdca_history_preserved']=(
   'pdca-history' in pdca
   and 'pdca history verification failed' in pdca
   and 'pdca-history' in post
 )
 erp_builder=Path('src/build_management_erp.py').read_text(encoding='utf-8') if Path('src/build_management_erp.py').exists() else ''
 public_app=Path('docs/app/race-select-current.js').read_text(encoding='utf-8') if Path('docs/app/race-select-current.js').exists() else ''
 replay_builder=Path('src/build_replay_page.py').read_text(encoding='utf-8') if Path('src/build_replay_page.py').exists() else ''
 checks['jst_date_rollover_display_guard']=(
   'actual_today=datetime.now(JST).date().isoformat()' in erp_builder
   and 'display_date' in erp_builder
   and 'preferredDate' in public_app
   and "timeZone:'Asia/Tokyo'" in public_app
   and 'latest_completed_date=max(canonical_dates)' in replay_builder
 )
 checks['active_runtime_has_no_fixed_weekend_date']=all(
   token not in (builder+erp_builder+public_app+post+seal)
   for token in ('2026-09-05','2026-09-06')
 )
 repair=cfg.get('repair_constitution') or {}
 checks['root_cause_repair_constitution_locked']=(
   repair.get('status')=='USER_LOCKED'
   and repair.get('priority')=='CONSTITUTIONAL'
   and 'ROOT_CAUSE_FIRST' in (repair.get('principles') or [])
   and 'ADDITIVE_PATCH_LAST_RESORT' in (repair.get('principles') or [])
   and 'NO_DUPLICATE_IMPLEMENTATIONS' in (repair.get('principles') or [])
 )

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
