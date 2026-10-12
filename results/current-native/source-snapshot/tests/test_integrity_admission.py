"""Checksum-locality controls on owned records and mocked ELF observations.

No compiler, binary utility, network, or external program is executed. The
symbol and section fixtures are observation models, not executable ELF files.
"""
import shutil
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tosem02.admission import evaluate, inspect_carrier
from tosem02.catalog import artifact_root
from tosem02.evidence_catalog import load
from tosem02.integrity import checksum_material, intervention_facts
from tosem02.model import BuildResult
from tosem02.pipeline import Pipeline
from tosem02.record import locate_record, make_record, symbol_names
from tosem02.relations import KEY1, PAYLOAD1


def model_utility(argv, **kwargs):
    """Return only observations of the owned fixture named in the request."""
    if argv[0] == 'nm':
        names = Path(argv[-1]).read_text(encoding='ascii').splitlines()
        return subprocess.CompletedProcess(argv, 0,
            '\n'.join('00000000 R ' + name for name in reversed(names)), '')
    if '-S' in argv:
        return subprocess.CompletedProcess(argv, 0, '  [ 1] .wmrec PROGBITS\n', '')
    if '--dump-section' in argv:
        destination = Path(next(value.split('=', 1)[1] for value in argv if value.startswith('.wmrec=')))
        destination.write_bytes(Path(argv[-1]).read_bytes())
        return subprocess.CompletedProcess(argv, 0, '', '')
    raise AssertionError('unexpected model utility request: ' + repr(argv))


class IntegrityModelPipeline(Pipeline):
    def __init__(self, carrier, change='checksum', mutant='CLEAN', inplace=False, prefix=b''):
        super().__init__(carrier, mutant)
        self.change = change
        self.inplace = inplace
        self.prefix = prefix
        self.source = self.followup = None
        self.followup_extractions = 0

    def build(self, request):
        request.work_dir.mkdir(parents=True, exist_ok=True)
        binary = request.work_dir / 'owned-carrier'
        if self.carrier == 'symbol':
            binary.write_text('\n'.join(symbol_names(request.payload, request.key)), encoding='ascii')
        else:
            binary.write_bytes(self.prefix + make_record(request.payload, request.key) + b'owned-tail')
        self.source = binary
        return BuildResult(binary, request.host, request.compiler, request.compiler,
                           request.optimization, request.optimization, self.carrier,
                           self.mutant_id, [], '', '', 0, '', request.payload.hex(),
                           request.payload.hex(), request.key)

    def corrupt_carrier(self, result, target_dir):
        target_dir.mkdir(parents=True, exist_ok=True)
        target = result.binary if self.inplace else target_dir / 'owned-followup'
        if not self.inplace:
            shutil.copy2(result.binary, target)
        if self.carrier == 'symbol':
            names = target.read_text(encoding='ascii').splitlines()
            changed = []
            for index, name in enumerate(names):
                fields = name.split('_')
                if self.change in {'checksum', 'payload+checksum', 'structure'}:
                    fields[-1] = (int(fields[-1], 16) ^ 1).to_bytes(8, 'big').hex()
                if self.change in {'payload', 'payload+checksum'} and index == 0:
                    chunk = bytearray.fromhex(fields[5]); chunk[0] ^= 1
                    fields[5] = chunk.hex()
                if self.change == 'structure':
                    fields[2] = 'ffff'
                changed.append('_'.join(fields))
            target.write_text('\n'.join(changed), encoding='ascii')
        else:
            data = bytearray(target.read_bytes())
            start, end = locate_record(bytes(data), KEY1)
            if self.change in {'checksum', 'payload+checksum', 'structure', 'outside'}:
                data[end - 1] ^= 1
            if self.change in {'payload', 'payload+checksum'}:
                data[start + 15] ^= 1
            if self.change == 'structure':
                data[start + 4] = 2
            if self.change == 'outside':
                data[-1] ^= 1
            target.write_bytes(data)
        self.followup = target
        return target

    def extract(self, binary, key):
        if self.followup is not None and binary == self.followup:
            self.followup_extractions += 1
        return super().extract(binary, key)


class IntegrityAdmissionTests(unittest.TestCase):
    def call(self, pipeline):
        host = artifact_root() / 'hosts/H01-gcd.c'
        with tempfile.TemporaryDirectory() as tmp, patch('subprocess.run', side_effect=model_utility):
            outcome = evaluate('MR10', pipeline, host, Path(tmp) / 'case')
            physical = inspect_carrier(pipeline.carrier, pipeline.followup, KEY1)
        return outcome, physical

    def test_same_premise_comparison_on_twelve_owned_cases(self):
        # Fixed before execution: three representations x four interventions.
        # Compare the old checksum-rejection gate, not a surrogate external tool.
        old_admitted = new_admitted = wrong_old_admissions = 0
        for carrier in ('string', 'section', 'symbol'):
            for change in ('checksum', 'none', 'payload', 'payload+checksum'):
                with self.subTest(carrier=carrier, change=change):
                    pipeline = IntegrityModelPipeline(carrier, change)
                    outcome, physical = self.call(pipeline)
                    legacy_gate = physical == {'kind': 'rejection', 'value': 'checksum'}
                    admitted = outcome.verdict != 'INADMISSIBLE'
                    self.assertEqual(legacy_gate, change != 'none')
                    self.assertEqual(admitted, change == 'checksum')
                    self.assertEqual(outcome.verdict, 'SATISFIED' if change == 'checksum' else 'INADMISSIBLE')
                    self.assertEqual(pipeline.followup_extractions, int(admitted))
                    old_admitted += legacy_gate
                    new_admitted += admitted
                    wrong_old_admissions += legacy_gate and change != 'checksum'
                    if change in {'payload', 'payload+checksum'}:
                        facts = outcome.observations['integrity_intervention']
                        self.assertFalse(facts['nonintervened_payload_preserved'])
                        self.assertFalse(facts['nonchecksum_material_preserved'])
                        self.assertEqual(facts['checksum_material_changed'], change == 'payload+checksum')
        self.assertEqual((old_admitted, new_admitted, wrong_old_admissions), (9, 3, 6))

    def test_verified_checksum_bypass_remains_inconsistent(self):
        declaration = next(row for row in load() if row['id'] == 'MR10')
        for carrier in ('string', 'section', 'symbol'):
            with self.subTest(carrier=carrier):
                outcome, _ = self.call(IntegrityModelPipeline(carrier, mutant='M16'))
                self.assertEqual(outcome.verdict, 'INCONSISTENT')
                self.assertTrue(outcome.exposed)
                self.assertTrue(all(outcome.admission.values()))
                self.assertEqual(set(outcome.admission), set(declaration['required_admission_facts']))
                self.assertEqual(set(outcome.observations), set(declaration['observation_keys']))

    def test_snapshot_precedes_inplace_payload_mutation(self):
        for carrier in ('string', 'section', 'symbol'):
            with self.subTest(carrier=carrier):
                pipeline = IntegrityModelPipeline(carrier, 'payload', inplace=True)
                outcome, _ = self.call(pipeline)
                self.assertEqual(outcome.reason, 'nonintervened_payload_preserved')
                self.assertEqual(outcome.phase, 'intervention-admission')
                self.assertFalse(outcome.exposed)
                self.assertEqual(pipeline.followup_extractions, 0)

    def test_changed_structure_cannot_be_integrity_evidence(self):
        for carrier in ('string', 'section', 'symbol'):
            with self.subTest(carrier=carrier):
                pipeline = IntegrityModelPipeline(carrier, 'structure')
                outcome, _ = self.call(pipeline)
                self.assertEqual(outcome.verdict, 'INADMISSIBLE')
                self.assertEqual(pipeline.followup_extractions, 0)

    def test_other_record_bytes_are_protected(self):
        for carrier in ('string', 'section'):
            with self.subTest(carrier=carrier):
                outcome, physical = self.call(IntegrityModelPipeline(carrier, 'outside'))
                self.assertEqual(physical['value'], 'checksum')
                self.assertEqual(outcome.reason, 'nonchecksum_material_preserved')

    def test_source_accepted_record_is_used_after_earlier_invalid_candidate(self):
        prefix = bytearray(make_record(b'earlier', KEY1)); prefix[-1] ^= 1
        for carrier in ('string', 'section'):
            with self.subTest(carrier=carrier):
                outcome, _ = self.call(IntegrityModelPipeline(carrier, prefix=bytes(prefix)))
                self.assertEqual(outcome.verdict, 'SATISFIED')

    def test_empty_payload_and_lengths_through_seventeen(self):
        # 54 representation/length cases, each with a genuine checksum change.
        with tempfile.TemporaryDirectory() as tmp, patch('subprocess.run', side_effect=model_utility):
            root = Path(tmp)
            for carrier in ('string', 'section', 'symbol'):
                for length in range(18):
                    with self.subTest(carrier=carrier, length=length):
                        payload = bytes(range(length))
                        source = root / 'source'; target = root / 'target'
                        if carrier == 'symbol':
                            names = symbol_names(payload, KEY1)
                            source.write_text('\n'.join(names), encoding='ascii')
                            target.write_text('\n'.join(name.rsplit('_', 1)[0] + '_' +
                                (int(name.rsplit('_', 1)[1], 16) ^ 1).to_bytes(8, 'big').hex()
                                for name in names), encoding='ascii')
                        else:
                            record = make_record(payload, KEY1)
                            source.write_bytes(record)
                            target.write_bytes(record[:-1] + bytes([record[-1] ^ 1]))
                        before = checksum_material(carrier, source, KEY1)
                        after = checksum_material(carrier, target, KEY1, source=before)
                        self.assertEqual(after.payload, payload)
                        self.assertTrue(all(intervention_facts(before, after).values()))

    def test_unchanged_checksum_fails_even_if_rejection_observer_is_wrong(self):
        with tempfile.TemporaryDirectory() as tmp, patch('subprocess.run', side_effect=model_utility), \
                patch('tosem02.admission.inspect_carrier', side_effect=[
                    {'kind': 'payload', 'value': PAYLOAD1.hex()},
                    {'kind': 'rejection', 'value': 'checksum'}]):
            pipeline = IntegrityModelPipeline('string', 'none')
            outcome = evaluate('MR10', pipeline, artifact_root() / 'hosts/H01-gcd.c', Path(tmp) / 'case')
        self.assertEqual(outcome.reason, 'checksum_material_changed')
        self.assertFalse(outcome.exposed)
        self.assertEqual(pipeline.followup_extractions, 0)

    def test_material_observer_failure_is_not_an_extractor_kill(self):
        with tempfile.TemporaryDirectory() as tmp, patch('tosem02.admission.checksum_material',
                side_effect=TimeoutError('owned observation timeout')):
            outcome = evaluate('MR10', IntegrityModelPipeline('string'),
                               artifact_root() / 'hosts/H01-gcd.c', Path(tmp) / 'case')
        self.assertEqual((outcome.verdict, outcome.reason), ('INADMISSIBLE', 'execution-error:TimeoutError'))
        self.assertFalse(outcome.exposed)


class IntegrityProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('owned_integrity_derivation',
                            artifact_root() / 'scripts/derive_admission_study.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def row(self, facts):
        return {'relation_id': 'MR10', 'verdict': 'SATISFIED',
                'admission_json': json.dumps({name: True for name in facts})}

    def test_protocol_follows_recorded_facts_not_current_code(self):
        old = self.row({'integrity_corruption_established'})
        new = self.row({'integrity_corruption_established'} | self.module.LOCALITY_FACTS)
        self.assertEqual(self.module.matrix_protocol([old]), 'evidence-gated-v1')
        self.assertEqual(self.module.matrix_protocol([new]), 'evidence-gated-v2-checksum-locality')
        self.assertEqual(self.module.matrix_protocol([]), 'unresolved-no-admitted-MR10')
        with self.assertRaises(ValueError):
            self.module.matrix_protocol([old, new])
        with self.assertRaises(ValueError):
            self.module.matrix_protocol([self.row({'checksum_material_changed'})])


if __name__ == '__main__':
    unittest.main()
