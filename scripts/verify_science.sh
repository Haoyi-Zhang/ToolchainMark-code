#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ARTIFACT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$ARTIFACT_ROOT"
python3 -m unittest discover -s tests -v
python3 scripts/verify_science.py
