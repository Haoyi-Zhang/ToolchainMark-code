# Sensitivity figure reproduction

The two PDF panels read the retained four-suite and twelve-class counts in
`results-overview.csv`. These are finite planned-unit sensitivities, not population
estimates. Labels, category order, the 72-unit fixed-suite denominator and the
five zero-sensitivity classes are retained.

From the artifact directory, optionally install the plotting dependency and run:

```sh
python -m pip install -r figures/requirements.txt
python -B figures/draw_results_overview.py
```

To rederive the plot CSV from already retained outputs without running experiments:

```sh
python -B figures/draw_results_overview.py --refresh-data results/admission-study/derived
```

In the manuscript-containing project, refresh and redraw both copies from the
artifact directory with the standalone figure producer:

```sh
python -B figures/draw_results_overview.py --refresh-data results/admission-study/derived
python -B figures/draw_results_overview.py --refresh-data results/admission-study/derived --data ../paper/figures/results-overview.csv --out-dir ../paper/figures
```

These commands read the retained summary and class-holdout counts without running
experiments or changing current table inputs or frozen native records. Both current
primary manuscripts use `paper/figures/results-overview-data.tex`, which only
includes the saved PDF panels and retains their sizes and headings. The caption
and description remain in the primary manuscripts.

The original `scripts/generate_admission_tables.py` is a historical producer: it
writes historical table inputs and the inactive `paper/figures/results-overview.tex`.
It has no plotting flag and is not the current figure or current-table refresh
command. The active `results-overview-data.tex` wrapper is outside its write paths.

The unmodified Linux Libertine regular TrueType face is bundled under
`../fonts/OFL-1.1.txt`. The renderer also accepts `--font` or matching installed
TeX/Matplotlib fonts; it rejects substitutions and CFF/Type1 fonts. Matplotlib
is optional and is not required by the scientific execution core.
