#!/usr/bin/env python3
from __future__ import annotations
import csv,json,hashlib,inspect,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src';sys.path.insert(0,str(SRC))
checks={}

def load(path):return json.loads((ROOT/path).read_text())
# Executable specification and result cardinalities.
mrs=load('specs/mrspec.json');rels=mrs.get('relations',mrs if isinstance(mrs,list) else [])
mut=load('specs/mutants.json');muts=mut.get('mutants',mut if isinstance(mut,list) else [])
checks['14_relations']=len(rels)==14
checks['24_fault_operators']=len(muts)==24
# Admission accounting.
den=load('results/admission_denominators.json')
checks['configured_rows_18900']=den['configured_rows']==18900
checks['clean_rows_756']=den['clean_rows']==756
checks['fault_active_rows_17172']=den['fault_active_rows']==17172
checks['stage_isolation_rows_972_all_satisfied']=den['stage_isolation_rows']==972 and den['stage_isolation_satisfied_rows']==972 and den['stage_isolation_inconsistent_rows']==0
checks['tri_verdict_replay_includes_inadmissible']='Do not drop inadmissible' in den['tri_valued_context_replay_rule']
# Targeted current-handler replay.
rep=load('results/targeted-current-handler-replay.summary.json')
checks['targeted_replay_complete']=rep['selected_tasks']==rep['completed_rows'] and rep['completed_rows']>0
checks['targeted_replay_zero_verdict_changes']=rep['verdict_changes']==0
checks['mr13_current_trace_complete']=rep['mr13_rows']>0 and rep['mr13_rows_with_action_trace']==rep['mr13_rows'] and rep['mr13_rows_with_command_trace']==rep['mr13_rows']
checks['guard_replay_972_satisfied']=rep['guard_rows']==972 and rep['guard_satisfied_rows']==972
# Protocol alignment.
pa=load('audit/protocol_alignment_audit.json')
checks['protocol_alignment_audit']=pa['verdict']=='PASS' and not pa['failed']
# External transformations.
et=load('results/external_transformations_observation_scopes.summary.json')
checks['external_transform_partition']=et['rows']==378 and et['preservation_verified_rows']==288 and et['rejection_only_rows']==72 and et['incompatible_rows']==18
with (ROOT/'results/external_transformations_observation_scopes.csv').open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
checks['rejection_only_host_unobserved']=all(r['host_execution_observed']=='false' and r['host_output_equal']=='UNOBSERVED' for r in rows if r['obligation_scope']=='REJECTION_ONLY')
checks['preservation_host_observed']=sum(r['obligation_scope']=='PRESERVATION_VERIFIED' and r['host_execution_observed']=='true' for r in rows)==288
# External source-pair study.
es=load('results/external-source-pair-current/summary.json')
checks['external_source_pair_120']=es['rows']==120
checks['external_source_pair_20_10']=es['compatibility_satisfied']==20 and es['compatibility_inconsistent']==10 and es['compatibility_inadmissible']==0
checks['missing_or_nonzero_never_success']=es['missing_output_or_nonzero_counted_as_success']==0
# Legacy comparison scope is accurately limited.
comparison=[]
for p in ROOT.rglob('*.json'):
 try:d=json.loads(p.read_text())
 except Exception:continue
 if d.get('retained_field_comparisons')==207900:comparison.append(d)
checks['legacy_207900_limited_to_11_fields']=bool(comparison) and all(d.get('retained_field_count')==11 and d.get('complete_trace_replay_claimed') is False for d in comparison)
# Static core integration checks.
code='\n'.join(p.read_text(errors='ignore') for p in SRC.glob('*.py'))
checks['section_observer_integrated']='observe_elf_section' in code and 'ToolObservationError' in code and '--dump-section' in code
checks['first_valid_parser_integrated']='first_valid_candidate' in code and '_candidate_' in code
checks['trace_fields_integrated']=all(x in code for x in ('request_trace_json','action_trace_json','command_trace_json','artifact_identity_trace_json','fault_activation_mode'))
# Raw matrices are immutable scientific inputs; sanity-check the archived matrix and rerun reports.
mat=next((p for p in (ROOT/'results/raw').glob('*robust*matrix*.csv')),None)
if mat is None: mat=next((p for p in (ROOT/'results/raw').glob('*replication*matrix*.csv')),None)
if mat:
 with mat.open(newline='',encoding='utf-8') as f: n=sum(1 for _ in f)-1
 checks['archived_complete_matrix_18900']=n==18900
else:checks['archived_complete_matrix_18900']=False
result={'schema_version':'1.0','artifact_root':str(ROOT),'check_count':len(checks),'passed':sum(checks.values()),'failed':[k for k,v in checks.items() if not v],'checks':checks,'verdict':'PASS' if all(checks.values()) else 'FAIL'}
(ROOT/'audit/science_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
