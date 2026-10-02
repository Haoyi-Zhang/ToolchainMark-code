from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .catalog import artifact_root, load_mutants, load_relations

SUITES = {
    'B0-Roundtrip': ['MR01'],
    'B1-Conventional': ['MR01', 'MR02'],
    'B2-Differential': ['MR01', 'MR02', 'MR06', 'MR07'],
    'Full': [f'MR{i:02d}' for i in range(1, 15)],
}


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row['pass'] = row['pass'] == 'True'
        row['killed'] = row['killed'] == 'True'
        row['pilot'] = row['pilot'] == 'True'
        row['duration_seconds'] = float(row['duration_seconds'])
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive(raw_catalog: Path, raw_breadth: Path, raw_pilot: Path, out_dir: Path) -> dict[str, Any]:
    catalog = read_rows(raw_catalog)
    breadth = read_rows(raw_breadth)
    pilot = read_rows(raw_pilot)
    mutant_rows = [r for r in catalog if r['defect_id'] != 'CLEAN']
    clean_rows = [r for r in catalog if r['defect_id'] == 'CLEAN']
    units = sorted({(r['carrier'], r['defect_id']) for r in mutant_rows})
    failures: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in mutant_rows:
        if not row['pass']:
            failures[(row['carrier'], row['defect_id'])].add(row['relation_id'])

    relation_rows = []
    for rel in load_relations():
        killed = sum(rel['id'] in failures[unit] for unit in units)
        relation_rows.append({'relation_id': rel['id'], 'relation_name': rel['name'], 'killed_units': killed,
                              'total_units': len(units), 'rate_percent': f'{100.0 * killed / len(units):.1f}'})
    write_csv(out_dir / 'relation_sensitivity.csv', relation_rows,
              ['relation_id', 'relation_name', 'killed_units', 'total_units', 'rate_percent'])

    suite_rows = []
    for name, members in SUITES.items():
        killed = sum(bool(failures[unit] & set(members)) for unit in units)
        suite_rows.append({'suite': name, 'relations': ' '.join(members), 'killed_units': killed,
                           'survived_units': len(units) - killed, 'total_units': len(units),
                           'score_percent': f'{100.0 * killed / len(units):.1f}'})
    write_csv(out_dir / 'suite_sensitivity.csv', suite_rows,
              ['suite', 'relations', 'killed_units', 'survived_units', 'total_units', 'score_percent'])

    mutant_meta = {m['id']: m for m in load_mutants()}
    class_units: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for unit in units:
        class_units[mutant_meta[unit[1]]['fault_class']].append(unit)
    class_rows = []
    for fault_class in sorted(class_units):
        members = class_units[fault_class]
        killed = sum(bool(failures[u]) for u in members)
        class_rows.append({'fault_class': fault_class, 'units': len(members), 'killed': killed,
                           'survived': len(members) - killed, 'score_percent': f'{100.0 * killed / len(members):.1f}'})
    write_csv(out_dir / 'fault_class_summary.csv', class_rows,
              ['fault_class', 'units', 'killed', 'survived', 'score_percent'])

    carrier_rows = []
    for carrier in ['string', 'symbol', 'section']:
        members = [u for u in units if u[0] == carrier]
        killed = sum(bool(failures[u]) for u in members)
        carrier_rows.append({'carrier': carrier, 'units': len(members), 'killed': killed, 'survived': len(members) - killed})
    write_csv(out_dir / 'carrier_summary.csv', carrier_rows, ['carrier', 'units', 'killed', 'survived'])

    witness_rows = []
    order = [r['id'] for r in load_relations()]
    for carrier, mutant_id in units:
        candidates = [r for r in mutant_rows if r['carrier'] == carrier and r['defect_id'] == mutant_id and not r['pass']]
        candidates.sort(key=lambda r: order.index(r['relation_id']))
        first = candidates[0]
        witness_rows.append({'carrier': carrier, 'defect_id': mutant_id, 'operator': first['defect_operator'],
                             'fault_class': first['fault_class'], 'first_relation': first['relation_id'],
                             'detail': first['detail']})
    write_csv(out_dir / 'witnesses.csv', witness_rows,
              ['carrier', 'defect_id', 'operator', 'fault_class', 'first_relation', 'detail'])

    uncovered = set(units)
    greedy = []
    while uncovered:
        scored = []
        for relation_id in order:
            gain_units = sorted([u for u in uncovered if relation_id in failures[u]])
            scored.append((len(gain_units), -order.index(relation_id), relation_id, gain_units))
        gain, _, relation_id, gain_units = max(scored)
        if gain == 0:
            break
        greedy.append({'step': len(greedy) + 1, 'relation_id': relation_id, 'new_units': gain,
                       'remaining_after': len(uncovered) - gain,
                       'units': [{'carrier': u[0], 'defect_id': u[1]} for u in gain_units]})
        uncovered -= set(gain_units)
    (out_dir / 'greedy_cover.json').write_text(json.dumps({'steps': greedy, 'uncovered': sorted(uncovered)}, indent=2) + '\n')

    durations = [r['duration_seconds'] for r in catalog]
    timing = {'row_count': len(durations), 'median_seconds': statistics.median(durations), 'max_seconds': max(durations),
              'zero_duration_rows': sum(d == 0 for d in durations)}
    (out_dir / 'timing_summary.json').write_text(json.dumps(timing, indent=2) + '\n')

    pilot_mutants = [r for r in pilot if r['defect_id'] != 'CLEAN']
    pilot_failures: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in pilot_mutants:
        if not row['pass']:
            pilot_failures[(row['carrier'], row['defect_id'])].add(row['relation_id'])
    pilot_units = sorted(pilot_failures.keys() | {(r['carrier'], r['defect_id']) for r in pilot_mutants})
    pilot_summary = {
        'unit_count': len(pilot_units),
        'full_suite_killed': sum(bool(pilot_failures[u]) for u in pilot_units),
        'MR02_killed': sum('MR02' in pilot_failures[u] for u in pilot_units),
        'MR10_killed': sum('MR10' in pilot_failures[u] for u in pilot_units),
        'final_full_suite_killed': sum(bool(failures[u]) for u in units),
    }
    (out_dir / 'pilot_summary.json').write_text(json.dumps(pilot_summary, indent=2) + '\n')

    summary = {
        'catalog_rows': len(catalog), 'clean_rows': len(clean_rows), 'clean_passes': sum(r['pass'] for r in clean_rows),
        'mutant_rows': len(mutant_rows), 'failing_mutant_rows': sum(not r['pass'] for r in mutant_rows),
        'defect_units': len(units), 'full_suite_killed': sum(bool(failures[u]) for u in units),
        'breadth_rows': len(breadth), 'breadth_passes': sum(r['pass'] for r in breadth),
        'suite_counts': {r['suite']: r['killed_units'] for r in suite_rows},
        'relation_counts': {r['relation_id']: r['killed_units'] for r in relation_rows},
        'greedy_order': [step['relation_id'] for step in greedy],
        'pilot': pilot_summary,
    }
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def write_manifest(root: Path, entries: list[Path], output: Path) -> None:
    rows = []
    for path in entries:
        rows.append({'path': str(path.relative_to(root)), 'sha256': sha(path), 'bytes': path.stat().st_size})
    output.write_text(json.dumps({'schema_version': '1.0', 'entries': rows}, indent=2) + '\n')
