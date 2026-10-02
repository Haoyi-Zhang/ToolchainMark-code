# Contract-aware watermark validation artifact

## Current protocol and evidence

The current implementation is the evidence-gated protocol. It distinguishes SATISFIED, INCONSISTENT and INADMISSIBLE. Only an admitted inconsistency exposes a fault unit. This corrects the supplied Boolean runner, which conflated relation failure with invalid construction. The original source operators and historical matrices remain available and are not pooled with current estimands.

Two new complete executions each contain 18,900 rows: 756 satisfied clean rows, 12,870 satisfied fault rows, 4,266 inconsistent fault rows and 1,008 inadmissible fault rows. There are 1,242 exposed units among 1,296 planned units, not 1,296 exposed units. The design-subject suites expose 21, 27, 33 and 69 of 72 units. All 207,900 non-timing field comparisons between the two new runs agree. These are repeated internal executions, not external replication.

## Verify without changing the frozen package

```sh
cd artifact
./scripts/verify.sh
```

The verifier executes tests, rederives current tables and figures, checks the current admission evidence, and verifies the file manifest before and after. Bibliographic structure is checked separately from external-record review; a citation occurrence never constitutes proof of semantic support.

## Execute a new study

```sh
cd artifact
./scripts/run_full.sh /a/new/output/directory 4
```

Use a genuinely new directory. Existing files are refused. The command runs both complete matrices and produces a comparison and derived summaries; it does not overwrite packaged evidence. For a short source-isolation smoke test:

```sh
PYTHONPATH=src python3 -m tosem02.cli run --out /a/new/clean.csv --design-only --clean-only --workers 2
```

Python3, GCC, Clang, GNU objcopy/nm/strip, pkg-config, and development packages for zlib, OpenSSL, SQLite, libxml2, json-c and libpng are required. The recorded environment is in results/admission-study/environment.json. No network is required for the packaged tests. The external-source adapter is separate and requires lawful acquisition of its exact upstream snapshot.

## Evidence boundaries

The new interpreter shares a parser family with its seed-free carrier observer. It does not prove parser independence, security, universal robustness or whole-program semantics. Carrier removal is an experimental antecedent, so skipped removal is inadmissible as an extraction test. A separate direct transform-stage obligation would be needed to expose that mechanism.

The GNU/LLVM 378-case study and public source-pair 120-row study are inherited evidence from the uploaded package, not newly executed in this revision. The latter lacks an automated embedding/extraction interface and a confirmed historical defect pair; its 10 output differences are conditional on the source-equivalence assumption.

The manuscript is a draft with three supplied identities and three blank layout reservations. It is not ready for submission with an incomplete author roster.

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
