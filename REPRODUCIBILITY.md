# Reproduction and interpretation

The current matrices are results/admission-study/matrix.csv and rerun.csv. Their unit key is(subject, carrier, operator, relation). Eleven non-timing fields are compared; durations must remain positive but are not expected to be equal. The executable relation evidence interface is specs/evidence_relations.json.

Run scripts/verify.sh for local tests and deterministic rederivation. Run scripts/run_full.sh with a NEW output directory and a worker count for two complete executions. Never replace the frozen raw rows with new outcomes. Record changed compiler and library versions and compare verdicts, evidence and timing separately.

All 73 references are locally cited. Current source-record receipts are stored in paper/evidence/reference_review_20260923.json. Their scope varies from publisher abstracts to scholarly-index records; no automatic full-text support certificate is issued. The search-engine page range 264-284 is corroborated by DBLP; the conflicting institutional range is documented rather than silently propagated. The seven-author path-based-watermark conference record is corroborated by DBLP; abbreviated records on older pages are not substituted.

Historical source code and results are retained so that the change from Boolean failure to evidence-gated attribution can be audited. Historical passes/failures cannot be read as the current three-valued verdict. Newly derived class and operator holdouts and bootstrap results are conditional on the constructed mechanism family.

Verification is not a substitute for manual author approval, venue-policy review, an independent observer, or an external-team replication.
