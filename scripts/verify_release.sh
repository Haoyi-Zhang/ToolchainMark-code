#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$ARTIFACT_ROOT/.." && pwd)"
"$SCRIPT_DIR/verify_science.sh"
if [[ -f "$SCRIPT_DIR/verify_package.py" ]]; then python3 "$SCRIPT_DIR/verify_package.py" "$PROJECT_ROOT"; fi
if [[ "${1:-}" == "--with-paper" ]]; then "$SCRIPT_DIR/build_paper_optional.sh" "$PROJECT_ROOT/paper"; fi
