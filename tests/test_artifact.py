from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tosem02.catalog import artifact_root, load_mutants, load_relations
from tosem02.model import BuildRequest, ExtractionError
from tosem02.pipeline import Pipeline
from tosem02.record import make_record, parse_record
from tosem02.relations import HANDLERS, KEY1, KEY2, PAYLOAD1


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.root = artifact_root()
        self.host = self.root / 'hosts/H01-gcd.c'

    def test_01_catalog_handler_equality(self):
        self.assertEqual({r['id'] for r in load_relations()}, set(HANDLERS))

    def test_02_positive_and_negative_polarities(self):
        polarities = {r['polarity'] for r in load_relations()}
        self.assertTrue({'preserve', 'reject', 'separate', 'trace'} <= polarities)

    def test_03_logical_record_roundtrip(self):
        record = make_record(PAYLOAD1, KEY1)
        self.assertEqual(parse_record(record, KEY1), PAYLOAD1)

    def test_04_wrong_key_rejected(self):
        record = make_record(PAYLOAD1, KEY1)
        with self.assertRaises(ExtractionError):
            parse_record(record, KEY2)

    def test_05_checksum_corruption_rejected(self):
        record = bytearray(make_record(PAYLOAD1, KEY1))
        record[-1] ^= 1
        with self.assertRaises(ExtractionError):
            parse_record(bytes(record), KEY1)

    def test_06_clean_roundtrip_all_carriers(self):
        with tempfile.TemporaryDirectory() as tmp:
            for carrier in ['string', 'symbol', 'section']:
                pipeline = Pipeline(carrier)
                result = pipeline.build(BuildRequest(self.host, PAYLOAD1, KEY1, 'gcc', 'O2', Path(tmp) / carrier))
                self.assertEqual(pipeline.extract(result.binary, KEY1), PAYLOAD1)

    def test_07_legacy_noop_fixture_leaves_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = Pipeline('string', 'M15')
            root = Path(tmp)
            result = pipeline.build(BuildRequest(self.host, PAYLOAD1, KEY1, 'gcc', 'O2', root / 'source', guard_upstream=True))
            removed = pipeline.remove_carrier(result, root / 'follow')
            self.assertEqual(pipeline.extract(removed, KEY1), PAYLOAD1)

    def test_08_eighteen_unique_subjects(self):
        hosts = sorted((self.root / 'hosts').glob('H*.c'))
        self.assertEqual(len(hosts), 18)
        self.assertEqual(len({path.read_bytes() for path in hosts}), 18)

    def test_09_library_backed_subjects_compile_with_both_compilers(self):
        names = ['H13-zlib.c', 'H14-openssl.c', 'H15-sqlite.c', 'H16-xml.c', 'H17-json.c', 'H18-png.c']
        with tempfile.TemporaryDirectory() as tmp:
            for name in names:
                for compiler in ('gcc', 'clang'):
                    pipeline = Pipeline('string')
                    work = Path(tmp) / name / compiler
                    result = pipeline.build(BuildRequest(self.root / 'hosts' / name, PAYLOAD1, KEY1, compiler, 'O2', work))
                    self.assertEqual(pipeline.extract(result.binary, KEY1), PAYLOAD1)

    def test_10_retained_boolean_matrix_cardinality_and_clean_controls(self):
        summary = json.loads((self.root / 'results/robustness-derived/robustness_summary.json').read_text())
        self.assertEqual(summary['rows'], 18900)
        self.assertEqual((summary['clean_passes'], summary['clean_rows']), (756, 756))
        self.assertEqual((summary['units_exposed'], summary['units']), (1296, 1296))

    def test_11_retained_boolean_rerun_non_timing_fields(self):
        report = json.loads((self.root / 'results/fresh-rerun-2026-07-24/comparison_report.json').read_text())
        self.assertEqual(report['compared_rows'], 18900)
        self.assertEqual(report['non_timing_field_comparisons'], 302400)
        self.assertEqual(report['non_timing_differences'], 0)
        self.assertEqual(report['verdict'], 'PASS')

    def test_12_adverse_utility_result_is_retained(self):
        summary = json.loads((self.root / 'results/raw/adverse_transformations.summary.json').read_text())
        self.assertEqual((summary['rows'], summary['passes'], summary['violations']), (378, 360, 18))
        self.assertEqual(summary['violations_by_operation'], {'llvm_full_strip': 18})
        self.assertEqual(summary['violations_by_carrier'], {'section': 18})

    def test_13_twenty_four_operators_cover_every_relation_directly(self):
        mutants = load_mutants()
        self.assertEqual(len(mutants), 24)
        direct_relations = {row['primary_relation'] for row in mutants}
        self.assertEqual(direct_relations, {f'MR{i:02d}' for i in range(1, 15)})

    def test_14_prospective_witnesses_are_relation_specific(self):
        with (self.root / 'results/raw/catalog_matrix.csv').open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        expected = {'M20': {'MR12'}, 'M21': {'MR06'}, 'M22': {'MR07'}, 'M23': {'MR13'}, 'M24': {'MR14'}}
        for defect, relations in expected.items():
            for carrier in ('string', 'symbol', 'section'):
                observed = {
                    row['relation_id'] for row in rows
                    if row['defect_id'] == defect and row['carrier'] == carrier and row['pass'] == 'False'
                }
                self.assertEqual(observed, relations, (defect, carrier, observed))

    def test_15_state_relations_execute_distinct_action_signatures(self):
        with (self.root / 'results/raw/catalog_matrix.csv').open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        clean = {
            row['relation_id']: json.loads(row['observations_json'])
            for row in rows
            if row['carrier'] == 'string' and row['defect_id'] == 'CLEAN'
            and row['relation_id'] in {'MR05', 'MR12', 'MR13', 'MR14'}
        }
        self.assertEqual(clean['MR05']['execution_order'], 'sequential-builds-then-extract')
        self.assertEqual(clean['MR12']['execution_order'], 'overlapping-builds-then-extract')
        self.assertTrue(clean['MR13']['intervening_extraction'])
        self.assertEqual(clean['MR14']['execution_order'], 'build1-extract1-build2-extract2')

    def test_16_parallel_witness_is_schedule_invariant(self):
        observations = []
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(3):
                pipeline = Pipeline('string', 'M08')
                outcome = HANDLERS['MR12'](pipeline, self.host, Path(tmp) / str(index))
                self.assertFalse(outcome.passed)
                observations.append(outcome.observations)
        self.assertEqual(observations[0], observations[1])
        self.assertEqual(observations[1], observations[2])
        self.assertEqual(observations[0], {
            'execution_order': 'overlapping-builds-then-extract',
            'both_expected': False,
            'payloads_distinct': False,
            'aliasing_detected': True,
        })


if __name__ == '__main__':
    unittest.main()
