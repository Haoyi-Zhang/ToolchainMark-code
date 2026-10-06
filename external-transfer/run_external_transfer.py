#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from tosem02.evidence_boundary import ObservationUnavailable, require_observed_output
from typing import Any

ROOT = Path(__file__).resolve().parent
import argparse
PARSER = argparse.ArgumentParser(description="Re-run the fixed public-prototype transfer on separately acquired source files.")
PARSER.add_argument("--source-dir", type=Path, required=True, help="Directory containing the six externally acquired source files named in acquisition_manifest.csv")
PARSER.add_argument("--out", type=Path, required=True, help="Output directory for regenerated CSV and JSON evidence")
SRC: Path
OUT: Path
COMPILERS = {"gcc": shutil.which("gcc"), "clang": shutil.which("clang")}
OPTS = ["O0", "O1", "O2", "O3", "Os"]
PAIRS = {
    "119": ("119_before.c", "119.c"),
    "2929": ("2929_old.c", "2929.c"),
    "363": ("363_old.c", "363.c"),
}
MODES = ("native", "compatibility")
EXPECTED_BLOBS = {
    "119.c": "1f27e4b126d696bb2b98914072cc4769317e962f",
    "119_before.c": "d67d0a2f8a6e74bbe4ef897087ded2271fac321e",
    "2929.c": "d873869fb1c80ec2aaf411ff813ecad3a51cfcd2",
    "2929_old.c": "5e2755fa84dd417b3322df5820162e4515697c0c",
    "363.c": "5e5b1dfae761760fd504807414149398cbc8b124",
    "363_old.c": "6e8ddc3e3b241feea4360921fcc1c0f8becffe36",
}
COMPAT = ROOT / "compatibility_header.h"

WRAPPER_363 = r'''
#include <math.h>
#include <stdio.h>
float weighted_positive_mean(float* values, float* weights, int size);
static void emit(const char* name, float* values, float* weights, int size) {
  float r = weighted_positive_mean(values, weights, size);
  printf("%s=%a\n", name, (double)r);
}
int main(void) {
  float v1[] = {1.0f,-2.0f,3.0f,-4.0f}; float w1[] = {1.0f,2.0f,3.0f,4.0f};
  float v2[] = {0.0f,0.0f,0.0f}; float w2[] = {1.0f,1.0f,1.0f};
  float v3[] = {-1.0f,-1.0f}; float w3[] = {0.0f,0.0f};
  float v4[] = {1e-6f,-1e6f,3.5f}; float w4[] = {5.0f,0.25f,2.0f};
  emit("mixed",v1,w1,4); emit("zeros",v2,w2,3); emit("zero_weight",v3,w3,2); emit("range",v4,w4,3);
  emit("null_values",NULL,w1,4); emit("null_weights",v1,NULL,4); emit("zero_size",v1,w1,0);
  return 0;
}
'''


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 30, env: dict[str, str] | None = None):
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=env)
    return proc, time.perf_counter() - started


def normalize(text: str, root: Path) -> str:
    return (
        text.replace(str(SRC), "EXTERNAL_SOURCE")
        .replace(str(root), "RUN_ROOT")
        .replace(str(ROOT), "PACKAGE_ROOT")
    )


def compile_one(
    compiler: str,
    flags: list[str],
    source: Path,
    case: str,
    work: Path,
    mode: str,
    sanitizer: bool = False,
) -> tuple[int, str, str, float, Path]:
    exe = work / "program"
    wrapper = work / "wrapper363.c"
    wrapper.write_text(WRAPPER_363, encoding="utf-8")
    include_flags = ["-include", str(COMPAT)] if mode == "compatibility" else []
    if case == "363":
        obj = work / "external.o"
        p1, t1 = run([compiler, *flags, *include_flags, "-Dmain=external_example_main", "-c", str(source), "-o", str(obj)])
        if p1.returncode != 0:
            return p1.returncode, p1.stdout, p1.stderr, t1, exe
        p2, t2 = run([compiler, *flags, *include_flags, str(obj), str(wrapper), "-lm", "-o", str(exe)])
        return p2.returncode, p1.stdout + p2.stdout, p1.stderr + p2.stderr, t1 + t2, exe
    p, elapsed = run([compiler, *flags, *include_flags, str(source), "-lm", "-o", str(exe)])
    return p.returncode, p.stdout, p.stderr, elapsed, exe


def observed_output(case: str, variant: str, cwd: Path, stdout: str, *, returncode: int | None) -> str:
    expected = cwd / ("nr_before.txt" if variant == "before" else "nr.txt") if case == "119" else None
    return require_observed_output(returncode=returncode, path=expected, stdout=stdout)


def output_observation(case: str, variant: str, cwd: Path, stdout: str, returncode: int | None) -> dict[str, Any]:
    try:
        value = observed_output(case, variant, cwd, stdout, returncode=returncode)
        return {"available": True, "value": value, "reason": ""}
    except ObservationUnavailable as exc:
        return {"available": False, "value": None, "reason": str(exc)}


def host_pair_verdict(before: dict[str, Any], after: dict[str, Any]) -> str:
    if not all(x["compile_rc"] == 0 and x["run_rc"] == 0 and x["output_available"] for x in (before, after)):
        return "INADMISSIBLE"
    return "SATISFIED" if before["output"] == after["output"] else "INCONSISTENT"


def relocation_verdict(compile_rc: int, run_rc: int | None, relocated_rc: int | None,
                       source: dict[str, Any], relocated: dict[str, Any]) -> str:
    if compile_rc != 0 or run_rc != 0 or relocated_rc != 0 or not source["available"] or not relocated["available"]:
        return "INADMISSIBLE"
    return "SATISFIED" if source["value"] == relocated["value"] else "INCONSISTENT"


def main() -> None:
    global SRC, OUT
    args = PARSER.parse_args()
    SRC = args.source_dir.resolve()
    OUT = args.out.resolve()
    if not SRC.is_dir():
        raise SystemExit(f"External source directory does not exist: {SRC}")
    if OUT.exists():
        raise SystemExit("Use a new output directory; existing evidence is not overwritten.")
    if not COMPAT.is_file():
        raise SystemExit(f"Packaged compatibility header is missing: {COMPAT}")
    if not all(COMPILERS.values()):
        missing = ", ".join(name for name, path in COMPILERS.items() if not path)
        raise SystemExit(f"Required compiler(s) unavailable: {missing}")
    OUT.mkdir(parents=True)
    for filename, expected in EXPECTED_BLOBS.items():
        actual = git_blob_sha1(SRC / filename)
        if actual != expected:
            raise SystemExit(f"Source identity mismatch for {filename}: {actual} != {expected}")

    rows: list[dict[str, Any]] = []
    observations: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    with tempfile.TemporaryDirectory(prefix="extwm-v2-") as td_s:
        td = Path(td_s)
        for mode in MODES:
            for compiler_name, compiler in COMPILERS.items():
                if not compiler:
                    continue
                version = subprocess.run([compiler, "--version"], text=True, capture_output=True).stdout.splitlines()[0]
                for opt in OPTS:
                    flags = [f"-{opt}", "-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-fno-fast-math"]
                    for case, (before_name, after_name) in PAIRS.items():
                        for variant, source_name in (("before", before_name), ("watermarked", after_name)):
                            work = td / f"{mode}-{case}-{compiler_name}-{opt}-{variant}"
                            work.mkdir()
                            source = SRC / source_name
                            crc, cstdout, cstderr, ctime, exe = compile_one(compiler, flags, source, case, work, mode)
                            rrc: int | None = None
                            rout = rerr = ""
                            output = None
                            source_obs = {"available": False, "value": None, "reason": "Build or execution unavailable."}
                            rtime = 0.0
                            reloc_rc: int | None = None
                            reloc_output = None
                            relocated_obs = {"available": False, "value": None, "reason": "Relocated execution unavailable."}
                            if crc == 0:
                                rp, rtime = run([str(exe)], cwd=work)
                                rrc, rout, rerr = rp.returncode, rp.stdout, rp.stderr
                                source_obs = output_observation(case, variant, work, rout, rrc)
                                output = source_obs["value"]
                                relocated = td / f"relocated-{mode}-{case}-{compiler_name}-{opt}-{variant}"
                                relocated.mkdir()
                                relocated_exe = relocated / "program"
                                shutil.copy2(exe, relocated_exe)
                                relp, _ = run([str(relocated_exe)], cwd=relocated)
                                reloc_rc = relp.returncode
                                relocated_obs = output_observation(case, variant, relocated, relp.stdout, reloc_rc)
                                reloc_output = relocated_obs["value"]
                            reloc_verdict = relocation_verdict(crc, rrc, reloc_rc, source_obs, relocated_obs)
                            record = {
                                "mode": mode,
                                "case": case,
                                "variant": variant,
                                "compiler": compiler_name,
                                "compiler_version": version,
                                "optimization": opt,
                                "source_label": source_name,
                                "source_git_blob_sha1": git_blob_sha1(source),
                                "source_sha256": sha256(source),
                                "compatibility_header_applied": mode == "compatibility",
                                "compile_rc": crc,
                                "compile_warning_lines": sum("warning:" in x for x in cstderr.splitlines()),
                                "compile_stderr": normalize(cstderr, td),
                                "run_rc": rrc,
                                "run_stderr": normalize(rerr, td),
                                "output_available": source_obs["available"],
                                "output_unavailable_reason": source_obs["reason"],
                                "output_sha256": sha256_bytes(output.encode()) if source_obs["available"] else "",
                                "relocate_rc": reloc_rc,
                                "relocate_output_available": relocated_obs["available"],
                                "relocate_output_unavailable_reason": relocated_obs["reason"],
                                "relocate_output_sha256": sha256_bytes(reloc_output.encode()) if relocated_obs["available"] else "",
                                "relocation_verdict": reloc_verdict,
                                "relocation_match": reloc_verdict == "SATISFIED",
                                "compile_seconds": round(ctime, 6),
                                "run_seconds": round(rtime, 6),
                            }
                            rows.append(record)
                            observations[(mode, case, compiler_name, opt, variant)] = {
                                "compile_rc": crc,
                                "run_rc": rrc,
                                "output": output,
                                "output_available": source_obs["available"],
                                "output_sha256": record["output_sha256"],
                            }

    relations: list[dict[str, Any]] = []
    for mode in MODES:
        for case in PAIRS:
            configs = [(c, o) for c, path in COMPILERS.items() if path for o in OPTS]
            for compiler, opt in configs:
                before = observations[(mode, case, compiler, opt, "before")]
                after = observations[(mode, case, compiler, opt, "watermarked")]
                both_build = before["compile_rc"] == 0 and after["compile_rc"] == 0
                both_run = both_build and before["run_rc"] == 0 and after["run_rc"] == 0
                exit_verdict = "SATISFIED" if both_run else "INADMISSIBLE"
                semantic_verdict = host_pair_verdict(before, after)
                reason = "" if semantic_verdict != "INADMISSIBLE" else "Both variants must compile, terminate successfully, and produce the required output before semantic comparison."
                relations.append({
                    "mode": mode,
                    "case": case,
                    "relation": "execution_only_baseline",
                    "compiler": compiler,
                    "optimization": opt,
                    "verdict": exit_verdict,
                    "reason": reason,
                })
                relations.append({
                    "mode": mode,
                    "case": case,
                    "relation": "host_observation_equivalence",
                    "compiler": compiler,
                    "optimization": opt,
                    "verdict": semantic_verdict,
                    "reason": reason,
                    "before_sha256": before["output_sha256"],
                    "after_sha256": after["output_sha256"],
                })
            for variant in ("before", "watermarked"):
                selected = [observations[(mode, case, c, o, variant)] for c, o in configs]
                admitted = [x for x in selected if x["compile_rc"] == 0 and x["run_rc"] == 0 and x["output_available"]]
                if len(admitted) != len(selected):
                    verdict = "INADMISSIBLE"
                    reason = "All compiler-optimization configurations must compile, terminate successfully, and produce the required output before stability is evaluated."
                    distinct = ""
                else:
                    distinct_count = len({x["output"] for x in admitted})
                    verdict = "SATISFIED" if distinct_count == 1 else "INCONSISTENT"
                    reason = ""
                    distinct = distinct_count
                relations.append({
                    "mode": mode,
                    "case": case,
                    "relation": "compiler_optimization_stability",
                    "variant": variant,
                    "compiler": "all",
                    "optimization": "all",
                    "verdict": verdict,
                    "reason": reason,
                    "distinct_outputs": distinct,
                })
            relations.append({
                "mode": mode,
                "case": case,
                "relation": "payload_recovery",
                "compiler": "all",
                "optimization": "all",
                "verdict": "INADMISSIBLE",
                "reason": "The fixed public example surface provides labeled source pairs but no automatable source-to-payload extraction interface; filenames are not used as a payload oracle.",
            })

    # Sanitizer study in compatibility mode. The same compatibility header is applied to both variants.
    san: list[dict[str, Any]] = []
    for compiler_name, compiler in COMPILERS.items():
        if not compiler:
            continue
        for case, (before_name, after_name) in PAIRS.items():
            for variant, source_name in (("before", before_name), ("watermarked", after_name)):
                with tempfile.TemporaryDirectory(prefix="extwm-san-v2-") as sd_s:
                    sd = Path(sd_s)
                    source = SRC / source_name
                    flags = ["-O1", "-g", "-std=c11", "-fno-omit-frame-pointer", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
                    crc, _, cstderr, _, exe = compile_one(compiler, flags, source, case, sd, "compatibility", sanitizer=True)
                    rrc: int | None = None
                    rstderr = ""
                    if crc == 0:
                        env = os.environ.copy()
                        env["ASAN_OPTIONS"] = "detect_leaks=1:halt_on_error=1"
                        env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
                        rp, _ = run([str(exe)], cwd=sd, env=env)
                        rrc, rstderr = rp.returncode, rp.stderr
                    clean = crc == 0 and rrc == 0 and "ERROR:" not in rstderr and "runtime error:" not in rstderr
                    san.append({
                        "mode": "compatibility",
                        "case": case,
                        "variant": variant,
                        "compiler": compiler_name,
                        "compile_rc": crc,
                        "run_rc": rrc,
                        "sanitizer_clean": clean,
                        "compile_stderr": normalize(cstderr, sd),
                        "run_stderr": normalize(rstderr, sd),
                    })


    def write_csv(path: Path, data: list[dict[str, Any]]) -> None:
        fields = sorted({k for row in data for k in row})
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)


    write_csv(OUT / "execution_rows.csv", rows)
    write_csv(OUT / "relation_verdicts.csv", relations)
    write_csv(OUT / "sanitizer_rows.csv", san)

    compat_sem = [r for r in relations if r["mode"] == "compatibility" and r["relation"] == "host_observation_equivalence"]
    compat_exit = [r for r in relations if r["mode"] == "compatibility" and r["relation"] == "execution_only_baseline"]
    native_sem = [r for r in relations if r["mode"] == "native" and r["relation"] == "host_observation_equivalence"]
    case_summary: list[dict[str, Any]] = []
    for case in PAIRS:
        csem = [r for r in compat_sem if r["case"] == case]
        cexit = [r for r in compat_exit if r["case"] == case]
        nsem = [r for r in native_sem if r["case"] == case]
        case_summary.append({
            "case": case,
            "native_admitted_checks": sum(r["verdict"] != "INADMISSIBLE" for r in nsem),
            "native_inadmissible_checks": sum(r["verdict"] == "INADMISSIBLE" for r in nsem),
            "compatibility_exit_only_satisfied": sum(r["verdict"] == "SATISFIED" for r in cexit),
            "compatibility_host_satisfied": sum(r["verdict"] == "SATISFIED" for r in csem),
            "compatibility_host_inconsistent": sum(r["verdict"] == "INCONSISTENT" for r in csem),
            "compatibility_configs": len(csem),
        })
    write_csv(OUT / "case_summary.csv", case_summary)

    compat_pair_exit_pass = sum(
        all(r["verdict"] == "SATISFIED" for r in compat_exit if r["case"] == case) for case in PAIRS
    )
    compat_pair_sem_pass = sum(
        all(r["verdict"] == "SATISFIED" for r in compat_sem if r["case"] == case) for case in PAIRS
    )
    compat_pair_sem_inconsistent = sum(
        any(r["verdict"] == "INCONSISTENT" for r in compat_sem if r["case"] == case) for case in PAIRS
    )
    summary = {
        "external_repository": "felipeasimos/software-watermark",
        "commit": "f63f49a770e3b0dc4f1d092cfa22ec2610eb13f8",
        "scholarly_doi": "10.1109/MetroInd4.0IoT54413.2022.9831668",
        "source_pairs": len(PAIRS),
        "source_files": len(EXPECTED_BLOBS),
        "source_identity_checks": len(EXPECTED_BLOBS),
        "source_identity_mismatches": 0,
        "modes": list(MODES),
        "compilers": [name for name, path in COMPILERS.items() if path],
        "optimization_levels": OPTS,
        "execution_rows": len(rows),
        "native_execution_rows": sum(r["mode"] == "native" for r in rows),
        "compatibility_execution_rows": sum(r["mode"] == "compatibility" for r in rows),
        "native_semantic_checks": len(native_sem),
        "native_semantic_inadmissible": sum(r["verdict"] == "INADMISSIBLE" for r in native_sem),
        "compatibility_exit_only_checks": len(compat_exit),
        "compatibility_exit_only_satisfied": sum(r["verdict"] == "SATISFIED" for r in compat_exit),
        "compatibility_host_semantic_checks": len(compat_sem),
        "compatibility_host_semantic_satisfied": sum(r["verdict"] == "SATISFIED" for r in compat_sem),
        "compatibility_host_semantic_inconsistent": sum(r["verdict"] == "INCONSISTENT" for r in compat_sem),
        "compatibility_pair_exit_only_pass": compat_pair_exit_pass,
        "compatibility_pair_host_semantic_pass": compat_pair_sem_pass,
        "compatibility_pair_host_semantic_inconsistent": compat_pair_sem_inconsistent,
        "relocation_attempts": len(rows),
        "relocation_admitted": sum(r["relocation_verdict"] != "INADMISSIBLE" for r in rows),
        "relocation_inadmissible": sum(r["relocation_verdict"] == "INADMISSIBLE" for r in rows),
        "relocation_satisfied": sum(bool(r["relocation_match"]) for r in rows),
        "sanitizer_checks": len(san),
        "sanitizer_clean": sum(bool(r["sanitizer_clean"]) for r in san),
        "payload_recovery_verdict": "INADMISSIBLE",
        "payload_recovery_reason": "No automated source-to-payload extraction interface is present in the fixed public example surface; filenames are not treated as an oracle.",
        "compatibility_intervention": "The same forced-include header maps the obsolete isnanf spelling to the standard isnan predicate for every source variant; no external source is edited.",
        "redistribution": "SOURCE_NOT_PACKAGED_NO_EXPLICIT_REPOSITORY_LICENSE_AT_FIXED_COMMIT",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
