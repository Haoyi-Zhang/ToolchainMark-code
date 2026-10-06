#!/usr/bin/env python3
"""Read-only verification of retained evidence; not a compiled campaign replay."""
import csv
import json
from pathlib import Path
from derive_observation_accounting import derive
from tosem02.catalog import load_mutants, load_relations
from tosem02.evidence_catalog import load as load_evidence

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def main():
    data = derive()
    actual = data['admission_denominators']
    saved = json.loads((ROOT/'results/admission_denominators.json').read_text(encoding='utf-8'))
    checks = {
        'fourteen_relation_declarations': len(load_relations()) == 14,
        'twenty_four_operator_declarations': len(load_mutants()) == 24,
        'evidence_catalog_schema_valid': len(load_evidence()) == 14,
        'saved_gated_denominators_recomputed': all(saved.get(key) == value for key, value in actual.items()),
        'configured_partition_18900': actual['configured_rows'] == 18900,
        'clean_756': actual['clean_rows'] == 756,
        'stage_isolation_972_satisfied': actual['stage_isolation_rows'] == 972 and
            actual['verdicts_by_activation']['STAGE_ISOLATION'] == {'SATISFIED': 972},
        'active_17172_three_valued': actual['fault_active_rows'] == 17172 and
            actual['verdicts_by_activation']['FAULT_ACTIVE'] ==
            {'SATISFIED': 11898, 'INCONSISTENT': 4266, 'INADMISSIBLE': 1008},
        'utility_378_partition': data['utility_summary'] ==
            json.loads((ROOT/'results/external_transformations_observation_scopes.summary.json').read_text(encoding='utf-8')),
        'utility_scope_rows_recomputed': data['utility_rows'] ==
            read_rows(ROOT/'results/external_transformations_observation_scopes.csv'),
    }
    first = read_rows(ROOT/'results/admission-study/matrix.csv')
    second = read_rows(ROOT/'results/admission-study/rerun.csv')
    def key(row):
        return tuple(row[name] for name in ('host', 'carrier', 'defect_id', 'relation_id'))
    left = {key(row): row for row in first}
    right = {key(row): row for row in second}
    fields = [name for name in first[0] if name != 'duration_seconds']
    checks['retained_keys_unique_and_equal'] = len(left) == len(first) == len(right) == len(second) == 18900 and set(left) == set(right)
    checks['eleven_retained_fields_equal'] = len(fields) == 11 and all(
        key_ in right and all(row[name] == right[key_][name] for name in fields)
        for key_, row in left.items())
    checks['positive_retained_durations'] = all(float(row['duration_seconds']) > 0 for row in first + second)
    checks['exposure_requires_inconsistent_nonclean'] = all(
        (row['exposed'] == 'True') == (row['verdict'] == 'INCONSISTENT' and row['defect_id'] != 'CLEAN') for row in first)
    checks['inconsistent_rows_complete_gate'] = all(
        all(value is True for value in json.loads(row['admission_json']).values())
        for row in first if row['verdict'] == 'INCONSISTENT')
    def replay_value(row):
        return row['verdict'], row['reason'] if row['verdict'] == 'INADMISSIBLE' else ''
    replay = [row for row in first if row['host'] != 'H01-gcd.c' and row['defect_id'] != 'CLEAN']
    checks['replay_includes_inadmissible_reasons'] = len(replay) == 17136 and all(
        replay_value(row) == replay_value(left[('H01-gcd.c', row['carrier'], row['defect_id'], row['relation_id'])])
        for row in replay)
    result = {'checks': checks, 'failed': [key_ for key_, value in checks.items() if not value],
              'verdict': 'PASS' if all(checks.values()) else 'FAIL',
              'scope': 'Retained-row accounting, stored-field replay and catalog schema only. No compiler, utility, external source or PDF campaign is executed; interface behavior requires the separate model tests and compiled replay.'}
    print(json.dumps(result, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
