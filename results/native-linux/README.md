# Native Linux evidence

Owned workflow run 37402311165 executed the repaired evidence-gated interfaces on 2026-10-06. The complete original result download is preserved unchanged as `evidence.zip` (573,700 bytes). Both actual raw matrices are inside that archive; publishing a second expanded copy of either matrix is unnecessary.

## Files and manual extraction

The archive contains exactly these result locations:

- `native-environment.json`: the measured Python, platform, and native tool versions.
- `native-study/first.csv` and `native-study/second.csv`: the two complete 18,900-row matrices.
- `native-study/derived/`: all 13 original derived files, including `summary.json`, `rerun_comparison.json`, admission/relation/unit/suite outcomes, paired comparisons, carrier/class/operator holdouts, and bootstrap rows and summary.

The environment and all derived files are also supplied uncompressed at those same relative paths beside the archive. `platform.json` records the run identity and measured result scope. `native-tests.txt` is the actual separately downloaded regression log for job 112072001072; it is not an entry in the original ZIP.

To inspect the raw rows, manually extract the archive into a new directory using a ZIP viewer, or from the artifact root:

```sh
python3 -m zipfile -e results/native-linux/evidence.zip /a/new/native-evidence-directory
```

The extracted matrices are `/a/new/native-evidence-directory/native-study/first.csv` and `/a/new/native-evidence-directory/native-study/second.csv`. Extraction reads data only; no script from the archive needs to be executed. Locally expanded copies, if present beside this README, are inspection copies; the complete ZIP is the canonical publication copy of the raw evidence.

## Actual results

Each run has 18,900 configured rows: 756 satisfied clean controls, 972 satisfied stage-isolation checks, and 17,172 active-fault cases (11,898 satisfied, 4,266 inconsistent, 1,008 inadmissible). The 18,144 nonclean configurations are not all fault-active. The full catalog exposes 1,242/1,296 expanded units and 69/72 design units. M15 accounts for the three unexposed design units and 54 unexposed expanded units; failed removal is not credited as an extraction inconsistency.

Both runs have identical scientific key sets and zero differences across 207,900 comparisons of 11 non-timing fields. All durations are positive. The first matrix's per-row duration median is 0.136894 seconds and maximum is 0.677082 seconds. The timer includes the relation attempt and row preparation, but excludes subsequent case-workspace cleanup and outer temporary-directory disposal. These measurements use the campaign's four-worker configuration and are not whole-campaign wall time.

The workflow selects Python 3.12; this run used Python 3.12.14, GCC 13.3.0, Clang 18.1.3, and GNU binutils 2.42 on Ubuntu Linux x86_64, kernel 6.17.0-1022-azure with glibc 2.39. Exact strings are preserved in `native-environment.json`; future runner images need not have identical versions.

The regression log lists 71 successful tests and reports `Ran 71 tests in 10.391s` followed by `OK`, including `test_real_elf_missing_and_present_section_are_distinct`. The earlier selected local checks were a different 54-test selection: 53 passes and one real-ELF skip. They are not the native test count.

## Evidence boundary

This is completed native ELF execution of the repaired internal campaign, not complete command/artifact/per-input trajectory replay or external-team replication. The separate 378-case GNU/LLVM utility study and upstream source-pair, relocation, and sanitizer studies were not rerun by this campaign. Their historical raw rows, source identities, licensing boundaries, and research integrity mechanisms remain separate and unchanged. No automated upstream watermark recovery or confirmed historical product-defect pair is supplied by these results.
