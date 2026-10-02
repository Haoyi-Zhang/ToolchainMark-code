#!/usr/bin/env python3
"""Bind current manuscript claims to evidence; never synthesize verification receipts."""
from pathlib import Path
import csv,json,hashlib,re
R=Path(__file__).resolve().parents[2];A=R/'artifact';P=R/'paper'
s=json.loads((A/'results/admission-study/derived/summary.json').read_text())
claims=[
('C-GATE','A failed admission fact or infrastructure exception cannot expose a fault unit.','Admission rule, gate invariant, and evidence-gated executor','formal and executable','src/tosem02/admission.py','tests/test_admission.py','Conditional on correct gate observations; the carrier parser is shared.'),
('C-SEPARABLE','A relation deletion removes detection power only under the stated observational-separability premise.','Direct contract-clause coverage: loss under a separable clause violation','proof','../paper/main.tex','','Direct labels alone do not prove absence of a logical implication.'),
('C-CLN',f"All {s['clean_rows']} clean cases are satisfied.",'Section 6','new execution','results/admission-study/matrix.csv','results/admission-study/derived/summary.json','Only the recorded context and declared operations are covered.'),
('C-FAULT',f"{s['defect_verdicts']['INCONSISTENT']} fault rows are inconsistent and {s['defect_verdicts']['INADMISSIBLE']} are inadmissible.",'Section 6','new execution','results/admission-study/matrix.csv','results/admission-study/derived/summary.json','Rows are correlated repeated relation executions, not independent field defects.'),
('C-UNIT',f"{s['units_exposed']}/{s['unit_count']} planned fault units exposed; {s['design_exposed']}/72 on design subject.",'Section 6','new execution','results/admission-study/matrix.csv','results/admission-study/derived/unit_outcomes.csv','The skipped-removal operator is not exposed as an extractor violation.'),
('C-SUITE','Fixed suites expose 21, 27, 33, and 69 of the same 72 design units.','Section 6','paired finite enumeration','results/admission-study/matrix.csv','results/admission-study/derived/suites.csv','No population p-value interpretation.'),
('C-TRANS','468 prior failures and 540 prior passes become inadmissible; 270 prior passes become typed-predicate inconsistencies.','Section 6','paired protocol audit','results/raw/robustness_matrix.csv','results/admission-study/derived/legacy_transitions.csv','The correction changes both gates and typed rejection predicates.'),
('C-REPLAY','17136/17136 subject verdict pairs and 1224/1224 unit kill sets replay.','Section 6','context replay','results/admission-study/matrix.csv','results/admission-study/derived/summary.json','Known mechanisms only; not independent discoveries.'),
('C-HOLDOUT',f"{len(s['zero_sensitivity_classes'])}/12 classes and {len(s['zero_sensitivity_operators'])}/24 operators have zero holdout sensitivity.",'Section 6','adverse analysis','results/admission-study/matrix.csv','results/admission-study/derived/class_holdout.csv','Same constructed mechanism family.'),
('C-BOOT',f"10000 resamples; {s['bootstrap']['perfect']} perfect; minimum {s['bootstrap']['minimum']:.1%}.",'Section 6','conditional resampling','results/admission-study/matrix.csv','results/admission-study/derived/bootstrap_summary.json','Class-stratified selection stability, not field uncertainty.'),
('C-RERUN','Two new complete runs compare every non-timing field by scientific key.','Section 6','new internal repeatability','results/admission-study/rerun.csv','results/admission-study/derived/rerun_comparison.json','Same environment; not external-team replication.'),
('C-EXT','Retained source-pair comparisons show 10 output discrepancies despite 30 successful termination comparisons.','Section 6','inherited external-source evidence','results/external-transfer/execution_rows.csv','results/external-transfer/summary.json','Conditional source-pair equivalence; no automated recovery or confirmed historical defect.'),
('C-UTIL','Retained GNU/LLVM study satisfies 360/378 operation obligations.','Section 6','inherited utility study','results/raw/adverse_transformations.csv','results/raw/adverse_transformations.summary.json','Not a new utility rerun in the current correction.'),
]
fields=['claim_id','claim_text','paper_location','evidence_type','primary_source','derived_or_checker','limitations','maturity_state']
with (A/'claim_evidence_ledger.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fields);w.writeheader()
 for cid,text,loc,kind,raw,der,lim in claims:w.writerow(dict(zip(fields,[cid,text,loc,kind,raw,der,lim,'INTERNAL_EXECUTION' if kind in ['new execution','new internal repeatability'] else kind.upper().replace(' ','_')])))
res=[]
for cid,text,loc,kind,raw,der,lim in claims:
 path=A/raw
 res.append({'result_id':cid,'paper_location':loc,'value':text,'raw_output':raw,'derived_output':der,'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'scope':kind,'limitations':lim})
with (A/'results_manifest.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,res[0].keys());w.writeheader();w.writerows(res)
print('current claims',len(claims))
