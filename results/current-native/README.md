# Retained native checksum-locality results

These are measured results of the published `evidence-gated-v2-checksum-locality`
contract, not a relabeling of the earlier checksum-rejection-only matrices.
Canonical workflow run **38310980867**, head
`c8367e792913794672baff73cee2a62df2975574`, completed successfully and
ran 116 regression tests in 34.507 seconds without skips. It executed both
full matrices with real GCC/Clang and ELF utilities. The genuine downloaded
artifact is **11775931468**.

The mirror is a separate execution of the same bound native inputs, not an independently
implemented tool or external-team replication. Run **38310978633**, head
`777877f94814a217b7a73c24c9c3f568469d492e`, artifact **11775174136**,
completed successfully. It ran 116 tests in 16.658 seconds without skips.
Exact measured environment strings, run/commit/artifact identities and
execution scope are preserved in `native-environment.json` and `provenance.json`.
Both runs used Python 3.12.15, GCC 13.3.0, Clang 18.1.3 and GNU binutils 2.42.
The coordinator supplied the successful run/head/artifact identities. The
archives do not contain job IDs, full Git trees, commit UTC timestamps or step
UTC timestamps; none is inferred or copied from an earlier campaign.

## Files and lossless transport

- `first.csv.gz`, `second.csv.gz`: canonical original CSV bytes, losslessly
  compressed with gzip level 9, `mtime=0`, and no stored filename.
- `derived/`: all 14 downloaded derived files, unchanged, including the
  10,000-row bootstrap CSV and `scientific_checks.json`.
- `native-tests.log`, `native-campaign.log`, `native-dependencies.log`, and
  `native-environment.json`: unchanged canonical measured records.
- `mirror/`: corresponding raw gzip files, derived files, logs and environment
  from the mirror execution.
- `source-snapshot/`: the original 23 claim-critical files identical to the
  verified native input blobs, including the repaired CLI and utility helper.
  They are inert provenance copies, not an additional execution or a
  standalone installable package.
- `historical-source-recovery/` and `historical-source-recovery.json`: two
  previously unsnapshotted historical inputs, a regression module and the
  package verifier, recovered from the recorded canonical Git commit.
  Each file matches its published Git blob;
  recovery is not a new execution or a replacement for the original snapshot.
- `transport.json`: byte lengths, raw/gzip SHA-256 identities and successful
  decompression byte comparisons.
- `native-inputs.json`: the 71 exact native-input path/blob identities,
  including the new regression module and the exact validated native YAML.
  Unchanged identities remain bound to the prior verified inputs; the four
  changed/new identities match the reviewed validation-branch transport bytes.
  Local audit reports and verifier stdout are kept outside this artifact.

The canonical CSVs originally contain 8,445,670 and 8,445,618 bytes. The
published gzip files contain 236,440 and 236,359 bytes. Decompression was
compared byte-for-byte with the originals: no row, field, order or newline was
altered. The exact original CSVs and original downloaded ZIPs are retained
privately for comparison, not redundantly published here. Original ZIP sizes
and digests remain in `provenance.json`. Derived CSVs remain plain for existing
consumers. The raw matrices are canonical in their gzip publication form.

Python's standard CSV reader can stream them directly, from the artifact root:

```python
import csv, gzip
with gzip.open('results/current-native/first.csv.gz', 'rt',
               encoding='utf-8', newline='') as stream:
    rows = list(csv.DictReader(stream))
```

The existing derivation accepts plain CSV. To rederive without executing any
native program, unpack into a temporary directory (run from the artifact root):

```sh
tmp=$(mktemp -d)
gzip -dc results/current-native/first.csv.gz > "$tmp/first.csv"
gzip -dc results/current-native/second.csv.gz > "$tmp/second.csv"
PYTHONPATH=src python3 -B scripts/derive_admission_study.py \
  --matrix "$tmp/first.csv" --rerun "$tmp/second.csv" \
  --mutants specs/mutants.json --legacy results/raw/robustness_matrix.csv \
  --out "$tmp/derived"
```

Inspect temporary outputs, then remove only that temporary directory when
finished. Do not overwrite historical matrices or package results. The original
`scripts/generate_admission_tables.py` is unchanged and remains a historical
generator; it is not the command for current paper inputs. Current data-only
verification and explicit current-table refresh use:

```sh
python3 -B evaluation/verify_native_records.py
python3 -B evaluation/verify_native_records.py --paper ../paper
python3 -B evaluation/verify_native_records.py --paper ../paper --write-paper
```

The default verifies all four gzip matrices, rederives both campaigns in
temporary directories with the current analysis script, and checks all 71
historical native-input byte bindings. It writes no paper input. The second
command also checks current paper values.
Only explicit `--write-paper` regenerates the two measured TeX inputs when needed; it never
redraws figures or substitutes old measurements. The Scientific checks
workflow invokes the read-only verifier. Native compiler YAML is byte-identical
to the validated workflow, including the `native-check-*` trigger; its execution
and resource steps are unchanged. The recorded fresh campaigns include the
repaired native inputs. The original `validation.json` records the then-current
71-file check, not a fresh check of today's source tree. Eight current files
have since changed: 63 current files still match the historical blobs, six
old versions are in `source-snapshot/`, and two old sources are in the later
recovery directory. The verifier reports these categories and any current-only
paths separately. It does not use the old runs to certify current v3 native
execution. If an old blob is unavailable or differs, historical binding fails;
if a producer changes, its new behavior needs its own applicable native evidence.

## Actual scientific results

Each of the four raw matrices covers exactly 18,900 unique configured keys:
756 clean controls, 972 stage-isolation checks, and 17,172 fault-active cases.
There are no missing, unexpected or duplicate planned keys. Clean and
stage-isolation cases are satisfied. Active outcomes are **11,898 satisfied,
4,266 inconsistent, 1,008 inadmissible**. The catalog exposes **1,242/1,296**
expanded units and **69/72** design units; M15 remains unexposed. The fixed
suites expose 21, 27, 33 and 69 design units. Class and operator holdouts still
have five and eight zero-sensitivity groups respectively. Bootstrap results
remain 10,000 replicates, 1,884 perfect, median suite size 9 and minimum
out-of-bag sensitivity 60.0%.

Within each run, and between canonical and mirror first matrices, all 207,900
comparisons over 11 non-timing fields agree exactly. Durations are positive.
Canonical first/second medians are 0.1229545/0.119467 seconds and maxima are
1.779854/0.933247 seconds. Mirror first/second medians are 0.114171/0.115176
seconds and maxima are 0.841067/0.763925 seconds. Timing excludes subsequent
workspace cleanup and is not whole-campaign wall time.

The fresh matrices agree on every retained non-timing field with the preceding
checksum-locality campaigns; only measured times and byte identities change.
The counts and selection metrics reproduce the older retained studies, but their
MR10 evidence is different: 1,206 rows have added locality admission facts and
`integrity_intervention` observations (2,412 changed non-timing field values).
After removing only those declared additions for comparison, the remaining
stored fields agree. This comparison does not backfill or upgrade old rows.
All 1,206 admitted current MR10 cases record true payload preservation,
non-checksum material preservation and checksum change. All 54 M16/MR10
checksum-bypass cases are inconsistent. No fake positive outcome or score
increase is inferred from the stronger gate. The separate 12-case fixture
comparison still has nine old-rule admissions versus three current admissions,
including six payload-changing cases rejected only by the current rule.

## Evidence boundary

`../admission-study`, `../native-linux`, and `../repair-replay` retain their
earlier contract and original rows, archives, environments and timings.
Equal numerical counts do not pool their MR10 qualification with this study.
The current run supplies real compiled checksum-locality evidence for the
internal seeded campaign, not an independent parser, a CTF experiment, an
independent embed-transform-extract product study, an upstream confirmed
historical defect, or a field-value estimate. The 378-case utility study and
public source-pair/sanitizer studies remain separately retained experiments.
