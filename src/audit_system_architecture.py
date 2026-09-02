#!/usr/bin/env python3
from __future__ import annotations
import json
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
 checks['live_prediction_seal_exists']=bool(seal and builder)
 checks['live_seal_market_firewall']=all(x in builder for x in ("'odds_popularity_used':False","'results_used':False","FORBIDDEN_KEYS"))
 checks['market_reads_only_sealed_races']='live_predictions_sealed.json' in market and "'prediction_sealed':True" in market
 checks['market_final_ticket_honesty']='MARKET_DATA_PENDING' in market and 'never fabricate odds or EV' in market
 checks['market_does_not_run_prediction_engine']='oral_operational_layer' not in text('jra-market-timing.yml') and 'analyze_race' not in text('jra-market-timing.yml')
 checks['validation_not_in_production_flow']='validate-jra-model.yml' not in text('post-jra-meeting-update.yml') and 'validate-jra-model.yml' not in text('race-week-prediction-seal.yml')
 blockers=[]
 if missing:blockers.append('required active workflows missing')
 if unexpected:blockers.append('unexpected active workflows remain; archive or explicitly authorize them')
 blockers += [f'check failed: {k}' for k,v in checks.items() if not v]
 status='PASS' if not blockers else 'BLOCKED'
 report={'schema_version':1,'status':status,'active_workflow_count':len(active),'required_workflow_count':len(REQUIRED),'active_workflows':sorted(active),'required_workflows':sorted(REQUIRED),'missing_required':missing,'unexpected_active_workflows':unexpected,'checks':checks,'blockers':blockers,'independent_subsystems':cfg.get('independent_subsystems'),'production_flow':cfg.get('production_flow'),'known_external_boundary':'Real market odds/EV acquisition is an external-data boundary. Until actual market data is connected, final tickets remain MARKET_DATA_PENDING rather than fabricated.','note':'PASS means orchestration shape, handoffs and subsystem boundaries are clean. It does not claim model predictive accuracy or live odds availability.'}
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))
 if status!='PASS':raise SystemExit(2)
if __name__=='__main__':main()
