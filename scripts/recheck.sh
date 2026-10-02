#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/src"
python3 -m tosem02.cli recheck
