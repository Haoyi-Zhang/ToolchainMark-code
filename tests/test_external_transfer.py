from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


class ExternalTransferEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifact = Path(__file__).resolve().parents[1]
        cls.results = cls.artifact / "results" / "external-transfer"
        cls.summary = json.loads((cls.results / "summary.json").read_text(encoding="utf-8"))
        cls.execution = cls._rows(cls.results / "execution_rows.csv")
        cls.relations = cls._rows(cls.results / "relation_verdicts.csv")
        cls.sanitizers = cls._rows(cls.results / "sanitizer_rows.csv")

    @staticmethod
    def _rows(path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_frozen_counts_and_negative_result(self) -> None:
        s = self.summary
        self.assertEqual((s["source_pairs"], s["source_identity_checks"], s["source_identity_mismatches"]), (3, 6, 0))
        self.assertEqual((s["compatibility_exit_only_satisfied"], s["compatibility_exit_only_checks"]), (30, 30))
        self.assertEqual((s["compatibility_host_semantic_satisfied"], s["compatibility_host_semantic_inconsistent"]), (20, 10))
        self.assertEqual((s["relocation_satisfied"], s["relocation_admitted"]), (110, 110))
        self.assertEqual((s["sanitizer_clean"], s["sanitizer_checks"]), (12, 12))
        self.assertEqual(s["payload_recovery_verdict"], "INADMISSIBLE")

    def test_rows_and_summary_are_consistent(self) -> None:
        rows = self.execution
        keys = ("mode", "case", "compiler", "optimization", "variant")
        indexed = {tuple(row[key] for key in keys): row for row in rows}
        self.assertEqual(len(indexed), len(rows))
        expected = {
            (mode, case, compiler, optimization, variant)
            for mode in ("native", "compatibility")
            for case in ("119", "2929", "363")
            for compiler in ("gcc", "clang")
            for optimization in ("O0", "O1", "O2", "O3", "Os")
            for variant in ("before", "watermarked")
        }
        self.assertEqual(set(indexed), expected)
        self.assertEqual(self.summary["execution_rows"], len(rows))
        for mode in ("native", "compatibility"):
            self.assertEqual(self.summary[mode + "_execution_rows"],
                             sum(row["mode"] == mode for row in rows))
        for mode in ("native", "compatibility"):
            for case in ("119", "2929", "363"):
                for compiler in ("gcc", "clang"):
                    for optimization in ("O0", "O1", "O2", "O3", "Os"):
                        pair = [indexed[(mode, case, compiler, optimization, variant)]
                                for variant in ("before", "watermarked")]
                        successful = all(row["compile_rc"] == row["run_rc"] == "0"
                                         for row in pair)
                        available = successful and all(row["output_sha256"] for row in pair)
                        outcomes = {
                            "execution_only_baseline": "SATISFIED" if successful else "INADMISSIBLE",
                            "host_observation_equivalence": (
                                "INADMISSIBLE" if not available else
                                "SATISFIED" if pair[0]["output_sha256"] == pair[1]["output_sha256"]
                                else "INCONSISTENT"),
                        }
                        for relation, verdict in outcomes.items():
                            matches = [row for row in self.relations
                                       if (row["mode"], row["case"], row["compiler"],
                                           row["optimization"], row["relation"]) ==
                                       (mode, case, compiler, optimization, relation)]
                            self.assertEqual(len(matches), 1)
                            self.assertEqual(matches[0]["verdict"], verdict)
        selections = {
            "native_semantic": ("native", "host_observation_equivalence"),
            "compatibility_exit_only": ("compatibility", "execution_only_baseline"),
            "compatibility_host_semantic": ("compatibility", "host_observation_equivalence"),
        }
        for prefix, (mode, relation) in selections.items():
            selected = [row for row in self.relations
                        if row["mode"] == mode and row["relation"] == relation]
            self.assertEqual(self.summary[prefix + "_checks"], len(selected))
            for verdict in ("SATISFIED", "INCONSISTENT", "INADMISSIBLE"):
                key = prefix + "_" + verdict.lower()
                if key in self.summary:
                    self.assertEqual(self.summary[key],
                                     sum(row["verdict"] == verdict for row in selected))
        admitted = [row for row in rows if row["compile_rc"] == row["run_rc"] == "0"
                    and row["output_sha256"] and row["relocate_output_sha256"]
                    and row["relocate_rc"] == "0"]
        self.assertEqual(self.summary["relocation_attempts"], len(rows))
        self.assertEqual(self.summary["relocation_admitted"], len(admitted))
        self.assertEqual(self.summary["relocation_inadmissible"], len(rows) - len(admitted))
        self.assertEqual(self.summary["relocation_satisfied"],
                         sum(row["output_sha256"] == row["relocate_output_sha256"]
                             for row in admitted))
        for row in rows:
            matched = row in admitted and row["output_sha256"] == row["relocate_output_sha256"]
            self.assertEqual(row["relocation_match"], str(matched))
        self.assertEqual(self.summary["sanitizer_checks"], len(self.sanitizers))
        for row in self.sanitizers:
            clean = row["compile_rc"] == row["run_rc"] == "0" and (
                "ERROR:" not in row["run_stderr"] and "runtime error:" not in row["run_stderr"])
            self.assertEqual(row["sanitizer_clean"], str(clean))
        self.assertEqual(self.summary["sanitizer_clean"],
                         sum(row["sanitizer_clean"] == "True" for row in self.sanitizers))

    def test_upstream_source_is_not_redistributed(self) -> None:
        transfer = self.artifact / "external-transfer"
        runner = (transfer / "run_external_transfer.py").read_text(encoding="utf-8")
        self.assertIn('COMPAT = ROOT / "compatibility_header.h"', runner)
        self.assertIn("if not COMPAT.is_file()", runner)
        self.assertIn('text.replace(str(SRC), "EXTERNAL_SOURCE")', runner)
        self.assertTrue((transfer / "compatibility_header.h").is_file())
        acquisition = (transfer / "acquire_sources.py").read_text(encoding="utf-8")
        self.assertIn("raw.githubusercontent.com", acquisition)
        self.assertIn("github_blob_sha1", acquisition)
        self.assertIn("acknowledge-no-redistribution-license", acquisition)
        self.assertFalse(any(transfer.rglob("*.c")))
        self.assertFalse(set(transfer.rglob("*.h")) - {transfer / "compatibility_header.h"})
        self.assertEqual(self.summary["redistribution"], "SOURCE_NOT_PACKAGED_NO_EXPLICIT_REPOSITORY_LICENSE_AT_FIXED_COMMIT")


if __name__ == "__main__":
    unittest.main()
