#!/usr/bin/env python3
"""Read-only accounting of retained rows; does not execute the toolchain."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from tosem02.accounting import summarize_rows

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def derive():
    matrix = ROOT / 'results/admission-study/matrix.csv'
    gated = read_rows(matrix)
    summary = summarize_rows(gated)
    summary['source_matrix'] = 'results/admission-study/matrix.csv'
    summary['source_matrix_sha256'] = hashlib.sha256(matrix.read_bytes()).hexdigest()
    active = summary['verdicts_by_activation']['FAULT_ACTIVE']
    summary.update(fault_active_satisfied_rows=active.get('SATISFIED', 0),
                   fault_active_inconsistent_rows=active.get('INCONSISTENT', 0),
                   fault_active_inadmissible_rows=active.get('INADMISSIBLE', 0),
                   stage_isolation_satisfied_rows=summary['verdicts_by_activation']['STAGE_ISOLATION'].get('SATISFIED', 0),
                   stage_isolation_inconsistent_rows=summary['verdicts_by_activation']['STAGE_ISOLATION'].get('INCONSISTENT', 0),
                   stage_isolation_inadmissible_rows=summary['verdicts_by_activation']['STAGE_ISOLATION'].get('INADMISSIBLE', 0))
    summary['tri_valued_context_replay_rule'] = 'Compare all three verdicts. Two inadmissible rows match only when their normalized reason category matches.'
    summary['guard_scope'] = {'relations': ['MR04', 'MR09', 'MR10'],
                            'operators': ['M01', 'M02', 'M03', 'M04', 'M05', 'M12'],
                            'interpretation': 'antecedent stage isolation; upstream fault disabled'}
    utility_rows = []
    for row in read_rows(ROOT / 'results/raw/adverse_transformations.csv'):
        if row['pass'] == 'True' and row['expected'] == 'preserve':
            scope, host_observed, host_equal = 'PRESERVATION_VERIFIED', 'true', row['host_outputs_equal']
        elif row['pass'] == 'True' and row['expected'] == 'reject':
            scope, host_observed, host_equal = 'REJECTION_ONLY', 'false', 'UNOBSERVED'
        else:
            scope, host_observed, host_equal = 'INCOMPATIBLE', 'false', 'UNOBSERVED'
        utility_rows.append({'host': row['host'], 'carrier': row['carrier'], 'operation': row['operation'],
                             'obligation_scope': scope, 'host_execution_observed': host_observed,
                             'host_output_equal': host_equal, 'expected': row['expected'],
                             'observed': row['observed'], 'error_kind': row['error_kind']})
    groups = Counter(row['obligation_scope'] for row in utility_rows)
    utility_summary = {'source_matrix': 'results/raw/adverse_transformations.csv', 'rows': len(utility_rows),
                       'preservation_verified_rows': groups['PRESERVATION_VERIFIED'],
                       'rejection_only_rows': groups['REJECTION_ONLY'], 'incompatible_rows': groups['INCOMPATIBLE']}
    return {'admission_denominators': summary, 'utility_summary': utility_summary, 'utility_rows': utility_rows}


if __name__ == '__main__':
    print(json.dumps(derive(), indent=2, sort_keys=True))
