#!/usr/bin/env python3
"""Compare the frozen matrices with the packaged fresh clean-source rerun.

All row identity, diagnostic, verdict, trace, and observation fields must match.
Only per-row wall-clock duration is permitted to differ.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "results" / "raw"
RERUN_ROOT = ROOT / "results" / "fresh-rerun-2026-07-24"
RERUN = RERUN_ROOT / "raw"
OUTPUT = ROOT / "audit" / "fresh_full_rerun_report.json"
FILES = ("catalog_matrix.csv", "pilot_matrix.csv", "breadth_matrix.csv")
KEY_COLUMNS = ("surface", "host", "carrier", "defect_id", "relation_id", "pilot")
IGNORED_COLUMNS = ("duration_seconds",)
EXPECTED_ROWS = {
    "catalog_matrix.csv": 1050,
    "pilot_matrix.csv": 1008,
    "breadth_matrix.csv": 216,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def row_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[column] for column in KEY_COLUMNS)


def compare_file(name: str) -> dict[str, Any]:
    frozen_path = FROZEN / name
    rerun_path = RERUN / name
    frozen_rows = read_rows(frozen_path)
    rerun_rows = read_rows(rerun_path)
    if not frozen_rows or not rerun_rows:
        raise RuntimeError(f"empty comparison input: {name}")
    frozen_columns = tuple(frozen_rows[0].keys())
    rerun_columns = tuple(rerun_rows[0].keys())
    comparable_columns = tuple(column for column in frozen_columns if column not in IGNORED_COLUMNS)
    frozen_map = {row_key(row): row for row in frozen_rows}
    rerun_map = {row_key(row): row for row in rerun_rows}

    difference_counts: Counter[str] = Counter()
    non_timing_mismatch_rows = 0
    duration_nonpositive_rows = 0
    duration_equal_rows = 0
    for key in sorted(set(frozen_map) | set(rerun_map)):
        if key not in frozen_map or key not in rerun_map:
            non_timing_mismatch_rows += 1
            difference_counts["missing_row"] += 1
            continue
        frozen_row = frozen_map[key]
        rerun_row = rerun_map[key]
        row_has_non_timing_mismatch = False
        for column in comparable_columns:
            if frozen_row[column] != rerun_row[column]:
                difference_counts[column] += 1
                row_has_non_timing_mismatch = True
        if row_has_non_timing_mismatch:
            non_timing_mismatch_rows += 1
        frozen_duration = float(frozen_row["duration_seconds"])
        rerun_duration = float(rerun_row["duration_seconds"])
        if frozen_duration <= 0 or rerun_duration <= 0:
            duration_nonpositive_rows += 1
        if frozen_row["duration_seconds"] == rerun_row["duration_seconds"]:
            duration_equal_rows += 1

    checks = {
        "column_schema_identical": frozen_columns == rerun_columns,
        "expected_row_count": len(frozen_rows) == len(rerun_rows) == EXPECTED_ROWS[name],
        "row_keys_unique_frozen": len(frozen_map) == len(frozen_rows),
        "row_keys_unique_rerun": len(rerun_map) == len(rerun_rows),
        "row_key_sets_identical": set(frozen_map) == set(rerun_map),
        "all_non_timing_fields_identical": non_timing_mismatch_rows == 0,
        "all_durations_positive": duration_nonpositive_rows == 0,
    }
    return {
        "file": name,
        "frozen_sha256": sha256(frozen_path),
        "fresh_rerun_sha256": sha256(rerun_path),
        "rows": len(frozen_rows),
        "key_columns": list(KEY_COLUMNS),
        "compared_columns": list(comparable_columns),
        "excluded_platform_sensitive_columns": list(IGNORED_COLUMNS),
        "non_timing_mismatch_rows": non_timing_mismatch_rows,
        "non_timing_difference_counts": dict(sorted(difference_counts.items())),
        "duration_equal_rows": duration_equal_rows,
        "duration_different_rows": len(frozen_rows) - duration_equal_rows,
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }


def main() -> None:
    comparisons = [compare_file(name) for name in FILES]
    frozen_environment = ROOT / "environment.json"
    rerun_environment = RERUN_ROOT / "environment.json"
    rerun_recheck = json.loads((RERUN_ROOT / "recheck_report.json").read_text())
    total_rows = sum(item["rows"] for item in comparisons)
    checks = {
        "three_matrices_compared": len(comparisons) == 3,
        "total_rows_2274": total_rows == 2274,
        "all_matrix_comparisons_pass": all(item["verdict"] == "PASS" for item in comparisons),
        "environment_record_identical": frozen_environment.read_bytes() == rerun_environment.read_bytes(),
        "fresh_rerun_recheck_pass": rerun_recheck.get("verdict") == "PASS",
        "fresh_rerun_recheck_predicates_8": len(rerun_recheck.get("checks", {})) == 8,
        "fresh_rerun_recheck_all_true": all(rerun_recheck.get("checks", {}).values()),
    }
    report = {
        "schema_version": "1.0",
        "classification": "FRESH_CLEAN_SOURCE_RERUN_SAME_ENVIRONMENT_NOT_EXTERNAL_INDEPENDENT_REPLICATION",
        "command": rerun_recheck.get("command", "python3 scripts/run_base_rerun.py --output results/fresh-rerun-2026-07-24"),
        "comparison_rule": "Rows are keyed by surface, host, carrier, defect, relation, and pilot flag. Every field except duration_seconds must match exactly; both durations must remain positive.",
        "frozen_environment_sha256": sha256(frozen_environment),
        "fresh_rerun_environment_sha256": sha256(rerun_environment),
        "total_rows_compared": total_rows,
        "matrices": comparisons,
        "checks": checks,
        "limitations": [
            "The rerun used a fresh clean source copy but the same container toolchain family and is not an external independent replication.",
            "Wall-clock durations are scheduler-sensitive and are deliberately excluded from exact equality.",
            "A stateless artifact-only peer review remains unavailable and is not represented as completed.",
        ],
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
    print(json.dumps(report, indent=2, sort_keys=False))
    if report["verdict"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
