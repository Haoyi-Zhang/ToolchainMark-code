"""Recompute evidence predicates. A green report is not a scientific guarantee."""
from __future__ import annotations
import csv,hashlib,json,re
from collections import Counter
from pathlib import Path
from .catalog import load_mutants,load_relations
from .evidence_catalog import load as load_evidence

def read(path:Path):
    with path.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def sha(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()
def recheck(artifact:Path)->dict:
    project=artifact.parent;paper=project/'paper';raw=artifact/'results/admission-study';d=raw/'derived'
    rows=read(raw/'matrix.csv');rerun=read(raw/'rerun.csv');summary=json.loads((d/'summary.json').read_text());checks={}
    ids=lambda r:(r['host'],r['carrier'],r['defect_id'],r['relation_id'])
    first={ids(r):r for r in rows};second={ids(r):r for r in rerun}
    checks['planned_rows_18900']=len(rows)==18900
    checks['scientific_keys_unique']=len(first)==len(rows)
    checks['rerun_keys_identical']=set(first)==set(second)
    fields=[k for k in rows[0] if k!='duration_seconds']
    checks['all_non_timing_fields_recomputed_equal']=all(all(a[k]==second[key][k] for k in fields) for key,a in first.items())
    checks['actual_field_comparisons_207900']=len(fields)*len(rows)==207900
    checks['positive_durations_both_runs']=all(float(r['duration_seconds'])>0 for r in rows+rerun)
    hosts=sorted((artifact/'hosts').glob('H*.c'));hosthash={p.name:sha(p) for p in hosts}
    checks['eighteen_distinct_subjects']=len(hosts)==len(set(hosthash.values()))==18
    checks['row_subject_identity_matches_source']=all(hosthash[r['host']]==r['host_sha256'] for r in rows)
    checks['three_carriers']={r['carrier'] for r in rows}=={'string','symbol','section'}
    checks['twenty_four_operators']=len(load_mutants())==24
    checks['fourteen_relations']=len(load_relations())==14
    checks['complete_evidence_catalog']=len(load_evidence())==14
    checks['verdict_alphabet_exact']={r['verdict'] for r in rows}=={'SATISFIED','INCONSISTENT','INADMISSIBLE'}
    clean=[r for r in rows if r['defect_id']=='CLEAN'];fault=[r for r in rows if r['defect_id']!='CLEAN']
    checks['clean_756_satisfied']=len(clean)==756 and all(r['verdict']=='SATISFIED' for r in clean)
    checks['fault_rows_18144']=len(fault)==18144
    counts=Counter(r['verdict'] for r in fault)
    checks['three_way_fault_partition']=counts=={'SATISFIED':12870,'INCONSISTENT':4266,'INADMISSIBLE':1008}
    checks['only_inconsistent_fault_rows_expose']=all((r['exposed']=='True')==(r['verdict']=='INCONSISTENT' and r['defect_id']!='CLEAN') for r in rows)
    checks['inconsistent_cases_have_satisfied_admission_facts']=all(all(v is True for v in json.loads(r['admission_json']).values()) for r in rows if r['verdict']=='INCONSISTENT')
    checks['inadmissible_cases_have_reason']=all(bool(r['reason']) for r in rows if r['verdict']=='INADMISSIBLE')
    units={};
    for r in fault:units.setdefault((r['host'],r['carrier'],r['defect_id']),[]).append(r)
    checks['planned_units_1296']=len(units)==1296
    exposed={k for k,v in units.items() if any(r['exposed']=='True' for r in v)}
    checks['exposed_units_1242']=len(exposed)==1242
    checks['all_units_have_an_admitted_case']=all(any(r['verdict']!='INADMISSIBLE' for r in v) for v in units.values())
    checks['only_noop_removal_operator_unexposed']={k[2] for k in units if k not in exposed}=={'M15'}
    checks['design_exposed_69']=sum(k[0]==hosts[0].name for k in exposed)==69
    reasons=Counter(r['reason'] for r in rows if r['verdict']=='INADMISSIBLE')
    checks['admission_reason_partition']=reasons=={'source_payload_recovered':540,'requested_branches_executed':270,'source_carrier_valid':108,'carrier_removed':54,'integrity_corruption_established':36}
    checks['source_failure_is_not_relocation_kill']=all(r['exposed']=='False' for r in rows if r['relation_id']=='MR08' and r['reason']=='source_payload_recovered')
    checks['noop_removal_is_inadmissible']=all(r['verdict']=='INADMISSIBLE' for r in rows if r['relation_id']=='MR09' and r['defect_id']=='M15')
    checks['verified_integrity_bypass_remains_inconsistent']=all(r['verdict']=='INCONSISTENT' for r in rows if r['relation_id']=='MR10' and r['defect_id']=='M16')
    suites=read(d/'suites.csv');checks['fixed_design_suites']=[int(r['design_exposed']) for r in suites]==[21,27,33,69]
    checks['fixed_expanded_suites']=[int(r['expanded_exposed']) for r in suites]==[378,486,594,1242]
    checks['summary_bound_to_new_matrix']=summary['matrix_sha256']==sha(raw/'matrix.csv')
    checks['summary_outcomes_match_rows']=summary['defect_verdicts']==dict(counts)
    checks['new_rerun_summary_matches_actual']=summary['rerun']['differences']==0 and summary['rerun']['field_comparisons']==207900
    checks['new_run_hashes_differ_only_where_expected']=sha(raw/'matrix.csv')!=sha(raw/'rerun.csv')
    classes=read(d/'class_holdout.csv');ops=read(d/'operator_holdout.csv');carriers=read(d/'carrier_holdout.csv')
    checks['class_holdout_denominator_12']=len(classes)==12
    checks['five_zero_sensitivity_classes']=sum(float(r['sensitivity'])==0 for r in classes)==5
    checks['operator_holdout_denominator_24']=len(ops)==24
    checks['eight_zero_sensitivity_operators']=sum(float(r['sensitivity'])==0 for r in ops)==8
    checks['three_carrier_holdouts']=len(carriers)==3 and all(int(r['exposed'])==414 and int(r['test_units'])==432 for r in carriers)
    checks['bootstrap_10000']=summary['bootstrap']['replicates']==10000
    checks['bootstrap_1884_perfect']=summary['bootstrap']['perfect']==1884
    checks['bootstrap_minimum_60_percent']=summary['bootstrap']['minimum']==.6
    checks['context_replay_17136']=summary['subject_replay']['matches']==summary['subject_replay']['rows']==17136
    checks['context_killsets_1224']=summary['subject_replay']['killsets_equal']==summary['subject_replay']['killsets']==1224
    trans=read(d/'legacy_transitions.csv');transmap={(r['legacy'],r['evidence_gated']):int(r['rows']) for r in trans}
    checks['legacy_failures_invalidated_468']=transmap.get(('FAIL','INADMISSIBLE'))==468
    checks['legacy_passes_invalidated_540']=transmap.get(('PASS','INADMISSIBLE'))==540
    checks['typed_predicate_additions_270']=transmap.get(('PASS','INCONSISTENT'))==270
    checks['legacy_matrix_preserved_distinct']=(artifact/'results/raw/robustness_matrix.csv').is_file() and sha(raw/'matrix.csv')!=sha(artifact/'results/raw/robustness_matrix.csv')
    checks['old_audit_claims_retained_as_history']=(artifact/'results/protocol-history/imported-audits/README.md').is_file()
    ref=json.loads((paper/'reference_verification_audit.json').read_text());shape=json.loads((paper/'citation_shape_audit.json').read_text())
    checks['seventy_three_bibliographic_records']=ref['record_count']==73
    checks['all_73_locally_cited']=shape['unique_citation_keys']==73 and not shape['uncited_bibliography_keys'] and not shape['missing_bibliography_keys']
    checks['single_key_citations']=shape['multi_key_commands']==0 and shape['adjacent_citation_piles']==0
    checks['local_reference_consistency']=shape['structural_verdict']=='PASS'
    checks['no_automatic_full_text_certification']=ref['semantic_verdict']=='PARTIAL_EXTERNAL_REVIEW_NOT_FULL_TEXT_CERTIFICATION'
    plan=json.loads((paper/'author_plan.json').read_text());auth=(paper/'authors.tex').read_text();main=(paper/'main.tex').read_text();supp=(paper/'online-supplement.tex').read_text()
    checks['six_planned_slots_three_blank']=plan['intended_slots']==6 and plan['named_authors']==3 and plan['blank_reserved_slots']==[4,5,6]
    checks['new_named_order_exact']=[a['name'] for a in plan['authors']]==['Haoyi Zhang','Huaijin Ran','Xunzhu Tang']
    checks['only_three_real_author_declarations']=auth.count('\\author{')==3
    checks['tang_luxembourg_correct']='University of Luxembourg' in auth and 'realdanieltang@gmail.com' in auth
    checks['no_invented_tang_orcid']=plan['authors'][2]['orcid'] is None
    checks['no_invented_tang_city']=plan['authors'][2]['city'] is None
    checks['both_papers_share_authors']='\\input{authors}' in main and '\\input{authors}' in supp
    checks['blank_slots_not_fake_names']='Author Placeholder' not in auth
    checks['new_results_bound_into_main']='\\input{generated/admission-results}' in main
    checks['no_inline_appendix']='\\appendix' not in main
    checks['seven_native_scientific_figures']=main.count('\\begin{figure}')==7
    checks['formal_algorithm_retained']='\\begin{algorithm}' in main
    checks['submission_derivative_only_class_change']=(paper/'submission-manuscript.tex').read_text()==main.replace('\\documentclass[acmsmall,review,screen]{acmart}','\\documentclass[manuscript,review,screen]{acmart}',1)
    checks['claim_evidence_paths_exist']=all((artifact/r['primary_source']).is_file() and (not r['derived_or_checker'] or (artifact/r['derived_or_checker']).is_file()) for r in read(artifact/'claim_evidence_ledger.csv'))
    checks['retained_external_evidence_not_relabelled']=(artifact/'results/external-transfer/summary.json').is_file()
    layout=json.loads((paper/'page_fit_audit.json').read_text())
    visual=json.loads((paper/'visual_qa.json').read_text())
    checks['page_audit_matches_current_pdf']=layout['pdf_sha256']==sha(paper/'main.pdf') and layout['within_one_ordinary_line'] and layout['references_start_page']==45
    checks['visual_audit_matches_all_current_pdfs']=all(data['sha256']==sha(paper/(name+'.pdf')) for name,data in visual['pdfs'].items())
    checks['incomplete_author_roster_explicitly_marked']=plan['status']=='INCOMPLETE_AUTHOR_ROSTER_DRAFT_ONLY'
    result={'schema_version':'evidence-gated-2026-09-23','checks':checks,'check_count':len(checks),'passed':sum(checks.values()),'verdict':'PASS' if all(checks.values()) else 'FAIL','scope':'Current executable evidence and documented limits; not a proof of field effectiveness, reference semantics, or submission eligibility.'}
    (artifact/'audit/recheck_report.json').write_text(json.dumps(result,indent=2)+'\n')
    if result['verdict']!='PASS':raise RuntimeError('Evidence checks failed: '+', '.join(k for k,v in checks.items() if not v))
    return result
