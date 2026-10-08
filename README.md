# Contract-aware watermark validation artifact

## Current protocol and evidence

The current implementation is the evidence-gated protocol. It distinguishes SATISFIED, INCONSISTENT and INADMISSIBLE. Only an admitted inconsistency exposes a fault unit. This corrects the supplied Boolean runner, which conflated relation failure with invalid construction. The original source operators and historical matrices remain available and are not pooled with current estimands.

The repaired interfaces have now completed two native Linux gated executions in owned workflow run 37402311165 on 2026-10-06. Each contains 18,900 rows: 756 satisfied clean rows, 972 satisfied stage-isolation checks, and 17,172 active-fault rows (11,898 satisfied, 4,266 inconsistent, and 1,008 inadmissible). The 18,144 nonclean configurations are not all fault-active. Native evidence exposes 1,242 of 1,296 planned units and 21, 27, 33, and 69 of 72 design units for the fixed suites, matching the retained counts. M15 remains unexposed on all three carriers. The matrices have identical keys and zero differences across 207,900 comparisons over 11 stored non-timing fields; this is not complete request/action/command/artifact trajectory replay or external replication.

The workflow selects Python 3.12. The actual environment is Python 3.12.14, GCC 13.3.0, Clang 18.1.3, and GNU binutils 2.42 on Ubuntu Linux x86_64, kernel 6.17.0-1022-azure with glibc 2.39. First-run per-row duration median is 0.136894 seconds and maximum 0.677082 seconds. Timing ends before subsequent case-workspace cleanup and outer temporary-directory disposal; it is not campaign wall time. Exact measured version strings are in `results/native-linux/native-environment.json`.

The actual regression log for job 112072001072 records **71 tests in 10.391 seconds, all successful**, including `test_real_elf_missing_and_present_section_are_distinct`. It is preserved as `results/native-linux/native-tests.txt`. The earlier selected Windows checks were **54 tests: 53 passed and one real-ELF test skipped**; they are a different test selection, not the native test total. No tests were rerun merely to integrate these files.

The complete native result archive is `results/native-linux/evidence.zip` (the original 573,700-byte download, unchanged). Its raw entries are `native-study/first.csv` and `native-study/second.csv`; the environment and all 13 derived files are also included. Derived files and the environment are available uncompressed alongside it, and the separately downloaded test log is an additional file outside the original archive. See [native evidence and manual extraction](results/native-linux/README.md). Any locally expanded raw CSVs are inspection copies, not additional evidence to upload; the canonical publication copy of both native matrices is the complete ZIP. Historical raw files are not replaced.

MR13 executes `B1 B2 X1 X2 X1` in the evidence-gated handler, changes payload only, and checks `p1, p2, p1`. Key, compiler and optimization remain `key-alpha`, GCC and O2. The historical Boolean handler has a different sequence and second key; it is not a replacement implementation for MR13.

## Verify without changing the frozen package

```sh
cd artifact
./scripts/verify.sh
```

The verifier runs the scientific tests and checks retained-row accounting, admission evidence, and stored-field agreement. It does not regenerate paper tables or figures, validate a release manifest, or repeat compiled campaigns. Bibliographic structure is checked separately from external-record review; a citation occurrence never constitutes proof of semantic support.

## Execute a new study

```sh
cd artifact
./scripts/run_full.sh /a/new/output/directory 4
```

Use a genuinely new directory. Existing files are refused. The command runs both complete matrices and produces a comparison and derived summaries; it does not overwrite packaged evidence. For a short source-isolation smoke test:

```sh
PYTHONPATH=src python3 -m tosem02.cli run --out /a/new/clean.csv --design-only --clean-only --workers 2
```

Python3, GCC, Clang, GNU objcopy/nm/strip/readelf, pkg-config, and development packages for zlib, OpenSSL, SQLite, libxml2, json-c and libpng are required. The native measured tool versions are in results/native-linux/native-environment.json; results/admission-study/environment.json describes the earlier gated study and must not be substituted for the native platform. No network is required for the packaged tests. The external-source adapter is separate and requires lawful acquisition of its exact upstream snapshot.

## Evidence boundaries

Symbol extraction checks the 16-bit payload-length domain, exact chunk count and widths, and the canonical empty-payload placeholder before key or checksum decisions. The later compiled replay is retained unchanged in `results/repair-replay/evidence.zip`: `native-tests.log` records 84 tests in 13.503 seconds, and `native-study/first.csv` and `native-study/second.csv` each contain 18,900 rows. Their 11 non-timing fields agree across 207,900 comparisons; counts and 10,000 bootstrap replicates match the earlier results. The original 71-test archive remains a separate measurement predating these repairs. Neither campaign reruns the external utility or public source-pair studies.

The catalog retains 24 operator identities and 12 named classes. M12 is a stage-routing proxy implemented by suppressing carrier construction before compilation, the same action as M01. Its 51/51 holdout result is not evidence of an unseen routing implementation because M01 remains in the selection data.

The full-study derivation now returns a nonzero exit status for incomplete planned denominators, a clean inconsistency or inadmissibility, or a failed requested rerun comparison. It writes `scientific_checks.json` beside new derived outputs before failing, so the raw matrices and failed comparison remain available. Inadmissible seeded cases and unrevealed fault units are still permitted and reported; the gate does not require a perfect sensitivity score. `scripts/run_full.sh` propagates that failure under its existing fail-fast behavior.

Before deriving a full study, the coverage guard also requires exactly one row for every configured `(host, carrier, defect_id, relation_id)` key: the 18 supplied hosts, three carriers, `CLEAN` plus M01–M24, and MR01–MR14. Matching cardinalities or matching-but-wrong rerun grids are insufficient. Missing, unexpected and duplicate keys produce a failing `scientific_checks.json` with exact counts and at most 20 examples per category; remaining study checks are explicitly `NOT_RUN`. Valid-grid derivations retain their existing output format and all semantic, clean-control and rerun checks. Partial native smoke runs remain available but are not complete-study evidence. No historical matrix, derived result, archive or digest is rewritten by this repair. Portable finite controls run with `PYTHONPATH=src:tests python -B -m unittest -v test_study_coverage test_scientific_repairs.CampaignGateTests` (use `src;tests` on Windows); scientific CI explicitly includes the new module, and native test discovery also includes it.

The new interpreter shares a parser family with its seed-free carrier observer. It does not prove parser independence, security, universal robustness or whole-program semantics. Carrier removal is an experimental antecedent, so skipped removal is inadmissible as an extraction test. A separate direct transform-stage obligation would be needed to expose that mechanism.

The GNU/LLVM 378-case study and public source-pair 120-row study are retained evidence, not newly executed by the interface repair. The utility study contains 288 host-plus-payload preservation rows, 72 rejection-only rows without host comparison, and 18 incompatibilities. The source-pair study lacks an automated embedding/extraction interface and a confirmed historical defect pair; its 10 output differences are conditional on the source-equivalence assumption. The repaired adapter rejects missing file outputs and non-success termination before semantic or relocation comparison, while retaining valid empty stdout.

## Portable verification entry points

From a checkout or a copy containing only `artifact/`:

```sh
cd artifact
./scripts/verify_science.sh
```

This command validates code, specifications, retained evidence, and scientific derivations without requiring paper sources, author metadata, or historical release audits. Paper compilation is optional and separate:

```sh
cd artifact
./scripts/build_paper_optional.sh ../paper
```

Rows are classified as `FAULT_ACTIVE`, `STAGE_ISOLATION`, or `CLEAN`. For MR04, MR09, and MR10, M01--M05 and M12 are guarded upstream; their 972 expanded-matrix rows check the negative antecedent and are not counted as active fault executions. Legacy two-run equality covered retained row fields only and must not be described as complete trace replay.

Bounded model checks do not require a compiler:

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_repair_models.py -v
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_evidence_boundaries.py -v
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_scientific_repairs.py -v
PYTHONPATH=src python3 -B scripts/derive_observation_accounting.py
```

The last command reads retained matrices only. It is an accounting derivation, not a new experiment. Real-ELF tests and compiled campaigns require the listed Linux tools and dependencies. The downloaded native log and two complete matrices establish that this native execution has occurred; they do not establish a fresh run of the separate external utility or upstream-source studies.
