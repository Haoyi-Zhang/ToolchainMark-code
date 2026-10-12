#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/src"
OUT=${1:?Supply a NEW output directory outside the frozen evidence}
WORKERS=${2:-4}
if [ -e "$OUT" ]; then echo "Refusing to overwrite an existing directory" >&2; exit 2; fi
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
python3 -m tosem02.cli run --out "$OUT/first.csv" --workers "$WORKERS"
python3 -m tosem02.cli run --out "$OUT/second.csv" --workers "$WORKERS"
python3 "$ROOT/scripts/derive_admission_study.py" --matrix "$OUT/first.csv" --rerun "$OUT/second.csv" --mutants "$ROOT/specs/mutants.json" --legacy "$ROOT/results/raw/robustness_matrix.csv" --out "$OUT/derived"
