"""Benign current-v3 evidence guards; never invoke native producers."""
import copy
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_native_execution import (
    DATA, ROOT, COHERENCE, LOCALITY, FIELD_NAMES,
    check_mr10_row, compare_non_timing, data_path, parse_duration,
    verify_matrix, verify_members, verify_source_inputs,
)


class NativeExecutionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.provenance = json.loads((DATA / "provenance.json").read_text(encoding="utf-8"))

    def test_all_published_members_and_source_inputs_match(self):
        self.assertEqual(verify_members(DATA, self.provenance), 40)
        self.assertEqual(verify_source_inputs(DATA, ROOT, self.provenance), 71)

    def test_source_byte_binding_cannot_be_relabelled(self):
        source = json.loads((DATA / "source-inputs.json").read_text(encoding="utf-8"))
        source["paths"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="native-v3-input-test-") as temporary:
            root = Path(temporary)
            (root / "source-inputs.json").write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input digest differs"):
                verify_source_inputs(root, ROOT, self.provenance)

    def test_incomplete_input_domain_is_rejected(self):
        source = json.loads((DATA / "source-inputs.json").read_text(encoding="utf-8"))
        source["paths"].pop()
        with tempfile.TemporaryDirectory(prefix="native-v3-input-test-") as temporary:
            root = Path(temporary)
            (root / "source-inputs.json").write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input count differs"):
                verify_source_inputs(root, ROOT, self.provenance)

    def test_preserved_producer_bytes_remain_bound_to_original_manifest(self):
        with tempfile.TemporaryDirectory(prefix="native-preserved-input-test-") as temporary:
            root=Path(temporary)
            shutil.copy2(DATA/'source-inputs.json',root/'source-inputs.json')
            shutil.copytree(DATA/'source-snapshot',root/'source-snapshot')
            self.assertEqual(verify_source_inputs(root,ROOT,self.provenance),71)
            preserved=root/'source-snapshot/src/tosem02/recheck.py'
            preserved.write_bytes(preserved.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'input digest differs'):
                verify_source_inputs(root,ROOT,self.provenance)

    def test_wrong_run_head_is_rejected(self):
        bad = copy.deepcopy(self.provenance)
        bad["run_records"]["primary"]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "run binding differs"):
            verify_members(DATA, bad)

    def test_mr10_requires_complete_true_v3_facts_and_snapshots(self):
        admission = {name: True for name in COHERENCE | LOCALITY}
        observations = {
            "integrity_intervention": {name: True for name in LOCALITY},
            "integrity_snapshots": {
                "source": {"bytes": 10, "sha256": "1" * 64},
                "followup": {"bytes": 10, "sha256": "2" * 64},
            },
        }
        check_mr10_row({}, admission, observations)
        partial = dict(admission)
        partial.pop("followup_snapshot_current")
        with self.assertRaisesRegex(ValueError, "complete v3 facts"):
            check_mr10_row({}, partial, observations)
        stale = copy.deepcopy(observations)
        stale["integrity_snapshots"]["followup"]["sha256"] = "1" * 64
        with self.assertRaisesRegex(ValueError, "distinct snapshots"):
            check_mr10_row({}, admission, stale)
        changed = dict(admission)
        changed["checksum_material_changed"] = False
        with self.assertRaisesRegex(ValueError, "unsatisfied v3 fact"):
            check_mr10_row({}, changed, observations)

    def test_snapshot_byte_counts_are_strict_positive_integers(self):
        admission = {name: True for name in COHERENCE | LOCALITY}
        observations = {
            "integrity_intervention": {name: True for name in LOCALITY},
            "integrity_snapshots": {
                "source": {"bytes": 10, "sha256": "1" * 64},
                "followup": {"bytes": 10, "sha256": "2" * 64},
            },
        }
        for label in ("source", "followup"):
            for bad in (True, False, 0, -1, -20, 1.0, "1", None):
                with self.subTest(label=label, bad=bad):
                    altered = copy.deepcopy(observations)
                    altered["integrity_snapshots"][label]["bytes"] = bad
                    with self.assertRaisesRegex(ValueError, "snapshot record malformed"):
                        check_mr10_row({}, admission, altered)

    def test_duration_requires_finite_positive_number(self):
        self.assertEqual(parse_duration("0.125"), 0.125)
        for bad in ("nan", "inf", "+inf", "-inf", "1e999", "0", "-0", "-1", "not-a-number"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_duration(bad)

    def _mutate_full_published_matrix(self, predicate, change, expected_error):
        source = DATA / "primary/first.csv"
        with source.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = list(reader)
        target = next(row for row in rows if predicate(row))
        change(target)
        with tempfile.TemporaryDirectory(prefix="native-v3-matrix-test-") as temporary:
            path = Path(temporary) / "mutated.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, expected_error):
                verify_matrix(path)

    def test_full_matrix_gate_rejects_infinite_duration(self):
        self._mutate_full_published_matrix(
            lambda row: row["defect_id"] == "CLEAN" and row["relation_id"] == "MR01",
            lambda row: row.__setitem__("duration_seconds", "inf"),
            "Native duration must be finite and positive",
        )

    def test_full_matrix_gate_rejects_boolean_snapshot_bytes(self):
        def change(row):
            observations = json.loads(row["observations_json"])
            observations["integrity_snapshots"]["source"]["bytes"] = True
            row["observations_json"] = json.dumps(observations, sort_keys=True)

        self._mutate_full_published_matrix(
            lambda row: row["relation_id"] == "MR10" and row["verdict"] != "INADMISSIBLE",
            change,
            "MR10 snapshot record malformed",
        )

    def test_non_timing_comparison_is_exact(self):
        row = {field: "x" for field in FIELD_NAMES}
        row.update(host="H01-gcd.c", carrier="string", defect_id="M01", relation_id="MR01")
        later = dict(row, duration_seconds="2")
        self.assertEqual(compare_non_timing([row], [later]), 11)
        later["verdict"] = "different"
        with self.assertRaisesRegex(ValueError, "non-timing observations differ"):
            compare_non_timing([row], [later])

    def test_member_path_escape_is_rejected(self):
        for relative in ("../first.csv", "/absolute.csv", "C:/absolute.csv", "..\\first.csv"):
            with self.subTest(relative=relative):
                with self.assertRaisesRegex(ValueError, "Unsafe evidence path"):
                    data_path(DATA, relative)


if __name__ == "__main__":
    unittest.main()
