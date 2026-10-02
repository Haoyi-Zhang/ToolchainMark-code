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
        cls.audit = json.loads((cls.artifact / "audit" / "external_transfer_audit.json").read_text(encoding="utf-8"))

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

    def test_rows_and_audit_are_consistent(self) -> None:
        self.assertEqual(len(self._rows(self.results / "execution_rows.csv")), 120)
        self.assertEqual(len(self._rows(self.results / "sanitizer_rows.csv")), 12)
        self.assertEqual(self.audit["verdict"], "PASS")
        self.assertTrue(all(self.audit["checks"].values()))

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
