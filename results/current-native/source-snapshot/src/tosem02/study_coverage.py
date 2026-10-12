"""Exact configured-key coverage for the supplied full scientific study.

This is not an admission, exposure, replay, or provenance check. Partial native
smoke runs remain possible; their rows do not constitute this complete study.
"""
from collections import Counter
from itertools import product


KEY_FIELDS = ('host', 'carrier', 'defect_id', 'relation_id')
HOSTS = (
    'H01-gcd.c', 'H02-fibonacci.c', 'H03-bitmix.c', 'H04-polynomial.c',
    'H05-crc.c', 'H06-primecount.c', 'H07-sortfold.c', 'H08-statemachine.c',
    'H09-matrix.c', 'H10-parser.c', 'H11-popcount.c', 'H12-lcg.c',
    'H13-zlib.c', 'H14-openssl.c', 'H15-sqlite.c', 'H16-xml.c',
    'H17-json.c', 'H18-png.c',
)
CARRIERS = ('string', 'symbol', 'section')
DEFECTS = ('CLEAN',) + tuple(f'M{i:02d}' for i in range(1, 25))
RELATIONS = tuple(f'MR{i:02d}' for i in range(1, 15))
PLANNED_KEYS = frozenset(product(HOSTS, CARRIERS, DEFECTS, RELATIONS))


def coverage_report(rows, expected=PLANNED_KEYS):
    """Count exact defects; cap only diagnostic examples, not coverage checks.

Rows are CSV-style mappings of field names to strings (or missing values).
The optional expected set supports small finite model tests; the full-study
consumers do not expose an override or infer a plan from observations.
"""
    expected = frozenset(expected)
    counts = Counter(tuple(row.get(field) for field in KEY_FIELDS) for row in rows)
    missing = expected - counts.keys()
    unexpected = counts.keys() - expected
    duplicates = {key: count for key, count in counts.items() if count > 1}
    order = lambda keys: sorted(keys, key=repr)
    return dict(
        complete=not missing and not unexpected and not duplicates,
        expected_rows=len(expected), observed_rows=sum(counts.values()),
        missing_keys=len(missing), unexpected_keys=len(unexpected),
        duplicate_keys=len(duplicates),
        duplicate_rows=sum(count - 1 for count in duplicates.values()),
        missing_examples=order(missing)[:20],
        unexpected_examples=order(unexpected)[:20],
        duplicate_examples=[dict(key=key, occurrences=duplicates[key])
                            for key in order(duplicates)[:20]],
    )


class StudyCoverageError(ValueError):
    def __init__(self, reports):
        super().__init__('scientific rows do not cover the exact planned key domain')
        self.reports = reports


def require_study_coverage(first, second=None):
    reports = {'matrix': coverage_report(first)}
    if second is not None:
        reports['rerun'] = coverage_report(second)
    if not all(report['complete'] for report in reports.values()):
        raise StudyCoverageError(reports)
    return reports
