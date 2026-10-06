"""Bounded byte-record, mocked-tool and admission regressions; no compilation."""
import csv
import importlib.util
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from tosem02.accounting import activation_mode, summarize_rows
from tosem02.admission import evaluate, extract_observation
from tosem02.catalog import artifact_root
from tosem02.evidence_boundary import Candidate, ObservationUnavailable, ToolObservationError, first_valid_candidate
from tosem02.model import BuildResult, ExtractionError
from tosem02.pipeline import Pipeline
from tosem02.record import MAGIC, locate_record, make_record, parse_record
from tosem02.relations import KEY1, KEY2, PAYLOAD1, PAYLOAD2


class RecordModelTests(unittest.TestCase):
    def assert_kind(self, blob, kind, key=KEY1):
        with self.assertRaises(ExtractionError) as caught:
            parse_record(blob, key)
        self.assertEqual(caught.exception.kind, kind)

    def test_zero_offset_and_empty_payload_are_accepted(self):
        for payload in (b'', PAYLOAD1):
            record = make_record(payload, KEY1)
            self.assertEqual(parse_record(record, KEY1), payload)
            self.assertEqual(locate_record(record, KEY1), (0, len(record)))

    def test_absolute_positions_after_false_magic(self):
        prefix = MAGIC + b'\xff' * 19 + b'prefix'
        record = make_record(PAYLOAD1, KEY1)
        self.assertEqual(parse_record(prefix + record, KEY1), PAYLOAD1)
        self.assertEqual(locate_record(prefix + record, KEY1), (len(prefix), len(prefix) + len(record)))

    def test_invalid_candidates_do_not_hide_a_later_valid_record(self):
        valid = make_record(PAYLOAD2, KEY1)
        wrong_version = bytearray(make_record(PAYLOAD1, KEY1)); wrong_version[4] = 2
        truncated = bytearray(make_record(PAYLOAD1, KEY1)); truncated[13:15] = b'\xff\xff'
        corrupt = bytearray(make_record(PAYLOAD1, KEY1)); corrupt[-1] ^= 1
        for prefix in (MAGIC, bytes(wrong_version), bytes(truncated),
                       make_record(PAYLOAD1, KEY2), bytes(corrupt)):
            with self.subTest(prefix=prefix.hex()):
                self.assertEqual(parse_record(prefix + valid, KEY1), PAYLOAD2)
                self.assertEqual(locate_record(prefix + valid, KEY1), (len(prefix), len(prefix) + len(valid)))

    def test_first_of_two_valid_records_wins(self):
        first = make_record(b'', KEY1); second = make_record(PAYLOAD2, KEY1)
        self.assertEqual(parse_record(first + second, KEY1), b'')
        self.assertEqual(locate_record(first + second, KEY1), (0, len(first)))

    def test_no_magic_and_unique_typed_rejections(self):
        self.assert_kind(b'plain bytes', 'absent')
        self.assert_kind(MAGIC, 'malformed')
        version = bytearray(make_record(PAYLOAD1, KEY1)); version[4] = 2
        self.assert_kind(bytes(version), 'version')
        self.assert_kind(make_record(PAYLOAD1, KEY2), 'wrong-key')
        corrupt = bytearray(make_record(PAYLOAD1, KEY1)); corrupt[-1] ^= 1
        self.assert_kind(bytes(corrupt), 'checksum')

    def test_rejection_priority_is_deterministic(self):
        version = bytearray(make_record(PAYLOAD1, KEY1)); version[4] = 2
        wrong_key = make_record(PAYLOAD1, KEY2)
        corrupt = bytearray(make_record(PAYLOAD1, KEY1)); corrupt[-1] ^= 1
        self.assert_kind(bytes(version) + wrong_key + MAGIC, 'wrong-key')
        self.assert_kind(wrong_key + bytes(corrupt), 'checksum')
        self.assert_kind(bytes(corrupt) + wrong_key, 'checksum')

    def test_integrity_bypass_remains_a_distinct_seeded_behavior(self):
        corrupt = bytearray(make_record(PAYLOAD1, KEY1)); corrupt[-1] ^= 1
        self.assertEqual(parse_record(bytes(corrupt), KEY1, checksum_bypass=True), PAYLOAD1)
        self.assert_kind(bytes(corrupt), 'checksum')

    def test_key_ignored_seed_retains_empty_payload(self):
        self.assertEqual(parse_record(make_record(b'', KEY1, key_ignored=True), KEY2, key_ignored=True), b'')

    def test_scanner_requires_explicit_success_and_rejects_empty_magic(self):
        self.assertEqual(first_valid_candidate(b'X', b'X', lambda _: Candidate(0, 1, b''), lambda: None), Candidate(0, 1, b''))
        with self.assertRaises(TypeError):
            first_valid_candidate(b'X', b'X', lambda _: (0, 1), lambda: None)
        with self.assertRaises(ValueError):
            first_valid_candidate(b'X', b'', lambda _: None, lambda: None)


class ByteBuildPipeline(Pipeline):
    """Materialize record bytes, not executable files, for deterministic models."""
    def __init__(self, carrier='string', mutant='CLEAN'):
        super().__init__(carrier, mutant)
        self.events = []
        self.requests = []

    def build(self, request):
        self.build_counter += 1
        request.work_dir.mkdir(parents=True, exist_ok=True)
        binary = request.work_dir / 'artifact.bin'
        binary.write_bytes(make_record(request.payload, request.key) if request.marked else b'unmarked')
        self.events.append('B' + str(self.build_counter))
        self.requests.append(request)
        self.original_paths.add(binary.resolve())
        return BuildResult(binary, request.host, request.compiler, request.compiler,
                           request.optimization, request.optimization, self.carrier,
                           self.mutant_id, [], '', '', 0, '', request.payload.hex(),
                           request.payload.hex(), request.key)

    def extract(self, binary, key):
        index = next((i for i, request in enumerate(self.requests, 1)
                      if binary == request.work_dir / 'artifact.bin'), 0)
        self.events.append('X' + str(index))
        return super().extract(binary, key)


class WiringModelTests(unittest.TestCase):
    def setUp(self):
        self.host = artifact_root() / 'hosts/H01-gcd.c'

    def test_real_instance_removal_uses_absolute_valid_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); pipeline = ByteBuildPipeline()
            from tosem02.model import BuildRequest
            result = pipeline.build(BuildRequest(self.host, PAYLOAD1, KEY1, 'gcc', 'O2', root/'source'))
            prefix = MAGIC + b'\xff' * 19
            result.binary.write_bytes(prefix + result.binary.read_bytes())
            target = pipeline.remove_carrier(result, root/'removed')
            self.assertEqual(target.read_bytes()[:len(prefix)], prefix)
            self.assertEqual(target.read_bytes()[len(prefix):len(prefix)+4], b'XXXX')
            with self.assertRaises(ExtractionError):
                pipeline.extract(target, KEY1)

    def test_corruption_uses_absolute_checksum_offset_after_false_magic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); pipeline = ByteBuildPipeline()
            from tosem02.model import BuildRequest
            result = pipeline.build(BuildRequest(self.host, PAYLOAD1, KEY1, 'gcc', 'O2', root/'source'))
            prefix = MAGIC + b'\xff' * 19
            source = prefix + result.binary.read_bytes()
            result.binary.write_bytes(source)
            target = pipeline.corrupt_carrier(result, root/'corrupt')
            changed = [index for index, (a, b) in enumerate(zip(source, target.read_bytes())) if a != b]
            self.assertEqual(changed, [len(source)-1])
            with self.assertRaises(ExtractionError) as caught:
                pipeline.extract(target, KEY1)
            self.assertEqual(caught.exception.kind, 'checksum')

    def test_noop_removal_gate_not_an_extractor_kill(self):
        with tempfile.TemporaryDirectory() as temp:
            outcome = evaluate('MR09', ByteBuildPipeline(mutant='M15'), self.host, Path(temp)/'case')
        self.assertEqual((outcome.verdict, outcome.reason), ('INADMISSIBLE', 'carrier_removed'))

    def test_verified_corruption_and_bypass_have_opposite_verdicts(self):
        for mutant, expected in (('CLEAN', 'SATISFIED'), ('M16', 'INCONSISTENT')):
            with tempfile.TemporaryDirectory() as temp:
                outcome = evaluate('MR10', ByteBuildPipeline(mutant=mutant), self.host, Path(temp)/'case')
            self.assertEqual(outcome.verdict, expected)
            self.assertTrue(all(outcome.admission.values()))
            self.assertEqual(outcome.observations['followup_carrier'], {'kind': 'rejection', 'value': 'checksum'})

    def test_mr13_actual_order_settings_and_three_predicates(self):
        for mutant, expected in (('CLEAN', 'SATISFIED'), ('M23', 'INCONSISTENT')):
            with tempfile.TemporaryDirectory() as temp:
                pipeline = ByteBuildPipeline(mutant=mutant)
                outcome = evaluate('MR13', pipeline, self.host, Path(temp)/'case')
            self.assertEqual(pipeline.events, ['B1', 'B2', 'X1', 'X2', 'X1'])
            self.assertEqual([r.payload for r in pipeline.requests], [PAYLOAD1, PAYLOAD2])
            self.assertEqual({(r.key, r.compiler, r.optimization) for r in pipeline.requests}, {(KEY1, 'gcc', 'O2')})
            self.assertEqual(outcome.verdict, expected)
            if mutant == 'M23':
                self.assertEqual(outcome.observations['after']['value'], PAYLOAD2.hex())

    def test_integrated_section_absence_and_dump_failures(self):
        for mode in ('absent', 'readelf-failure', 'empty-listing', 'dump-failure', 'missing-dump', 'io-failure', 'present'):
            def run(argv, **kwargs):
                if mode == 'io-failure':
                    raise OSError('model I/O failure')
                if '-S' in argv:
                    if mode == 'empty-listing':
                        return subprocess.CompletedProcess(argv, 0, '', '')
                    return subprocess.CompletedProcess(argv, 1 if mode == 'readelf-failure' else 0,
                        '  [ 1] .text PROGBITS\n' if mode == 'absent' else '  [ 1] .wmrec PROGBITS\n', '')
                if mode == 'present':
                    Path(next(x.split('=', 1)[1] for x in argv if x.startswith('.wmrec='))).write_bytes(make_record(PAYLOAD1, KEY1))
                return subprocess.CompletedProcess(argv, 2 if mode == 'dump-failure' else 0, '', '')
            with patch('tosem02.pipeline.subprocess.run', side_effect=run):
                if mode in ('absent', 'present'):
                    observation = extract_observation(Pipeline('section'), self.host, KEY1)
                    self.assertEqual(observation, {'kind': 'rejection', 'value': 'absent'} if mode == 'absent'
                                     else {'kind': 'payload', 'value': PAYLOAD1.hex()})
                else:
                    with self.assertRaises(ToolObservationError):
                        extract_observation(Pipeline('section'), self.host, KEY1)

    def test_section_observation_failure_is_inadmissible_at_real_gate(self):
        with tempfile.TemporaryDirectory() as temp, patch('tosem02.pipeline.subprocess.run', side_effect=OSError()):
            outcome = evaluate('MR03', ByteBuildPipeline('section'), self.host, Path(temp)/'case')
        self.assertEqual(outcome.verdict, 'INADMISSIBLE')
        self.assertFalse(outcome.exposed)
        self.assertIn('ToolObservationError', outcome.reason)

    def test_present_section_integrity_bypass_is_not_absence(self):
        corrupt = bytearray(make_record(PAYLOAD1, KEY1)); corrupt[-1] ^= 1
        def run(argv, **kwargs):
            if '-S' in argv:
                return subprocess.CompletedProcess(argv, 0, '  [ 1] .wmrec PROGBITS\n', '')
            Path(next(x.split('=', 1)[1] for x in argv if x.startswith('.wmrec='))).write_bytes(bytes(corrupt))
            return subprocess.CompletedProcess(argv, 0, '', '')
        with patch('tosem02.pipeline.subprocess.run', side_effect=run):
            pipeline = Pipeline('section', 'M16')
            self.assertEqual(pipeline.extract(self.host, KEY1), PAYLOAD1)
            with self.assertRaises(ExtractionError) as caught:
                pipeline.extract_for_validation(self.host, KEY1)
            self.assertEqual(caught.exception.kind, 'checksum')


class ExternalOutputModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = artifact_root() / 'external-transfer/run_external_transfer.py'
        spec = importlib.util.spec_from_file_location('transfer_model', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_two_missing_files_are_not_equal_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = self.module.output_observation('119', 'before', root, '', 0)
            b = self.module.output_observation('119', 'watermarked', root, '', 0)
        self.assertFalse(a['available']); self.assertFalse(b['available'])
        before = {'compile_rc': 0, 'run_rc': 0, 'output_available': a['available'], 'output': a['value']}
        after = {'compile_rc': 0, 'run_rc': 0, 'output_available': b['available'], 'output': b['value']}
        self.assertEqual(self.module.host_pair_verdict(before, after), 'INADMISSIBLE')
        self.assertEqual(self.module.relocation_verdict(0, 0, 0, a, b), 'INADMISSIBLE')

    def test_matching_nonzero_exits_do_not_pass_relocation(self):
        observed = {'available': True, 'value': 'same'}
        self.assertEqual(self.module.relocation_verdict(0, 1, 1, observed, observed), 'INADMISSIBLE')
        for rc in (1, None):
            observation = self.module.output_observation('363', 'before', Path('.'), 'same', rc)
            self.assertFalse(observation['available'])

    def test_empty_stdout_and_empty_existing_files_are_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'nr_before.txt').write_text('', encoding='utf-8')
            for case in ('119', '363'):
                observation = self.module.output_observation(case, 'before', root, '', 0)
                self.assertEqual(observation['value'], '')
                self.assertTrue(observation['available'])
                self.assertEqual(self.module.relocation_verdict(0, 0, 0, observation, observation), 'SATISFIED')

    def test_observed_inequality_remains_inconsistent(self):
        before = {'compile_rc': 0, 'run_rc': 0, 'output_available': True, 'output': 'a'}
        after = dict(before, output='b')
        self.assertEqual(self.module.host_pair_verdict(before, after), 'INCONSISTENT')

    def test_unreadable_required_output_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch('tosem02.evidence_boundary.Path.is_file', return_value=True), \
                 patch('tosem02.evidence_boundary.Path.read_text', side_effect=OSError('read failed')):
                observed = self.module.output_observation('119', 'before', root, '', 0)
        self.assertFalse(observed['available'])
        self.assertIsNone(observed['value'])


class RetainedAccountingTests(unittest.TestCase):
    def test_gated_matrix_partition_and_verdicts(self):
        with (artifact_root()/'results/admission-study/matrix.csv').open(newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        accounting = summarize_rows(rows)
        self.assertEqual((accounting['configured_rows'], accounting['clean_rows'], accounting['stage_isolation_rows'],
                          accounting['fault_active_rows']), (18900, 756, 972, 17172))
        self.assertEqual(accounting['verdicts_by_activation'], {
            'CLEAN': {'SATISFIED': 756}, 'STAGE_ISOLATION': {'SATISFIED': 972},
            'FAULT_ACTIVE': {'SATISFIED': 11898, 'INCONSISTENT': 4266, 'INADMISSIBLE': 1008}})
        self.assertEqual(activation_mode('MR04', 'M01'), 'STAGE_ISOLATION')

    def test_utility_groups_do_not_imply_360_host_checks(self):
        with (artifact_root()/'results/raw/adverse_transformations.csv').open(newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        groups = Counter('PRESERVATION_VERIFIED' if row['pass']=='True' and row['expected']=='preserve'
                         else 'REJECTION_ONLY' if row['pass']=='True' and row['expected']=='reject'
                         else 'INCOMPATIBLE' for row in rows)
        self.assertEqual(groups, {'PRESERVATION_VERIFIED': 288, 'REJECTION_ONLY': 72, 'INCOMPATIBLE': 18})
        self.assertTrue(all(row['host_outputs_equal']=='True' for row in rows if row['pass']=='True' and row['expected']=='preserve'))
        self.assertTrue(all(row['host_outputs_equal']=='False' for row in rows if row['expected']=='reject'))


if __name__ == '__main__':
    unittest.main()
