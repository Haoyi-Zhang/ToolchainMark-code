"""Configured activation groups, distinct from admission and verdict."""
from collections import Counter

GUARDED_RELATIONS = frozenset({'MR04', 'MR09', 'MR10'})
GUARDED_OPERATORS = frozenset({'M01', 'M02', 'M03', 'M04', 'M05', 'M12'})


def activation_mode(relation: str, defect: str) -> str:
    if defect == 'CLEAN':
        return 'CLEAN'
    if relation in GUARDED_RELATIONS and defect in GUARDED_OPERATORS:
        return 'STAGE_ISOLATION'
    return 'FAULT_ACTIVE'


def summarize_rows(rows) -> dict:
    groups = {name: Counter() for name in ('CLEAN', 'STAGE_ISOLATION', 'FAULT_ACTIVE')}
    for row in rows:
        groups[activation_mode(row['relation_id'], row['defect_id'])][row['verdict']] += 1
    totals = {name: sum(counts.values()) for name, counts in groups.items()}
    return {
        'configured_rows': sum(totals.values()),
        'clean_rows': totals['CLEAN'],
        'nonclean_configured_rows': totals['STAGE_ISOLATION'] + totals['FAULT_ACTIVE'],
        'stage_isolation_rows': totals['STAGE_ISOLATION'],
        'fault_active_rows': totals['FAULT_ACTIVE'],
        'verdicts_by_activation': {name: dict(sorted(counts.items())) for name, counts in groups.items()},
    }
