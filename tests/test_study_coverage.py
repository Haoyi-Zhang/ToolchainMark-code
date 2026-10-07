"""Self-contained coverage controls: no compiler, host execution or old code."""
import contextlib
import importlib.util
import io
import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tosem02.study_coverage import (
    StudyCoverageError, coverage_report, require_study_coverage,
)


FIELDS = ('host', 'carrier', 'defect_id', 'relation_id')
TINY = (
    ('owned-host', 'string', 'CLEAN', 'MR01'),
    ('owned-host', 'string', 'CLEAN', 'MR02'),
    ('owned-host', 'string', 'M01', 'MR01'),
    ('owned-host', 'string', 'M01', 'MR02'),
)
UNKNOWN = ('owned-host', 'string', 'CLEAN', 'MR99')
ROOT = Path(__file__).resolve().parents[1]


def row(key):
    return dict(zip(FIELDS, key))


def literal_full_rows():
    # Independent, test-local statement of the supplied producer contract.
    hosts = ('H01-gcd.c', 'H02-fibonacci.c', 'H03-bitmix.c', 'H04-polynomial.c',
             'H05-crc.c', 'H06-primecount.c', 'H07-sortfold.c', 'H08-statemachine.c',
             'H09-matrix.c', 'H10-parser.c', 'H11-popcount.c', 'H12-lcg.c',
             'H13-zlib.c', 'H14-openssl.c', 'H15-sqlite.c', 'H16-xml.c',
             'H17-json.c', 'H18-png.c')
    defects = ('CLEAN', 'M01', 'M02', 'M03', 'M04', 'M05', 'M06', 'M07', 'M08',
               'M09', 'M10', 'M11', 'M12', 'M13', 'M14', 'M15', 'M16', 'M17',
               'M18', 'M19', 'M20', 'M21', 'M22', 'M23', 'M24')
    relations = ('MR01', 'MR02', 'MR03', 'MR04', 'MR05', 'MR06', 'MR07',
                 'MR08', 'MR09', 'MR10', 'MR11', 'MR12', 'MR13', 'MR14')
    return [row((h, c, d, r)) for h in hosts for c in ('string', 'symbol', 'section')
            for d in defects for r in relations]


def reference_keys(observed, expected):
    # Literal list membership/counting, not the production Counter/set method.
    expected = list(expected)
    distinct = []
    for key in observed:
        if key not in distinct:
            distinct.append(key)
    missing = [key for key in expected if key not in observed]
    unexpected = [key for key in distinct if key not in expected]
    duplicates = [key for key in distinct if observed.count(key) > 1]
    return dict(complete=not missing and not unexpected and not duplicates,
                expected_rows=len(expected), observed_rows=len(observed),
                missing_keys=len(missing), unexpected_keys=len(unexpected),
                duplicate_keys=len(duplicates),
                duplicate_rows=sum(observed.count(key) - 1 for key in duplicates),
                missing_examples=sorted(missing, key=repr)[:20],
                unexpected_examples=sorted(unexpected, key=repr)[:20],
                duplicate_examples=[dict(key=key, occurrences=observed.count(key))
                                    for key in sorted(duplicates, key=repr)[:20]])


class StudyCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('current_study_derivation',
                            ROOT / 'scripts/derive_admission_study.py')
        cls.derivation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.derivation)

    def test_exhaustive_tiny_sequences_match_literal_reference(self):
        comparisons = 0
        for length in range(5):
            for observed in itertools.product(TINY + (UNKNOWN,), repeat=length):
                self.assertEqual(coverage_report(map(row, observed), TINY),
                                 reference_keys(list(observed), TINY))
                comparisons += 1
        self.assertEqual(comparisons, 781)

    def test_every_key_coordinate_and_unknown_clean_id_are_exact(self):
        for coordinate, replacement in ((0, 'another-host'), (1, 'another-carrier'),
                (2, 'clean'), (2, 'CLEAN-unknown'), (2, 'M99'), (3, 'MR99')):
            observed = list(TINY)
            changed = list(observed[0]); changed[coordinate] = replacement
            observed[0] = tuple(changed)
            with self.subTest(coordinate=coordinate, replacement=replacement):
                report = coverage_report(map(row, observed), TINY)
                self.assertEqual(report, reference_keys(observed, TINY))
                self.assertEqual((report['missing_keys'], report['unexpected_keys'],
                                  report['duplicate_rows']), (1, 1, 0))

    def test_missing_fields_are_not_a_clean_or_relation_alias(self):
        for field in FIELDS:
            observed = [row(key) for key in TINY]
            del observed[0][field]
            report = coverage_report(observed, TINY)
            self.assertFalse(report['complete'])
            self.assertEqual((report['missing_keys'], report['unexpected_keys']), (1, 1))

    def test_example_caps_do_not_cap_missing_or_duplicate_counts(self):
        expected = [('h', 'c', 'd', str(index)) for index in range(35)]
        empty = coverage_report([], expected)
        self.assertEqual(empty['missing_keys'], 35)
        self.assertEqual(len(empty['missing_examples']), 20)
        observed = expected + expected + [UNKNOWN] * 3
        report = coverage_report(map(row, observed), expected)
        self.assertEqual(report, reference_keys(observed, expected))
        self.assertEqual((report['duplicate_keys'], report['duplicate_rows']), (36, 37))
        self.assertEqual(len(report['duplicate_examples']), 20)

    def test_order_and_outcome_metadata_do_not_change_coverage(self):
        observed = [dict(row(key), verdict='INADMISSIBLE', exposed='False',
                         reason='owned-negative-control', admission_json='{"ready":false}')
                    for key in reversed(TINY)]
        self.assertTrue(coverage_report(iter(observed), TINY)['complete'])
        self.assertFalse(coverage_report(observed + observed[:1], TINY)['complete'])

    def test_full_plan_matches_supplied_producer_declarations(self):
        expected = literal_full_rows()
        self.assertEqual(len(expected), 18900)
        self.assertTrue(coverage_report(reversed(expected))['complete'])
        self.assertTrue(all(value['complete'] for value in
                            require_study_coverage(expected, expected).values()))
        hosts = {value['host'] for value in expected}
        self.assertEqual(hosts, {path.name for path in (ROOT / 'hosts').glob('H*.c')})
        mutants = json.loads((ROOT / 'specs/mutants.json').read_text())['mutants']
        relations = json.loads((ROOT / 'specs/mrspec.json').read_text())['relations']
        self.assertEqual({value['defect_id'] for value in expected},
                         {'CLEAN'} | {value['id'] for value in mutants})
        self.assertEqual({value['relation_id'] for value in expected},
                         {value['id'] for value in relations})
        # Partial producer smoke domains are deliberately not full studies.
        for partial in (expected[:14], [value for value in expected
                                       if value['defect_id'] == 'CLEAN']):
            with self.assertRaises(StudyCoverageError):
                require_study_coverage(partial)

    def test_cli_rejects_duplicates_substitutions_and_wrong_matching_reruns(self):
        planned = literal_full_rows()
        variants = [
            ('duplicate', [planned[1]] + planned[1:], planned),
            ('unknown-clean-id', [dict(planned[0], defect_id='CLEAN-unknown')] + planned[1:], planned),
            ('matching-wrong', [dict(planned[0], relation_id='MR99')] + planned[1:],
                               [dict(planned[0], relation_id='MR99')] + planned[1:]),
            ('wrong-rerun-only', planned, [dict(planned[0], host='unknown.c')] + planned[1:]),
        ]
        for label, first, second in variants:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(self.derivation, 'rows', side_effect=[first, second]), \
                    contextlib.redirect_stdout(io.StringIO()) as stdout:
                result = self.derivation.main(['--matrix', 'owned-first.csv', '--rerun',
                    'owned-second.csv', '--mutants', 'never-opened.json', '--out', tmp])
                self.assertEqual(result, 1)
                gate = json.loads((Path(tmp) / 'scientific_checks.json').read_text())
                self.assertEqual(gate['verdict'], 'FAIL')
                self.assertEqual(gate['failed'], ['planned_key_domain_complete'])
                self.assertEqual(gate['remaining_study_checks'], 'NOT_RUN')
                self.assertEqual(json.loads(stdout.getvalue()), {'scientific_checks': gate})
                self.assertEqual({path.name for path in Path(tmp).iterdir()},
                                 {'scientific_checks.json'})
                failing = gate['coverage']['rerun' if label == 'wrong-rerun-only' else 'matrix']
                self.assertEqual(failing['missing_keys'], 1)
                self.assertEqual(failing['duplicate_rows'], 1 if label == 'duplicate' else 0)
                self.assertEqual(failing['unexpected_keys'], 0 if label == 'duplicate' else 1)

    def test_exact_grid_does_not_bypass_original_row_semantic_assertions(self):
        base = [dict(value, verdict='SATISFIED', exposed='False', admission_json='{"ready":true}')
                for value in literal_full_rows()]
        for label, changes in (('bad-verdict', {'verdict': 'PASS'}),
                ('clean-exposure', {'exposed': 'True'}),
                ('failed-admission', {'admission_json': '{"ready":false}'})):
            first = [dict(base[0], **changes)] + base[1:]
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(self.derivation, 'rows', return_value=first):
                with self.assertRaises(AssertionError):
                    self.derivation.derive(Path('owned-input.csv'), ROOT / 'specs/mutants.json',
                                           Path(tmp))
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_real_tiny_csvs_preserve_inputs_and_fail_without_deriving(self):
        import csv
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrices = [root / 'first.csv', root / 'second.csv']
            for path in matrices:
                with path.open('w', newline='', encoding='utf-8') as handle:
                    writer = csv.DictWriter(handle, fieldnames=FIELDS)
                    writer.writeheader()
                    writer.writerows(row(key) for key in TINY + (TINY[0],))
            original = [path.read_bytes() for path in matrices]
            with contextlib.redirect_stdout(io.StringIO()):
                code = self.derivation.main(['--matrix', str(matrices[0]), '--rerun',
                    str(matrices[1]), '--mutants', str(root / 'never-opened.json'),
                    '--out', str(root / 'diagnostics')])
            self.assertEqual(code, 1)
            self.assertEqual([path.read_bytes() for path in matrices], original)
            gate = json.loads((root / 'diagnostics/scientific_checks.json').read_text())
            for report in gate['coverage'].values():
                self.assertEqual((report['expected_rows'], report['observed_rows'],
                    report['missing_keys'], report['unexpected_keys'], report['duplicate_rows']),
                    (18900, 5, 18900, 4, 1))


if __name__ == '__main__':
    unittest.main()
