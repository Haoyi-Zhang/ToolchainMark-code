#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
PAPER_DIR="${1:-$(CDPATH= cd -- "$ARTIFACT_ROOT/../paper" 2>/dev/null && pwd || true)}"
if [[ -z "$PAPER_DIR" || ! -f "$PAPER_DIR/build.sh" ]]; then
  echo "SKIP: optional paper source is not present" >&2
  exit 0
fi
cd "$PAPER_DIR"
./build.sh
