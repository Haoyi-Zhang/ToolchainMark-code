#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

RELATIONS = [f"MR{i:02d}" for i in range(1, 15)]
SUITES = {
    "round_trip": ["MR01"],
    "host_semantics": ["MR01", "MR02"],
    "compiler_differential": ["MR01", "MR02", "MR06", "MR07"],
    "complete_catalog": RELATIONS,
}
DESIGN_HOST = "H01-gcd.c"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def greedy_cover(units: Iterable[tuple[str, ...]], failures: dict[tuple[str, ...], set[str]], weights: Counter | None = None) -> list[str]:
    remaining = set(units)
    selected: list[str] = []
    while remaining:
        scored = []
        for relation in RELATIONS:
            gain_units = {unit for unit in remaining if relation in failures[unit]}
            if weights is None:
                gain = len(gain_units)
            else:
                gain = sum(weights[unit] for unit in gain_units)
            scored.append((gain, -RELATIONS.index(relation), relation, gain_units))
        gain, _, relation, gain_units = max(scored)
        if gain == 0:
            break
        selected.append(relation)
        remaining -= gain_units
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--mutants", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260722)
    args = parser.parse_args()

    rows = read_csv(args.matrix)
    mutants = {m["id"]: m for m in json.loads(args.mutants.read_text())["mutants"]}
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    clean = [row for row in rows if row["defect_id"] == "CLEAN"]
    defective = [row for row in rows if row["defect_id"] != "CLEAN"]
    failures: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in defective:
        if row["pass"] == "False":
            failures[(row["host"], row["carrier"], row["defect_id"])].add(row["relation_id"])
    all_units = sorted({(row["host"], row["carrier"], row["defect_id"]) for row in defective})
    design_units = [unit for unit in all_units if unit[0] == DESIGN_HOST]

    relation_rows = []
    for relation in RELATIONS:
        relation_rows.append({
            "relation": relation,
            "design_units_exposed": sum(relation in failures[unit] for unit in design_units),
            "expanded_units_exposed": sum(relation in failures[unit] for unit in all_units),
            "expanded_units": len(all_units),
        })
    write_csv(out / "relation_sensitivity.csv", relation_rows,
              ["relation", "design_units_exposed", "expanded_units_exposed", "expanded_units"])

    suite_rows = []
    suite_sets: dict[str, set[tuple[str, str, str]]] = {}
    for name, members in SUITES.items():
        exposed = {unit for unit in design_units if failures[unit] & set(members)}
        suite_sets[name] = exposed
        suite_rows.append({
            "suite": name,
            "relations": " ".join(members),
            "design_units_exposed": len(exposed),
            "design_units": len(design_units),
            "score_percent": f"{100 * len(exposed) / len(design_units):.2f}",
        })
    write_csv(out / "suite_comparison.csv", suite_rows,
              ["suite", "relations", "design_units_exposed", "design_units", "score_percent"])

    paired_rows = []
    comparisons = [
        ("host_semantics", "round_trip"),
        ("compiler_differential", "host_semantics"),
        ("complete_catalog", "round_trip"),
        ("complete_catalog", "host_semantics"),
        ("complete_catalog", "compiler_differential"),
    ]
    for larger, smaller in comparisons:
        a, bset = suite_sets[larger], suite_sets[smaller]
        b = len(a - bset)
        c = len(bset - a)
        paired_rows.append({
            "larger_suite": larger,
            "smaller_suite": smaller,
            "larger_only": b,
            "smaller_only": c,
            "net_gain": b - c,
            "exact_two_sided_p": f"{exact_mcnemar(b, c):.12g}",
        })
    write_csv(out / "paired_mcnemar.csv", paired_rows,
              ["larger_suite", "smaller_suite", "larger_only", "smaller_only", "net_gain", "exact_two_sided_p"])

    primary_exclusive = 0
    primary_exposed = 0
    for unit in all_units:
        primary = mutants[unit[2]]["primary_relation"]
        primary_exposed += primary in failures[unit]
        primary_exclusive += failures[unit] == {primary}

    non_design_hosts = sorted({unit[0] for unit in all_units if unit[0] != DESIGN_HOST})
    context_verdict_total = 0
    context_verdict_matches = 0
    context_killset_total = 0
    context_killset_matches = 0
    for host in non_design_hosts:
        for carrier in sorted({unit[1] for unit in design_units}):
            for defect in sorted(mutants):
                design_set = failures[(DESIGN_HOST, carrier, defect)]
                held_set = failures[(host, carrier, defect)]
                context_killset_total += 1
                context_killset_matches += design_set == held_set
                for relation in RELATIONS:
                    context_verdict_total += 1
                    context_verdict_matches += ((relation in design_set) == (relation in held_set))

    class_rows = []
    fault_classes = sorted({m["fault_class"] for m in mutants.values()})
    for fault_class in fault_classes:
        train = [unit for unit in design_units if mutants[unit[2]]["fault_class"] != fault_class]
        selected = greedy_cover(train, failures)
        test = [unit for unit in all_units if unit[0] != DESIGN_HOST and mutants[unit[2]]["fault_class"] == fault_class]
        exposed = sum(bool(failures[unit] & set(selected)) for unit in test)
        direct_relations = sorted({mutants[unit[2]]["primary_relation"] for unit in test})
        class_rows.append({
            "held_out_fault_class": fault_class,
            "training_design_units": len(train),
            "test_units": len(test),
            "selected_relations": " ".join(selected),
            "direct_relations": " ".join(direct_relations),
            "exposed_test_units": exposed,
            "sensitivity_percent": f"{100 * exposed / len(test):.2f}",
        })
    write_csv(out / "fault_class_holdout.csv", class_rows,
              ["held_out_fault_class", "training_design_units", "test_units", "selected_relations", "direct_relations", "exposed_test_units", "sensitivity_percent"])

    operator_rows = []
    for defect in sorted(mutants):
        train = [unit for unit in design_units if unit[2] != defect]
        selected = greedy_cover(train, failures)
        test = [unit for unit in all_units if unit[0] != DESIGN_HOST and unit[2] == defect]
        exposed = sum(bool(failures[unit] & set(selected)) for unit in test)
        operator_rows.append({
            "held_out_operator": defect,
            "fault_class": mutants[defect]["fault_class"],
            "direct_relation": mutants[defect]["primary_relation"],
            "selected_relations": " ".join(selected),
            "test_units": len(test),
            "exposed_test_units": exposed,
            "sensitivity_percent": f"{100 * exposed / len(test):.2f}",
        })
    write_csv(out / "operator_holdout.csv", operator_rows,
              ["held_out_operator", "fault_class", "direct_relation", "selected_relations", "test_units", "exposed_test_units", "sensitivity_percent"])

    carrier_rows = []
    carriers = sorted({unit[1] for unit in all_units})
    for held_carrier in carriers:
        train = [unit for unit in design_units if unit[1] != held_carrier]
        selected = greedy_cover(train, failures)
        test = [unit for unit in all_units if unit[1] == held_carrier]
        exposed = sum(bool(failures[unit] & set(selected)) for unit in test)
        carrier_rows.append({
            "held_out_carrier": held_carrier,
            "selected_relations": " ".join(selected),
            "test_units": len(test),
            "exposed_test_units": exposed,
            "sensitivity_percent": f"{100 * exposed / len(test):.2f}",
        })
    write_csv(out / "carrier_holdout.csv", carrier_rows,
              ["held_out_carrier", "selected_relations", "test_units", "exposed_test_units", "sensitivity_percent"])

    design_failure = {(unit[1], unit[2]): failures[unit] for unit in design_units}
    two_dim_units = list(design_failure)
    by_class: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for unit in two_dim_units:
        by_class[mutants[unit[1]]["fault_class"]].append(unit)
    rng = random.Random(args.seed)
    bootstrap_rows = []
    selection_counts = Counter()
    perfect = 0
    for replicate in range(1, args.bootstrap_replicates + 1):
        draws: list[tuple[str, str]] = []
        drawn: set[tuple[str, str]] = set()
        for fault_class in sorted(by_class):
            members = by_class[fault_class]
            for _ in members:
                unit = rng.choice(members)
                draws.append(unit)
                drawn.add(unit)
        weights = Counter(draws)
        selected = greedy_cover(weights.keys(), design_failure, weights)
        selection_counts.update(selected)
        out_of_bag = [unit for unit in two_dim_units if unit not in drawn]
        exposed = sum(bool(design_failure[unit] & set(selected)) for unit in out_of_bag)
        sensitivity = exposed / len(out_of_bag) if out_of_bag else 1.0
        perfect += exposed == len(out_of_bag)
        bootstrap_rows.append({
            "replicate": replicate,
            "selected_relations": " ".join(selected),
            "suite_size": len(selected),
            "out_of_bag_units": len(out_of_bag),
            "out_of_bag_exposed": exposed,
            "out_of_bag_sensitivity": f"{sensitivity:.8f}",
        })
    write_csv(out / "bootstrap_replicates.csv", bootstrap_rows,
              ["replicate", "selected_relations", "suite_size", "out_of_bag_units", "out_of_bag_exposed", "out_of_bag_sensitivity"])

    sens = [float(row["out_of_bag_sensitivity"]) for row in bootstrap_rows]
    sizes = [int(row["suite_size"]) for row in bootstrap_rows]
    oob_sizes = [int(row["out_of_bag_units"]) for row in bootstrap_rows]
    quantile = lambda values, q: statistics.quantiles(values, n=4, method="inclusive")[{0.25: 0, 0.75: 2}[q]]
    bootstrap_summary = {
        "seed": args.seed,
        "replicates": args.bootstrap_replicates,
        "suite_size": {"min": min(sizes), "q1": quantile(sizes, 0.25), "median": statistics.median(sizes), "q3": quantile(sizes, 0.75), "max": max(sizes)},
        "out_of_bag_units": {"min": min(oob_sizes), "q1": quantile(oob_sizes, 0.25), "median": statistics.median(oob_sizes), "q3": quantile(oob_sizes, 0.75), "max": max(oob_sizes)},
        "out_of_bag_sensitivity": {"min": min(sens), "q1": quantile(sens, 0.25), "median": statistics.median(sens), "q3": quantile(sens, 0.75), "max": max(sens)},
        "perfect_replicates": perfect,
        "selection_counts": dict(sorted(selection_counts.items())),
    }
    (out / "bootstrap_summary.json").write_text(json.dumps(bootstrap_summary, indent=2) + "\n")

    durations = [float(row["duration_seconds"]) for row in rows]
    summary = {
        "schema_version": "1.0",
        "matrix": str(args.matrix),
        "matrix_sha256": sha256(args.matrix),
        "rows": len(rows),
        "hosts": len({row["host"] for row in rows}),
        "carriers": len({row["carrier"] for row in rows}),
        "relations": len({row["relation_id"] for row in rows}),
        "operators": len({row["defect_id"] for row in defective}),
        "clean_rows": len(clean),
        "clean_passes": sum(row["pass"] == "True" for row in clean),
        "defect_rows": len(defective),
        "inconsistent_defect_rows": sum(row["pass"] == "False" for row in defective),
        "units": len(all_units),
        "units_exposed": sum(bool(failures[unit]) for unit in all_units),
        "primary_relation_exposes_units": primary_exposed,
        "primary_relation_exclusive_units": primary_exclusive,
        "context_replay": {
            "verdict_matches": context_verdict_matches,
            "verdict_total": context_verdict_total,
            "killset_matches": context_killset_matches,
            "killset_total": context_killset_total,
        },
        "zero_sensitivity_fault_classes": [row["held_out_fault_class"] for row in class_rows if float(row["sensitivity_percent"]) == 0.0],
        "zero_sensitivity_operators": [row["held_out_operator"] for row in operator_rows if float(row["sensitivity_percent"]) == 0.0],
        "suite_counts": {row["suite"]: row["design_units_exposed"] for row in suite_rows},
        "timing": {"all_positive": all(value > 0 for value in durations), "median_seconds": statistics.median(durations), "max_seconds": max(durations), "sum_seconds": sum(durations)},
        "bootstrap": bootstrap_summary,
    }
    (out / "robustness_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
