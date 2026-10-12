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

In the manuscript-containing project, `python scripts/generate_admission_tables.py --plots`
from the artifact directory updates the public and manuscript plot data/assets.
Without `--plots`, table generation does not overwrite the includegraphics wrapper.
The manuscript retains its original panel sizes, headings, caption and description.

The unmodified Linux Libertine regular TrueType face is bundled under
`../fonts/OFL-1.1.txt`. The renderer also accepts `--font` or matching installed
TeX/Matplotlib fonts; it rejects substitutions and CFF/Type1 fonts. Matplotlib
is optional and is not required by the scientific execution core.
