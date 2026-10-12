# Current native checksum-locality results

These are measured results of the current `evidence-gated-v2-checksum-locality`
contract, not a relabeling of the earlier checksum-rejection-only matrices.
Canonical workflow run **38191576562**, head
`2eea208a1e383a51b83bd0420f98f685949a4aed`, completed successfully on
2026-10-12. Job **114625256622** ran 103 regression tests in 11.727 seconds
without skips and executed both full matrices with real GCC/Clang and ELF
utilities. Its matrix/derivation step ran from **01:22:02 to 01:47:39 UTC**.
Artifact **11722876392** was created at **01:47:40 UTC**.

The mirror is a separate execution of the same Git tree, not an independently
implemented tool or external-team replication. Run **38192265626**, head
`df2b4c0323c94ec3782fce85f358720c6706c330`, job **114627345751**, artifact
**11722857486**, completed successfully. It ran 103 tests in 8.147 seconds
without skips; its full-matrix step ran from **01:32:33 to 01:57:37 UTC**.
Exact measured environment strings, UTC metadata, source identities and
execution scope are preserved in `native-environment.json` and `provenance.json`.
Both runs used Python 3.12.15, GCC 13.3.0, Clang 18.1.3 and GNU binutils 2.42.

## Files and lossless transport

- `first.csv.gz`, `second.csv.gz`: canonical original CSV bytes, losslessly
  compressed with gzip level 9, `mtime=0`, and no stored filename.
- `derived/`: all 14 downloaded derived files, unchanged, including the
  10,000-row bootstrap CSV and `scientific_checks.json`.
- `native-tests.log`, `native-campaign.log`, `native-dependencies.log`, and
  `native-environment.json`: unchanged canonical measured records.
- `mirror/`: corresponding raw gzip files, derived files, logs and environment
  from the mirror execution.
- `source-snapshot/`: claim-critical files fetched at both exact commits;
  their Git blob identities agree. They are inert provenance copies, not an
  additional execution or a standalone installable package.
- `transport.json`: byte lengths, raw/gzip SHA-256 identities and successful
  decompression byte comparisons.
- `native-inputs.json`: the 70 native-input blob identities at both successful
  commits, including the unchanged original table generator and native YAML.
- `validation.json`: integration-time data checks and comparison with retained
  evidence. All paths are relative; these checks are not another native run.

The canonical CSVs originally contain 8,445,649 and 8,445,562 bytes. The
published gzip files contain 232,522 and 232,535 bytes. Decompression was
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
temporary directories and checks the unchanged native-input bindings. It
writes no paper input. The second command also checks current paper values.
Only explicit `--write-paper` regenerates the two changed TeX inputs; it never
redraws figures or substitutes old measurements. The Scientific checks
workflow invokes the read-only verifier. Native compiler YAML is unchanged.
Later documentation/data/helper changes are not described as a new-head native
execution: the last applicable successes remain the recorded runs, with all
70 native-input files unchanged. A binding failure requires new applicable
native evidence rather than reuse of an old green result.

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
Canonical first/second medians are 0.137322/0.1378305 seconds and maxima are
0.670565/0.658338 seconds. Mirror first/second medians are 0.1308205/0.131342
seconds and maxima are 0.663797/0.689011 seconds. Timing excludes subsequent
workspace cleanup and is not whole-campaign wall time.

The counts and selection metrics reproduce the retained studies, but their
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
