#!/usr/bin/env python3
"""Read-only integrity check for the current paper/artifact publication tree.

This checks file identity, roles, required data, paper inputs, and current
read-only scientific validators. It does not certify external citations,
compile a paper, execute a native campaign, or rewrite historical audits.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "artifact/audit/project_manifest.csv"
ACTIVE_SHELL = {"paper/build.sh"} | {
    "artifact/scripts/" + name for name in (
        "build_paper_optional.sh", "recheck.sh", "run_base.sh",
        "run_complete.sh", "run_full.sh", "verify.sh",
        "verify_release.sh", "verify_science.sh"
    )
}
TEX_STEMS = {"main", "online-supplement"}
TEX_AUX = {".aux", ".blg", ".log", ".out", ".toc", ".fls", ".fdb_latexmk", ".synctex.gz"}
NATIVE_BASE = "artifact/results/current-native/"
RESULT_CONTAINERS = {
    NATIVE_BASE + prefix + name + ".csv.gz"
    for prefix in ("", "mirror/") for name in ("first", "second")
} | {
    "artifact/results/native-linux/evidence.zip",
    "artifact/results/repair-replay/evidence.zip",
    "artifact/results/owned-native-full-20261014-001/raw.jsonl.gz",
    "artifact/results/owned-native-small-20261014-001/raw.jsonl.gz",
}
RESULT_LOGS = {
    NATIVE_BASE + prefix + name + ".log"
    for prefix in ("", "mirror/")
    for name in ("native-tests", "native-campaign", "native-dependencies")
}
REQUIRED = {
    "artifact/LICENSE", "paper/ACM-LICENSE.txt",
    "artifact/README.md", "artifact/REPRODUCIBILITY.md",
    "artifact/RESEARCH-PROTOCOL.md", "artifact/scripts/verify_package.py",
    "artifact/scripts/verify_science.py", "artifact/evaluation/verify_native_records.py",
    "artifact/results/current-native/native-inputs.json",
    "artifact/results/current-native/provenance.json",
    "artifact/results/current-native/transport.json",
    "artifact/results/current-native/historical-source-recovery.json",
    "artifact/results/current-native/source-snapshot/scripts/derive_admission_study.py",
    "artifact/results/current-native/historical-source-recovery/scripts/verify_package.py",
    "artifact/results/current-native/historical-source-recovery/tests/test_evidence_catalog.py",
    "paper/main.tex", "paper/main.pdf", "paper/main.bbl",
    "paper/online-supplement.tex", "paper/online-supplement.pdf",
    "artifact/submission-materials-map.json",
    "paper/references.bib", "paper/generated/admission-results.tex",
    "paper/generated/admission-overview.tex",
} | RESULT_CONTAINERS | RESULT_LOGS | ACTIVE_SHELL

PRIVATE_PATH = re.compile(r"/mnt/data|/home/oai|sandbox:", re.I)
PROCESS_TRACE = re.compile(r"chatgpt|openai|system prompt|chain of thought|assistant response|private prompt", re.I)
HEX256 = re.compile(r"[0-9a-f]{64}\Z")
TEX_DEPENDENCY = re.compile(
    r"\\(input|includegraphics|bibliography|bibliographystyle|documentclass)"
    r"(?:\[[^\]]*\])?\{([^{}]+)\}")
EXTERNAL_TEX_INPUTS = {"Ustmry.fd"}  # resolved from the TeX installation


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_manifest_path(value: str) -> bool:
    if not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts and \
        path.as_posix() == value


def publication_mode(relative: str) -> str:
    """Declared portable role, not the host OS's writable-bit observation."""
    return "0755" if relative in ACTIVE_SHELL else "0644"


def file_role(relative: str) -> str:
    """Return a role or a concrete invalid/debris label."""
    path = PurePosixPath(relative)
    if len(path.parts) == 2 and path.parts[0] == "paper" and \
            path.name.casefold().startswith("submission-manuscript."):
        return "duplicate-review-entry"
    if any(part in {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules"}
           for part in path.parts):
        return "cache-or-repository-internals"
    if relative.endswith("~") or path.suffix in {".pyc", ".pyo", ".bak", ".tmp"}:
        return "temporary-or-backup"
    if relative in RESULT_CONTAINERS:
        return "scientific-container"
    if relative in RESULT_LOGS:
        return "scientific-log"
    if path.parts and path.parts[0] == "paper" and len(path.parts) == 2:
        for suffix in sorted(TEX_AUX, key=len, reverse=True):
            if path.name.endswith(suffix) and path.name.removesuffix(suffix) in TEX_STEMS:
                return "compiler-auxiliary"
    if path.suffix in {".zip", ".gz", ".log", ".aux", ".blg", ".out", ".toc", ".fls"} or \
            relative.endswith((".fdb_latexmk", ".synctex.gz")):
        return "unexpected-container-or-auxiliary"
    return "ordinary"


def public_text(relative: str) -> bool:
    """Scan active prose/source, not historical data or the scanner's own literals."""
    path = PurePosixPath(relative)
    if relative == "artifact/scripts/verify_package.py":
        return False
    if relative.startswith(("artifact/results/", "artifact/audit/", "paper/evidence/")):
        return False
    if path.name in {"ACM-LICENSE.txt", "LICENSE"}:
        return False
    if relative.startswith("paper/"):
        return path.suffix in {".tex", ".bib", ".md", ".py", ".sh"}
    return path.suffix in {".md", ".tex", ".py", ".sh", ".json", ".csv", ".yml", ".yaml"}


def inventory(root: Path):
    items = sorted(root.rglob("*"))
    links = [p.relative_to(root).as_posix() for p in items
             if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())]
    files = [p for p in items if p.is_file() and not p.is_symlink()
             and not (hasattr(p, "is_junction") and p.is_junction())]
    inode = {}
    for path in files:
        info = path.stat()
        inode.setdefault((info.st_dev, info.st_ino), []).append(path.relative_to(root).as_posix())
    shared = [paths for paths in inode.values() if len(paths) > 1]
    return files, links, shared


def check_manifest(root: Path, files: list[Path]):
    manifest = root / MANIFEST
    expected = {p.relative_to(root).as_posix(): p for p in files if p != manifest}
    issues = {"schema": [], "missing": [], "extra": [], "content": [], "role_mode": []}
    if not manifest.is_file():
        issues["schema"].append("manifest absent")
        rows = []
    else:
        try:
            with manifest.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != ["path", "sha256", "bytes", "mode"]:
                    issues["schema"].append("manifest header differs")
                rows = list(reader)
        except (OSError, UnicodeError, csv.Error) as error:
            issues["schema"].append(type(error).__name__)
            rows = []
    by_path = {}
    for row in rows:
        path = row.get("path")
        if not isinstance(path, str) or not safe_manifest_path(path) or path in by_path or \
                not HEX256.fullmatch(row.get("sha256") or "") or \
                not (row.get("bytes") or "").isdigit() or row.get(None):
            issues["schema"].append("invalid or duplicate manifest row")
            continue
        by_path[path] = row
        if row.get("mode") != publication_mode(path):
            issues["role_mode"].append(path)
    issues["missing"] = sorted(set(expected) - set(by_path))
    issues["extra"] = sorted(set(by_path) - set(expected))
    for relative, path in expected.items():
        row = by_path.get(relative)
        if row and (row["sha256"] != sha256(path) or int(row["bytes"]) != path.stat().st_size):
            issues["content"].append(relative)
    checks = {
        "manifest_schema_and_safe_paths": not issues["schema"],
        "manifest_exact_path_set": not issues["missing"] and not issues["extra"],
        "manifest_sha256_and_bytes": not issues["content"],
        "manifest_portable_role_modes": not issues["role_mode"],
    }
    return checks, {"manifest_rows": len(rows), "expected_rows": len(expected),
                    "manifest_issues": issues}


def check_publication(root: Path, files: list[Path], links: list[str], shared: list[list[str]]):
    names = {p.name for p in root.iterdir()}
    relative = {p.relative_to(root).as_posix(): p for p in files}
    invalid_roles = {name: file_role(name) for name in relative
                     if file_role(name) in {"cache-or-repository-internals",
                                            "temporary-or-backup",
                                            "unexpected-container-or-auxiliary",
                                            "duplicate-review-entry"}}
    missing = sorted(name for name in REQUIRED if name not in relative or relative[name].stat().st_size == 0)
    private = []
    process = []
    for name, path in relative.items():
        if not public_text(name):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            private.append(name + ": unreadable text")
            continue
        if PRIVATE_PATH.search(source):
            private.append(name)
        if PROCESS_TRACE.search(source):
            process.append(name)
    shell_shape = [name for name in ACTIVE_SHELL if name in relative and
                   not relative[name].read_bytes().startswith(b"#!/usr/bin/env bash")]
    checks = {
        "root_is_paper_and_artifact": names == {"paper", "artifact"},
        "no_symlinks_or_junctions": not links,
        "no_shared_hardlinks": not shared,
        "file_roles_valid": not invalid_roles,
        "public_source_has_no_private_runtime_paths": not private,
        "public_source_has_no_process_trace": not process,
        "required_sources_licenses_and_evidence_present": not missing,
        "active_shell_scripts_have_expected_shebang": not shell_shape,
    }
    exec_observation = "not observable on Windows; portable role declared in manifest"
    if os.name != "nt":
        no_exec = [name for name in ACTIVE_SHELL if name in relative and
                   not (relative[name].stat().st_mode & stat.S_IXUSR)]
        checks["active_shell_scripts_executable_on_posix"] = not no_exec
        exec_observation = {"missing_user_execute_bit": no_exec}
    return checks, {
        "root_entries": sorted(names), "links": links, "shared_hardlinks": shared,
        "invalid_roles": invalid_roles, "missing_or_empty_required": missing,
        "private_paths_in_active_text": private, "process_traces_in_active_text": process,
        "shell_shape_errors": shell_shape, "shell_executable_observation": exec_observation,
    }


def check_archives(root: Path):
    errors = []
    for relative in sorted(RESULT_CONTAINERS):
        path = root / relative
        if not path.is_file():
            errors.append(relative + ": absent")
            continue
        try:
            if relative.endswith(".zip"):
                with zipfile.ZipFile(path) as archive:
                    names = archive.namelist()
                    if not names or len(names) != len(set(names)) or archive.testzip() is not None:
                        raise ValueError("empty, duplicate or corrupt ZIP entries")
                    if any(not safe_manifest_path(name.rstrip("/")) for name in names):
                        raise ValueError("unsafe ZIP member path")
                    for name in ("native-study/first.csv", "native-study/second.csv"):
                        if name not in names:
                            raise ValueError("missing native matrix " + name)
                        if archive.getinfo(name).file_size == 0:
                            raise ValueError("empty native matrix " + name)
            elif relative.endswith("raw.jsonl.gz"):
                summary = json.loads((path.parent / "summary.json").read_text(encoding="utf-8"))
                verdicts = Counter()
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    for line in stream:
                        row = json.loads(line)
                        if not isinstance(row, dict) or not isinstance(row.get("identity"), list) or \
                                not isinstance(row.get("verdict"), str) or \
                                not isinstance(row.get("admission"), dict) or \
                                not isinstance(row.get("observations"), dict) or \
                                not isinstance(row.get("builds"), list):
                            raise ValueError("owned raw row schema differs")
                        verdicts[row["verdict"]] += 1
                if not verdicts or sum(verdicts.values()) != summary["rows"] or \
                        dict(verdicts) != summary["verdicts"]:
                    raise ValueError("owned raw count/verdicts differ from summary")
            else:
                with gzip.open(path, "rb") as stream:
                    if not stream.read(1):
                        raise ValueError("empty native matrix")
                    for _ in iter(lambda: stream.read(1 << 20), b""):
                        pass
        except (OSError, UnicodeError, EOFError, ValueError, KeyError,
                json.JSONDecodeError, zipfile.BadZipFile, RuntimeError) as error:
            errors.append(relative + ": " + str(error))
    return not errors, errors


def check_references(root: Path):
    """Current local citation structure only; no external support certificate."""
    try:
        source = root / "artifact/scripts/audit_references.py"
        spec = importlib.util.spec_from_file_location("package_reference_structure", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        paper = root / "paper"
        tex = (paper / "main.tex").read_text(encoding="utf-8")
        bib = module.parse_bib((paper / "references.bib").read_text(encoding="utf-8"))
        records = json.loads((paper / "evidence/reference_records.json").read_text(encoding="utf-8"))
        receipts = json.loads((paper / "evidence/reference_review_20260923.json").read_text(encoding="utf-8"))
        shape = module.structural_audit(tex, bib, records, receipts)
        keys = [r["citation_key"] for r in records]
        receipt_keys = [r["citation_key"] for r in receipts]
        def norm(value):
            return re.sub(r"[^a-z0-9]", "", module.strip_tex(str(value)).lower())
        metadata = all(
            norm(bib[key].get("title", "")) == norm(record["title"]) and
            bib[key].get("doi", "").casefold() == record["doi"].casefold() and
            str(bib[key].get("year", "")) == str(record["year"])
            for key, record in ((r["citation_key"], r) for r in records)
        )
        required_shape = (
            len(keys) == len(set(keys)) == len(receipts) == len(bib) and
            len(receipt_keys) == len(set(receipt_keys)) and
            set(keys) == set(receipt_keys) == set(bib) and
            shape["missing_bibliography_keys"] == [] and
            shape["uncited_bibliography_keys"] == [] and
            shape["doi_records_unique"] and metadata
        )
        return required_shape, {"records": len(records), "citations": shape["citation_commands"],
                                "fresh_record_checks_reported_by_receipts": shape["fresh_record_checks"],
                                "external_support_certified": False}
    except (OSError, UnicodeError, ValueError, KeyError, IndexError,
            TypeError, AttributeError) as error:
        return False, {"error": type(error).__name__ + ": " + str(error)}


def check_review_entry(root: Path):
    """Require one acmart review article and no duplicate submission wrapper."""
    paper = root / "paper"
    errors = []

    def uncommented(path):
        return re.sub(r"(?<!\\)%[^\n]*", "", path.read_text(encoding="utf-8"))

    try:
        main = uncommented(paper / "main.tex").split(r"\begin{document}", 1)[0]
    except (OSError, UnicodeError) as error:
        main = ""
        errors.append("main.tex: " + type(error).__name__)
    classes = re.findall(r"\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}", main)
    options = [value.strip() for value in classes[0][0].split(",")] if len(classes) == 1 else []
    review_class = len(re.findall(r"\\documentclass\b", main)) == len(classes) == 1 and \
        classes[0][1].strip() == "acmart" and len(options) == 3 and \
        set(options) == {"manuscript", "review", "screen"}
    duplicates = {path.name for path in paper.iterdir()
                  if path.name.casefold().startswith("submission-manuscript.")} if paper.is_dir() else set()
    for path in paper.glob("*.tex"):
        if path.name in {"main.tex", "online-supplement.tex"}:
            continue
        try:
            if re.search(r"\\documentclass\b", uncommented(path)):
                duplicates.add(path.name)
        except (OSError, UnicodeError) as error:
            errors.append(path.name + ": " + type(error).__name__)
    try:
        materials = json.loads((root / "artifact/submission-materials-map.json").read_text(encoding="utf-8"))
        mapped = materials.get("main_review_candidate") == "paper/main.pdf" and \
            materials.get("supplement") == "paper/online-supplement.pdf" and \
            "journal_layout" not in materials
    except (OSError, UnicodeError, ValueError, AttributeError) as error:
        mapped = False
        errors.append("submission-materials-map.json: " + type(error).__name__)
    return {
        "main_uses_initial_review_class": review_class,
        "main_is_unique_review_entry": not duplicates and not errors,
        "submission_map_uses_main": mapped,
    }, {"duplicate_review_files": sorted(duplicates), "entry_read_errors": errors,
        "main_documentclasses": classes}


def check_paper_dependencies(root: Path):
    """Check literal local TeX consumers, not installation-provided font files."""
    paper = root / "paper"
    pending = [paper / "main.tex", paper / "online-supplement.tex"]
    seen = set()
    missing = []
    unsafe = []
    while pending:
        source = pending.pop()
        if source in seen:
            continue
        seen.add(source)
        if not source.is_file() or source.stat().st_size == 0:
            missing.append(source.relative_to(paper).as_posix())
            continue
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            missing.append(source.relative_to(paper).as_posix() + ": unreadable")
            continue
        for command, raw in TEX_DEPENDENCY.findall(text):
            for item in raw.split(",") if command == "bibliography" else (raw,):
                item = item.strip()
                if command == "input" and item in EXTERNAL_TEX_INPUTS:
                    continue
                relative = PurePosixPath(item)
                if not safe_manifest_path(item):
                    unsafe.append(source.relative_to(paper).as_posix() + ":" + item)
                    continue
                if command == "input" and not relative.suffix:
                    relative = relative.with_suffix(".tex")
                elif command == "bibliography":
                    relative = relative.with_suffix(".bib")
                elif command == "bibliographystyle":
                    relative = relative.with_suffix(".bst")
                elif command == "documentclass":
                    relative = relative.with_suffix(".cls")
                target = paper.joinpath(*relative.parts)
                if not target.is_file() or target.stat().st_size == 0:
                    missing.append(relative.as_posix())
                elif command == "input":
                    pending.append(target)
    return not (missing or unsafe), {"missing_or_empty": sorted(set(missing)),
                                     "unsafe_literal_paths": sorted(set(unsafe)),
                                     "scanned_tex_sources": len(seen),
                                     "external_installed_font_inputs": sorted(EXTERNAL_TEX_INPUTS)}


def run_readonly_check(artifact: Path, script: str, extra: list[str]):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(artifact / "src") + os.pathsep + env.get("PYTHONPATH", "")
    try:
        completed = subprocess.run(
            [sys.executable, "-B", str(artifact / script), *extra],
            cwd=artifact, env=env, text=True, capture_output=True, timeout=120, check=False)
        report = json.loads(completed.stdout)
        passed = completed.returncode == 0 and report.get("verdict") == "PASS"
        if script == "evaluation/verify_native_records.py":
            passed = passed and report.get("paper_checked") is True and \
                     report.get("certifies_v3_native_execution") is False and \
                     report.get("historical_source", {}).get("historical_native_input_files") == 71
        return passed, {"exit": completed.returncode, "verdict": report.get("verdict"),
                        "scope": report.get("scope"), "stderr": completed.stderr[-1000:]}
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return False, {"error": type(error).__name__ + ": " + str(error)}


def audit_project(root: Path):
    root = root.resolve()
    files, links, shared = inventory(root)
    checks, details = check_publication(root, files, links, shared)
    manifest_checks, manifest_details = check_manifest(root, files)
    checks.update(manifest_checks)
    details.update(manifest_details)
    archives_ok, archive_errors = check_archives(root)
    checks["required_evidence_archives_readable"] = archives_ok
    details["archive_errors"] = archive_errors
    entry_checks, entry_details = check_review_entry(root)
    checks.update(entry_checks)
    details["review_entry"] = entry_details
    references_ok, references = check_references(root)
    checks["current_local_reference_structure"] = references_ok
    details["reference_structure"] = references
    dependencies_ok, dependencies = check_paper_dependencies(root)
    checks["literal_local_paper_dependencies_present"] = dependencies_ok
    details["paper_dependencies"] = dependencies
    artifact = root / "artifact"
    for key, script, extra in (
        ("retained_science_recomputed_now", "scripts/verify_science.py", []),
        ("historical_native_records_and_paper_inputs_checked_now",
         "evaluation/verify_native_records.py", ["--paper", str(root / "paper")]),
    ):
        checks[key], details[key] = run_readonly_check(artifact, script, extra)
    result = {
        "schema_version": "3.0",
        "project_root": str(root),
        "checks": checks,
        "details": details,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "scope": "Current paper/artifact package, byte manifest, local citation structure, "
                 "retained data-only science and historical native-source binding. "
                 "No TeX build, native campaign, external-source support certification "
                 "or validation of PDF freshness."
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", nargs="?", type=Path, default=ROOT)
    parser.add_argument("--write-audit", action="store_true",
                        help="Retired: historical audit/package_audit.json is immutable")
    args = parser.parse_args(argv)
    if args.write_audit:
        parser.error("historical package_audit.json is immutable; redirect stdout outside the project")
    result = audit_project(args.project_root)
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
