# Independent public-prototype transfer

This directory records a transfer study against the public research prototype associated with **Software Watermark Scheme** (DOI 10.1109/MetroInd4.0IoT54413.2022.9831668), repository `felipeasimos/software-watermark`, fixed at commit `f63f49a770e3b0dc4f1d092cfa22ec2610eb13f8`.

The fixed repository exposes three labeled before/after C source pairs. The study treats them as an independently maintained example surface, not as a production product or historical-defect corpus. It compares an execution-only baseline with host-observation equivalence under GCC and Clang at five optimization levels, relocation, and address/undefined-behavior sanitizers.

The upstream source files are **not redistributed** because no explicit repository license was present at the fixed commit. `acquisition_manifest.csv` records immutable paths, Git blob identifiers, and SHA-256 digests. To re-run, either acquire the six files manually or use the packaged read-only acquisition helper after reviewing the upstream terms:

```sh
python3 acquire_sources.py --out /path/to/acquired/files --acknowledge-no-redistribution-license
PYTHONPATH=../src python3 run_external_transfer.py --source-dir /path/to/acquired/files --out /path/to/new/output
```

The runner checks the fixed Git blob identities before execution; SHA-256 identities remain recorded in the acquisition manifest. The earlier runner-path defect and its historical repair are preserved under protocol history. Those old comparisons are not evidence of a full rerun of the current output-observation repair.

The current adapter compares outputs only after a successful process exit and an available declared output channel. Case 119 requires the expected output file; the other cases use stdout, which may legitimately be empty. Missing files, unreadable files, and non-success exits are unavailable observations, not matching sentinel strings. Relocation independently requires successful original and relocated execution plus both output observations. Existing output directories are refused. Importing the adapter for model tests performs no acquisition, compilation, experiment, or output write.

The native build mode leaves upstream source untouched. One legacy example does not satisfy the native build precondition because it uses an obsolete floating-point predicate spelling. A separately declared compatibility mode forces the same small header into both variants without editing either source. This mode is reported separately rather than silently repairing the upstream program.

The snapshot does not expose an automatable source-to-payload extraction interface for the labeled examples. Payload recovery is therefore `INADMISSIBLE`; filenames are never treated as an oracle. Frozen results are under `artifact/results/external-transfer/`.
