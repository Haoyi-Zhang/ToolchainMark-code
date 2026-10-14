"""Current package verifier guards, using owned temporary fixtures only."""
import csv
import gzip
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_package.py"
SPEC = importlib.util.spec_from_file_location("current_package_verifier", SCRIPT)
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class PackageIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="package-integrity-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "paper").mkdir()
        (self.root / "artifact/audit").mkdir(parents=True)
        (self.root / "paper/main.tex").write_text("owned fixture\n", encoding="utf-8")
        (self.root / "artifact/README.md").write_text("owned fixture\n", encoding="utf-8")

    def manifest(self, transforms=None):
        paths = [self.root / "paper/main.tex", self.root / "artifact/README.md"]
        rows = [
            {"path": path.relative_to(self.root).as_posix(), "sha256": PACKAGE.sha256(path),
             "bytes": str(path.stat().st_size),
             "mode": PACKAGE.publication_mode(path.relative_to(self.root).as_posix())}
            for path in paths
        ]
        if transforms:
            transforms(rows)
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=["path", "sha256", "bytes", "mode"])
        writer.writeheader()
        writer.writerows(rows)
        (self.root / PACKAGE.MANIFEST).write_text(output.getvalue(), encoding="utf-8")
        return paths

    def checked(self, paths):
        return PACKAGE.check_manifest(self.root, paths)[0]

    def test_exact_manifest_bytes_and_portable_roles(self):
        paths = self.manifest()
        self.assertTrue(all(self.checked(paths).values()))
        self.assertEqual(PACKAGE.publication_mode("paper/build.sh"), "0755")
        self.assertEqual(PACKAGE.publication_mode("paper/main.tex"), "0644")

    def test_missing_path_and_changed_bytes_are_rejected(self):
        paths = self.manifest(lambda rows: rows.pop())
        self.assertFalse(self.checked(paths)["manifest_exact_path_set"])
        paths = self.manifest()
        paths[0].write_text("tampered\n", encoding="utf-8")
        self.assertFalse(self.checked(paths)["manifest_sha256_and_bytes"])

    def test_bad_hash_role_duplicate_and_path_escape_are_rejected(self):
        paths = self.manifest(lambda rows: rows[0].update(sha256="0" * 64))
        self.assertFalse(self.checked(paths)["manifest_sha256_and_bytes"])
        self.manifest(lambda rows: rows[0].update(mode="0666"))
        self.assertFalse(self.checked(paths)["manifest_portable_role_modes"])
        self.manifest(lambda rows: rows.append(rows[0].copy()))
        self.assertFalse(self.checked(paths)["manifest_schema_and_safe_paths"])
        self.manifest(lambda rows: rows[0].update(path="../outside"))
        self.assertFalse(self.checked(paths)["manifest_schema_and_safe_paths"])

    def test_root_shape_and_actual_active_text_leak(self):
        paths = self.manifest()
        checks = PACKAGE.check_publication(self.root, paths, [], [])[0]
        self.assertTrue(checks["root_is_paper_and_artifact"])
        (self.root / "third").mkdir()
        self.assertFalse(PACKAGE.check_publication(self.root, paths, [], [])[0]["root_is_paper_and_artifact"])
        (self.root / "third").rmdir()
        paths[0].write_text("/home/" + "oai/private\n", encoding="utf-8")
        self.assertFalse(PACKAGE.check_publication(self.root, paths, [], [])[0]
                         ["public_source_has_no_private_runtime_paths"])

    def test_known_evidence_and_compiler_files_not_blanket_debris(self):
        self.assertEqual(PACKAGE.file_role("paper/main.aux"), "compiler-auxiliary")
        self.assertEqual(PACKAGE.file_role("artifact/results/native-linux/evidence.zip"),
                         "scientific-container")
        self.assertEqual(PACKAGE.file_role("artifact/results/current-native/native-tests.log"),
                         "scientific-log")
        self.assertEqual(PACKAGE.file_role("artifact/results/unknown.zip"),
                         "unexpected-container-or-auxiliary")
        self.assertFalse(PACKAGE.safe_manifest_path("C:/outside"))
        self.assertFalse(PACKAGE.safe_manifest_path("paper/../outside"))

    def test_missing_and_corrupt_owned_archive_are_rejected(self):
        with patch.object(PACKAGE, "RESULT_CONTAINERS", {"artifact/results/owned.zip"}):
            passed, errors = PACKAGE.check_archives(self.root)
            self.assertFalse(passed)
            self.assertIn("absent", errors[0])
            (self.root / "artifact/results").mkdir()
            (self.root / "artifact/results/owned.zip").write_bytes(b"not a zip")
            self.assertFalse(PACKAGE.check_archives(self.root)[0])

    def test_owned_raw_schema_and_summary_count_are_required(self):
        relative = "artifact/results/owned-test/raw.jsonl.gz"
        path = self.root / relative
        path.parent.mkdir(parents=True)
        summary = path.parent / "summary.json"
        summary.write_text(json.dumps({"rows": 1, "verdicts": {"SATISFIED": 1}}),
                           encoding="utf-8")
        with patch.object(PACKAGE, "RESULT_CONTAINERS", {relative}):
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                stream.write(json.dumps({"verdict": "SATISFIED"}) + "\n")
            self.assertFalse(PACKAGE.check_archives(self.root)[0])
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                stream.write(json.dumps({"identity": [], "verdict": "SATISFIED",
                                         "admission": {}, "observations": {}, "builds": []}) + "\n")
            self.assertTrue(PACKAGE.check_archives(self.root)[0])
            summary.write_text(json.dumps({"rows": 2, "verdicts": {"SATISFIED": 2}}),
                               encoding="utf-8")
            self.assertFalse(PACKAGE.check_archives(self.root)[0])

    def test_missing_literally_consumed_paper_input_is_rejected(self):
        (self.root / "paper/online-supplement.tex").write_text("fixture\n", encoding="utf-8")
        (self.root / "paper/main.tex").write_text(
            "\\input{Ustmry.fd}\n\\input{figures/missing}\n", encoding="utf-8")
        passed, details = PACKAGE.check_paper_dependencies(self.root)
        self.assertFalse(passed)
        self.assertIn("figures/missing.tex", details["missing_or_empty"])
        (self.root / "paper/figures").mkdir()
        (self.root / "paper/figures/missing.tex").write_text("fixture\n", encoding="utf-8")
        self.assertTrue(PACKAGE.check_paper_dependencies(self.root)[0])

    def test_child_verdict_cannot_override_nonzero_exit(self):
        completed = PACKAGE.subprocess.CompletedProcess([], 1, json.dumps({"verdict": "PASS"}), "")
        with patch.object(PACKAGE.subprocess, "run", return_value=completed):
            passed, details = PACKAGE.run_readonly_check(self.root / "artifact", "scripts/owned.py", [])
        self.assertFalse(passed)
        self.assertEqual(details["exit"], 1)


if __name__ == "__main__":
    unittest.main()
