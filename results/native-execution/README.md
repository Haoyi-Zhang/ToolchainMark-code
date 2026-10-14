# Current v3 native execution records

This directory publishes the four plain-CSV matrices from two complete Linux
executions of the current `evidence-gated-v3-snapshot-coherence` implementation.
Each execution ran the same 18-host × 3-carrier × 25-case × 14-relation plan
twice, yielding 18,900 unique configured keys per matrix. The primary and
mirror runs repeat the same implementation and Git tree within this project's
reproduction workflow. Each run's original test log records 119 passing
real-tool regressions, including actual ELF utility checks.

`primary/` and `mirror/` each contain `first.csv`, `second.csv`, all 14 original
derived files, `native-environment.json`, and the three original log members
renamed from `.log` to `.txt` without changing their bytes. `provenance.json`
binds every published file to its original ZIP member, byte count, SHA-256,
run/head/job/artifact identity, and the ZIP's SHA-256. The full original ZIPs
are retained by the project coordinator rather than duplicated here.
`source-inputs.json` records the 71 current native-input path/blob identities
matched against the untruncated Git tree common to both run heads. The older
v2 records in `results/current-native/` remain separate and unchanged; 63 of
their 71 input paths have identical bytes here, while eight current inputs
changed. Old v2 outputs must not be relabelled as v3 executions.

The primary first matrix has 756 satisfied clean controls, 972 satisfied
stage-isolation rows, and 17,172 fault-active rows: 11,898 satisfied, 4,266
inconsistent, and 1,008 inadmissible. The 24 seeded operators form 1,296
planned fault units, of which 1,242 are exposed by at least one admitted
relation; all 1,296 have an admitted case. All 1,206 admitted MR10 rows per
matrix record complete true checksum-locality and snapshot-coherence facts.
The two matrices within each run and corresponding matrices across runs agree
on all 207,900 comparisons over 11 non-timing fields. The primary first-run
median recorded *per-row* duration is 0.1372015 seconds; the mirror median is
approximately 0.11786 seconds. The timer ends before subsequent cleanup; the
two host-specific measurements describe per-row execution cost.

The current data-only check, without compiler execution or network access, is:

```sh
python3 -B evaluation/verify_native_execution.py
python3 -O -B evaluation/verify_native_execution.py
```

It checks the 71 current input bytes, each published member's original ZIP
identity, all four exact planned key domains and v3 admission records, rerun
agreement, and full rederivation of both sets of 14 derived files. These checks
verify the published data and its producer binding. Observation semantics are
checked by the recorded native tests and relation gates; complete trajectory
replay, product transfer, and unseen-fault sensitivity require separate evidence.
The unexposed M15 operator and zero-sensitivity classes and operators
remain visible in `derived/summary.json` and the holdout tables.
