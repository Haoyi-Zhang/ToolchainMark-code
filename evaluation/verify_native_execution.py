"""Read-only verification of the published complete current-v3 native records.

This verifies recorded bytes, the 71 recorded producer inputs, row/admission
semantics, reruns, and data-only rederivation. It does not compile or execute
native subjects, contact GitHub, or write into the artifact tree.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/native-execution"
sys.path.insert(0, str(ROOT / "src"))
from tosem02.study_coverage import require_study_coverage

EXPECTED_RUNS = {
    "primary": {
        "repository": "Haoyi-Zhang/ToolchainMark",
        "run_id": 38624209055,
        "job_id": 116059121152,
        "head_sha": "9c82a7dd69c8138c5ebcca818b5c7f4475509155",
        "artifact_id": 11923959918,
        "original_zip_bytes": 637722,
        "original_zip_sha256": "5bd2fb80f41f85b28cf88086aeab6a597b5f499224ce84fb29f6ae44bcda3793",
        "first_sha256": "4836112e5a3ab3fae7f9dc6a6a4503c04f70982a18a4609be238903ee606be47",
        "second_sha256": "6c35a910194d5e5042e01dfb6acf70cfc4481ceddde0603d5cb8e6f0de237ff4",
    },
    "mirror": {
        "repository": "Haoyi-Zhang/ToolchainMark-code",
        "run_id": 38624220772,
        "job_id": 116059160214,
        "head_sha": "f681510ac5553eff8bdfdfe1013bd7671093ffec",
        "artifact_id": 11923829435,
        "original_zip_bytes": 643588,
        "original_zip_sha256": "4cca934c6ba0e039fac81735db9a9446282837dc5765b383c55af8243465e634",
        "first_sha256": "6b38acf9217b8b38344693aa6a7ef94496f241985c15d93c80004be12930faaf",
        "second_sha256": "7b7c06843051ddb2c80f347ed5063fa656f720b9fcd732ccf4c3c49dd0deefca",
    },
}
SHARED_TREE = "a8b749feb4df9f78ac00828bc7512951e1cde851"
CSV_DERIVED = {
    "admission_failures.csv", "bootstrap.csv", "carrier_holdout.csv",
    "class_holdout.csv", "legacy_transitions.csv", "operator_holdout.csv",
    "relation_outcomes.csv", "suites.csv", "unit_outcomes.csv",
}
JSON_DERIVED = {
    "bootstrap_summary.json", "paired_comparison.json", "rerun_comparison.json",
    "scientific_checks.json", "summary.json",
}
RUN_FILES = {
    "first.csv", "second.csv", "native-tests.txt", "native-campaign.txt",
    "native-dependencies.txt", "native-environment.json",
} | {"derived/" + name for name in CSV_DERIVED | JSON_DERIVED}
FIELD_NAMES = (
    "host", "host_sha256", "carrier", "defect_id", "relation_id", "verdict",
    "exposed", "reason", "phase", "admission_json", "observations_json",
    "duration_seconds",
)
KEY_FIELDS = ("host", "carrier", "defect_id", "relation_id")
COHERENCE = {
    "source_snapshot_matches_request", "followup_snapshot_current",
    "followup_unchanged_during_extraction",
}
LOCALITY = {
    "nonintervened_payload_preserved", "checksum_material_changed",
    "nonchecksum_material_preserved",
}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GIT_BLOB = re.compile(r"[0-9a-f]{40}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob(path):
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def data_path(base, relative):
    path = PurePosixPath(relative)
    require(not path.is_absolute() and path.parts and ".." not in path.parts
            and "\\" not in relative and ":" not in relative,
            "Unsafe evidence path: " + relative)
    target = base.joinpath(*path.parts)
    require(target.resolve().is_relative_to(base.resolve()),
            "Evidence path escapes root: " + relative)
    return target


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fields = tuple(reader.fieldnames or ())
        rows = list(reader)
    require(all(None not in row and all(value is not None for value in row.values())
                for row in rows), "Malformed CSV row: " + str(path))
    return fields, rows


def current_native_paths(source_root):
    names = set()
    for prefix in ("src", "hosts", "scripts", "specs", "tests"):
        for path in (source_root / prefix).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                names.add(path.relative_to(source_root).as_posix())
    workflow = source_root / ".github/workflows/native-compiler-campaign.yml"
    if workflow.is_file():
        names.add(".github/workflows/native-compiler-campaign.yml")
    return names


def verify_source_inputs(data_root, source_root, provenance):
    source_map = json.loads((data_root / "source-inputs.json").read_text(encoding="utf-8"))
    require(source_map["path_count"] == 71 and len(source_map["paths"]) == 71,
            "Current native input count differs")
    require(source_map["shared_git_tree"] == SHARED_TREE == provenance["shared_git_tree"],
            "Current native Git tree differs")
    require(source_map["primary_head_sha"] == EXPECTED_RUNS["primary"]["head_sha"]
            and source_map["mirror_head_sha"] == EXPECTED_RUNS["mirror"]["head_sha"],
            "Current native run heads differ")
    names = [entry["path"] for entry in source_map["paths"]]
    require(len(set(names)) == 71 and set(names) == current_native_paths(source_root),
            "Current 71-path native input domain differs")
    for entry in source_map["paths"]:
        name = entry["path"]
        require(name == ".github/workflows/native-compiler-campaign.yml" or
                PurePosixPath(name).parts[0] in {"src", "hosts", "scripts", "specs", "tests"},
                "Invalid current native input scope: " + name)
        def matches(path):
            return path.is_file() and path.stat().st_size == entry["bytes"] and \
                GIT_BLOB.fullmatch(entry["git_blob_sha1"]) is not None and \
                git_blob(path) == entry["git_blob_sha1"] and digest(path) == entry["sha256"]
        current = data_path(source_root, name)
        preserved = data_path(data_root / "source-snapshot", name)
        # Packaging maintenance may change a producer input after measurement.
        # Its preserved bytes must still match every original recorded identity.
        path = current if matches(current) else preserved
        require(matches(path),
                "Current native input digest differs: " + name)
    return len(names)


def verify_members(data_root, provenance):
    require(provenance["protocol"] == "evidence-gated-v3-snapshot-coherence"
            and provenance["shared_git_tree"] == SHARED_TREE
            and provenance["source_inputs"] == "source-inputs.json",
            "Native execution provenance identity differs")
    require(set(provenance["run_records"]) == set(EXPECTED_RUNS),
            "Native run pair differs")
    for label, pinned in EXPECTED_RUNS.items():
        record = provenance["run_records"][label]
        for field in ("repository", "run_id", "job_id", "head_sha", "artifact_id",
                      "original_zip_bytes", "original_zip_sha256"):
            require(record[field] == pinned[field], label + " native run binding differs: " + field)
        require(record["artifact_name"] == "native-compiler-evidence", "Wrong native artifact name")
        members = record["members"]
        require(len(members) == len(RUN_FILES), "Native ZIP member count differs: " + label)
        published = [member["published_path"] for member in members]
        require(set(published) == {label + "/" + name for name in RUN_FILES}
                and len(set(published)) == len(RUN_FILES),
                "Native published member set differs: " + label)
        actual = {path.relative_to(data_root / label).as_posix()
                  for path in (data_root / label).rglob("*") if path.is_file()}
        require(actual == RUN_FILES, "Native publication contains missing or extra files: " + label)
        for member in members:
            relative = member["published_path"]
            source_name = member["original_zip_member"]
            expected_original = (
                relative.split("/", 1)[1].replace(".txt", ".log")
                if relative.endswith(("native-tests.txt", "native-campaign.txt", "native-dependencies.txt"))
                else relative.split("/", 1)[1]
            )
            if expected_original in {"first.csv", "second.csv"} or expected_original.startswith("derived/"):
                expected_original = "native-study/" + expected_original
            require(source_name == expected_original, "ZIP member mapping differs: " + relative)
            path = data_path(data_root, relative)
            require(path.is_file() and path.stat().st_size == member["bytes"]
                    and SHA256.fullmatch(member["sha256"]) is not None
                    and digest(path) == member["sha256"],
                    "Published native member differs from original ZIP: " + relative)
        require(next(m for m in members if m["published_path"] == label + "/first.csv")["sha256"]
                == pinned["first_sha256"] and
                next(m for m in members if m["published_path"] == label + "/second.csv")["sha256"]
                == pinned["second_sha256"],
                "Native raw matrix identities differ: " + label)
    return len(RUN_FILES) * len(EXPECTED_RUNS)


def check_mr10_row(row, admission, observations):
    require(COHERENCE | LOCALITY <= admission.keys(), "Admitted MR10 lacks complete v3 facts")
    require(all(admission[name] is True for name in COHERENCE | LOCALITY),
            "Admitted MR10 has unsatisfied v3 fact")
    intervention = observations.get("integrity_intervention")
    snapshots = observations.get("integrity_snapshots")
    require(isinstance(intervention, dict) and isinstance(snapshots, dict),
            "Admitted MR10 lacks intervention or snapshot observations")
    require(all(intervention.get(name) is True for name in LOCALITY),
            "MR10 observed checksum-locality facts differ")
    for label in ("source", "followup"):
        snapshot = snapshots.get(label)
        require(isinstance(snapshot, dict) and type(snapshot.get("bytes")) is int
                and snapshot["bytes"] > 0 and isinstance(snapshot.get("sha256"), str)
                and SHA256.fullmatch(snapshot["sha256"]) is not None,
                "MR10 snapshot record malformed: " + label)
    require(snapshots["source"]["sha256"] != snapshots["followup"]["sha256"],
            "MR10 checksum intervention lacks distinct snapshots")


def parse_duration(value):
    try:
        duration = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid native duration") from error
    require(math.isfinite(duration) and duration > 0,
            "Native duration must be finite and positive")
    return duration


def verify_matrix(path, source_root=ROOT):
    fields, rows = read_csv(path)
    require(fields == FIELD_NAMES and len(rows) == 18900, "Native matrix schema/size differs: " + str(path))
    require_study_coverage(rows)
    seen_hosts = {}
    admitted_mr10 = 0
    for row in rows:
        verdict = row["verdict"]
        require(verdict in {"SATISFIED", "INCONSISTENT", "INADMISSIBLE"}, "Unknown native verdict")
        require(row["exposed"] == str(row["defect_id"] != "CLEAN" and verdict == "INCONSISTENT"),
                "Native exposure/verdict mismatch")
        admission = json.loads(row["admission_json"])
        observations = json.loads(row["observations_json"])
        require(isinstance(admission, dict) and isinstance(observations, dict)
                and all(isinstance(value, bool) for value in admission.values()),
                "Malformed native evidence fields")
        if verdict != "INADMISSIBLE":
            require(all(admission.values()), "Failed premise counted as admitted")
        if row["relation_id"] == "MR10" and verdict != "INADMISSIBLE":
            check_mr10_row(row, admission, observations)
            admitted_mr10 += 1
        parse_duration(row["duration_seconds"])
        host = row["host"]
        if host not in seen_hosts:
            require(digest(source_root / "hosts" / host) == row["host_sha256"],
                    "Native observed host source differs from current file: " + host)
        previous = seen_hosts.setdefault(host, row["host_sha256"])
        require(previous == row["host_sha256"] and SHA256.fullmatch(previous) is not None,
                "Host hash changes within matrix")
    require(len(seen_hosts) == 18 and admitted_mr10 == 1206,
            "Native host count or MR10 v3 admission count differs")
    return rows


def key(row):
    return tuple(row[field] for field in KEY_FIELDS)


def compare_non_timing(a, b):
    left = {key(row): row for row in a}
    right = {key(row): row for row in b}
    require(len(left) == len(a) and len(right) == len(b) and left.keys() == right.keys(),
            "Native matrix key sets differ")
    fields = FIELD_NAMES[:-1]
    require(all(left[k][field] == right[k][field] for k in left for field in fields),
            "Native non-timing observations differ")
    return len(left) * len(fields)


def load_deriver():
    spec = importlib.util.spec_from_file_location("native_execution_deriver", ROOT / "scripts/derive_admission_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(data_root=DATA, source_root=ROOT):
    provenance = json.loads((data_root / "provenance.json").read_text(encoding="utf-8"))
    inputs = verify_source_inputs(data_root, source_root, provenance)
    members = verify_members(data_root, provenance)
    deriver = load_deriver()
    all_rows = {}
    all_summaries = {}
    with tempfile.TemporaryDirectory(prefix="native-v3-data-only-") as temporary:
        scratch = Path(temporary)
        for label in EXPECTED_RUNS:
            base = data_root / label
            first = verify_matrix(base / "first.csv", source_root)
            second = verify_matrix(base / "second.csv", source_root)
            require(deriver.matrix_protocol(first) == deriver.matrix_protocol(second)
                    == "evidence-gated-v3-snapshot-coherence",
                    "Native MR10 protocol differs: " + label)
            compare_non_timing(first, second)
            summary = deriver.derive(base / "first.csv", source_root / "specs/mutants.json",
                                     scratch / label, source_root / "results/raw/robustness_matrix.csv",
                                     base / "second.csv")
            checks = deriver.scientific_checks(summary)
            require(all(checks.values()), "Data-only scientific gates failed: " + label)
            expected_gate = json.loads((base / "derived/scientific_checks.json").read_text(encoding="utf-8"))
            require(expected_gate["verdict"] == "PASS" and expected_gate["checks"] == checks,
                    "Original native scientific gate differs: " + label)
            for name in CSV_DERIVED:
                require(read_csv(base / "derived" / name) == read_csv(scratch / label / name),
                        "Data-only derived CSV differs: " + label + "/" + name)
            for name in JSON_DERIVED - {"scientific_checks.json"}:
                actual = json.loads((base / "derived" / name).read_text(encoding="utf-8"))
                repeat = json.loads((scratch / label / name).read_text(encoding="utf-8"))
                require(actual == repeat, "Data-only derived JSON differs: " + label + "/" + name)
            all_rows[label] = (first, second)
            all_summaries[label] = summary
    cross_first = compare_non_timing(all_rows["primary"][0], all_rows["mirror"][0])
    cross_second = compare_non_timing(all_rows["primary"][1], all_rows["mirror"][1])
    p, m = all_summaries["primary"].copy(), all_summaries["mirror"].copy()
    for summary in (p, m):
        for field in ("matrix_sha256", "run_timing", "rerun"):
            summary.pop(field)
    require(p == m, "Native cross-run scientific summaries differ")
    return {
        "verdict": "PASS", "scope": "Recorded-current-v3-data-only; no new native execution or network check",
        "source_input_paths": inputs, "original_zip_members_preserved": members,
        "run_heads": {label: record["head_sha"] for label, record in EXPECTED_RUNS.items()},
        "shared_git_tree": SHARED_TREE,
        "matrices": {label: {"first_rows": len(rows[0]), "second_rows": len(rows[1]),
                             "protocol": all_summaries[label]["protocol"],
                             "rerun_field_comparisons": all_summaries[label]["rerun"]["field_comparisons"],
                             "rerun_differences": all_summaries[label]["rerun"]["differences"],
                             "median_row_seconds": all_summaries[label]["run_timing"]["median"]}
                     for label, rows in all_rows.items()},
        "cross_run_first_comparisons": cross_first,
        "cross_run_second_comparisons": cross_second,
        "cross_run_non_timing_differences": 0,
        "data_only_rederived_files_per_run": len(CSV_DERIVED) + len(JSON_DERIVED),
        "scientific_summary": p,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATA,
                        help="Optional benign alternate evidence root for tests")
    parser.add_argument("--source-root", type=Path, default=ROOT,
                        help="Optional benign alternate source root for tests")
    args = parser.parse_args()
    print(json.dumps(verify(args.data_root, args.source_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
