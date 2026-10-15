"""Current package verifier guards, using owned temporary fixtures only."""
import csv
import gzip
import importlib.util
import io
import json
import subprocess
import sys
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

    def review_fixture(self, options="manuscript,review,screen"):
        paper = self.root / "paper"
        (paper / "main.tex").write_text(
            "\\documentclass[" + options + "]{acmart}\n\\begin{document}\nowned fixture\n\\end{document}\n",
            encoding="utf-8")
        (self.root / "artifact/submission-materials-map.json").write_text(json.dumps({
            "main_review_candidate": "paper/main.pdf", "supplement": "paper/online-supplement.pdf",
        }), encoding="utf-8")
        return paper

    def recheck_module(self):
        with patch.object(sys, "path", [str(SCRIPT.parents[1] / "src"), *sys.path]):
            return importlib.import_module("tosem02.recheck")

    def test_unique_main_review_class_and_materials_mapping(self):
        paper = self.review_fixture()
        # A commented declaration is not an alternative active entry.
        source = (paper / "main.tex").read_text(encoding="utf-8")
        (paper / "main.tex").write_text("% \\documentclass[sigconf]{acmart}\n" + source,
                                       encoding="utf-8")
        self.assertTrue(all(PACKAGE.check_review_entry(self.root)[0].values()))
        self.assertTrue(all(self.recheck_module().check_paper_entry(self.root)[0].values()))
        self.assertNotIn("paper/submission-manuscript.tex", PACKAGE.REQUIRED)
        for name in ("paper/main.pdf", "paper/main.bbl", "paper/online-supplement.pdf"):
            self.assertIn(name, PACKAGE.REQUIRED)

    def test_bad_or_multiple_main_classes_are_rejected(self):
        for options in ("acmsmall,review,screen", "sigconf,review,screen", "manuscript,screen",
                        "manuscript,review=false,screen", "manuscript,review,screen,twocolumn",
                        "manuscript,review,review"):
            with self.subTest(options=options):
                self.review_fixture(options)
                checks = PACKAGE.check_review_entry(self.root)[0]
                self.assertFalse(checks["main_uses_initial_review_class"])
                self.assertFalse(self.recheck_module().check_paper_entry(self.root)[0]
                                 ["main_uses_initial_review_class"])
        paper = self.review_fixture()
        source = (paper / "main.tex").read_text(encoding="utf-8")
        (paper / "main.tex").write_text("\\documentclass{article}\n" + source, encoding="utf-8")
        self.assertFalse(PACKAGE.check_review_entry(self.root)[0]["main_uses_initial_review_class"])
        (paper / "main.tex").write_text("% \\documentclass[manuscript,review,screen]{acmart}\n",
                                       encoding="utf-8")
        self.assertFalse(PACKAGE.check_review_entry(self.root)[0]["main_uses_initial_review_class"])

    def test_duplicate_wrapper_family_and_second_article_are_rejected(self):
        paper = self.review_fixture()
        for suffix in ("tex", "pdf", "bbl", "aux", "blg", "log", "out"):
            with self.subTest(suffix=suffix):
                wrapper = paper / ("submission-manuscript." + suffix)
                wrapper.write_bytes(b"owned duplicate fixture")
                self.assertFalse(PACKAGE.check_review_entry(self.root)[0]["main_is_unique_review_entry"])
                self.assertEqual(PACKAGE.file_role("paper/" + wrapper.name), "duplicate-review-entry")
                wrapper.unlink()
        (paper / "review-copy.tex").write_text("\\documentclass{acmart}\n", encoding="utf-8")
        self.assertFalse(PACKAGE.check_review_entry(self.root)[0]["main_is_unique_review_entry"])

    def test_stale_wrapper_materials_mapping_is_rejected(self):
        self.review_fixture()
        (self.root / "artifact/submission-materials-map.json").write_text(json.dumps({
            "main_review_candidate": "paper/submission-manuscript.pdf",
            "supplement": "paper/online-supplement.pdf",
        }), encoding="utf-8")
        self.assertFalse(PACKAGE.check_review_entry(self.root)[0]["submission_map_uses_main"])

    def test_build_preflight_checks_class_and_duplicate_without_tex_execution(self):
        build_path = SCRIPT.parents[2] / "paper/build.sh"
        if not build_path.is_file():
            self.skipTest("optional sibling paper source is not present")
        build = build_path.read_text(encoding="utf-8")
        preflight = build.split("<<'PYENTRY'\n", 1)[1].split("\nPYENTRY", 1)[0]
        paper = self.review_fixture()

        def run_preflight():
            return subprocess.run([sys.executable, "-B", "-c", preflight], cwd=paper,
                                  text=True, capture_output=True, check=False)

        self.assertEqual(run_preflight().returncode, 0)
        self.review_fixture("acmsmall,review,screen")
        self.assertNotEqual(run_preflight().returncode, 0)
        self.review_fixture()
        (paper / "submission-manuscript.pdf").write_bytes(b"owned duplicate fixture")
        self.assertNotEqual(run_preflight().returncode, 0)

    def test_unique_entry_does_not_replace_required_input_checks(self):
        paper = self.review_fixture()
        (paper / "online-supplement.tex").write_text("owned supplement\n", encoding="utf-8")
        (paper / "acmart.cls").write_text("owned class fixture\n", encoding="utf-8")
        with (paper / "main.tex").open("a", encoding="utf-8") as stream:
            stream.write("\\input{science-method}\n")
        self.assertTrue(all(PACKAGE.check_review_entry(self.root)[0].values()))
        self.assertFalse(PACKAGE.check_paper_dependencies(self.root)[0])
        (paper / "science-method.tex").write_text("\\input{generated/numerical}\n", encoding="utf-8")
        passed, details = PACKAGE.check_paper_dependencies(self.root)
        self.assertFalse(passed)
        self.assertIn("generated/numerical.tex", details["missing_or_empty"])
        (paper / "generated").mkdir()
        (paper / "generated/numerical.tex").write_text("owned numerical input\n", encoding="utf-8")
        self.assertTrue(PACKAGE.check_paper_dependencies(self.root)[0])

    def test_visual_bindings_still_require_main_and_supplement(self):
        paper = self.review_fixture()
        for name in ("main", "online-supplement"):
            (paper / (name + ".pdf")).write_bytes(("owned " + name).encode("utf-8"))
        visual = {"pdfs": {name: {"sha256": PACKAGE.sha256(paper / (name + ".pdf"))}
                           for name in ("main", "online-supplement")}}
        visual["pdfs"]["submission-manuscript"] = {"sha256": "0" * 64}
        recheck = self.recheck_module()
        self.assertTrue(recheck.check_review_pdf_bindings(paper, visual))
        (paper / "main.pdf").write_bytes(b"changed owned fixture")
        self.assertFalse(recheck.check_review_pdf_bindings(paper, visual))
        self.assertFalse(recheck.check_review_pdf_bindings(paper, {"pdfs": {}}))

    def test_cli_recheck_uses_current_full_package_checker(self):
        module=self.recheck_module()
        expected={"verdict":"PASS","checks":{"owned_science":True,"unique_main":True}}
        checker=type('OwnedPackageChecker',(),{})()
        checker.audit_project=lambda root:expected
        with patch.object(module,'package_checker',return_value=checker):
            self.assertIs(module.recheck(self.root/'artifact'),expected)

    def test_cli_recheck_does_not_ignore_failed_package_gate(self):
        module=self.recheck_module()
        checker=type('OwnedPackageChecker',(),{})()
        checker.audit_project=lambda root:{"verdict":"FAIL","checks":{"owned_science":False}}
        with patch.object(module,'package_checker',return_value=checker):
            with self.assertRaisesRegex(RuntimeError,'owned_science'):
                module.recheck(self.root/'artifact')

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
