"""Owned symbol-format and relation-boundary regressions; no native tools."""
import subprocess
import contextlib
import importlib.util
import io
import itertools
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tosem02.admission import evaluate
from tosem02.catalog import artifact_root
from tosem02.model import ExtractionError
from tosem02.record import checksum, key_tag, parse_symbols, symbol_names
from tosem02.relations import KEY1, KEY2, PAYLOAD1
from test_repair_models import ByteBuildPipeline


class SymbolFormatTests(unittest.TestCase):
    def parse(self, names, key=KEY1, **kwargs):
        listing = "\n".join("00000000 R " + name for name in names)
        with patch("tosem02.record.subprocess.run", return_value=
                   subprocess.CompletedProcess(["owned-symbol-observation"], 0, listing, "")):
            return parse_symbols(Path("owned-synthetic-symbol-table"), key, **kwargs)

    def altered(self, payload, *, length=None, chunks=None):
        names = symbol_names(payload, KEY1)
        result = []
        for index, name in enumerate(names):
            fields = name.split("_")
            if length is not None:
                fields[2] = f"{length:04x}"
            if chunks is not None:
                fields[5] = chunks[index].hex()
            result.append("_".join(fields))
        return result

    def malformed(self, names):
        for bypass in (False, True):
            with self.subTest(checksum_bypass=bypass):
                with self.assertRaises(ExtractionError) as caught:
                    self.parse(names, checksum_bypass=bypass)
                self.assertEqual(caught.exception.kind, "malformed")

    def test_canonical_lengths_zero_through_seventeen(self):
        for length in range(18):
            payload = bytes(range(length))
            with self.subTest(length=length):
                self.assertEqual(self.parse(symbol_names(payload, KEY1)), payload)

    def test_declared_length_cannot_exceed_available_chunks(self):
        self.malformed(self.altered(b"abcd", length=5))

    def test_short_interior_chunk_is_not_structurally_complete(self):
        self.malformed(self.altered(b"abcde", chunks=[b"abc", b"de"]))

    def test_extra_final_bytes_are_not_silently_discarded(self):
        self.malformed(self.altered(b"a", chunks=[b"ab"]))

    def test_empty_payload_requires_only_the_canonical_placeholder(self):
        self.malformed(self.altered(b"", chunks=[b"\x01"]))

    def test_generator_enforces_its_sixteen_bit_length_field(self):
        with self.assertRaises(ValueError):
            symbol_names(b"a" * 65536, KEY1)
        self.assertEqual(len(symbol_names(b"a" * 65535, KEY1)), 16384)

    def test_key_and_checksum_rejections_stay_distinct(self):
        with self.assertRaises(ExtractionError) as caught:
            self.parse(symbol_names(PAYLOAD1, KEY1), key=KEY2)
        self.assertEqual(caught.exception.kind, "wrong-key")
        names = [name.rsplit("_", 1)[0] + "_" + (bytes([checksum(PAYLOAD1)[0] ^ 1]) +
                 checksum(PAYLOAD1)[1:]).hex() for name in symbol_names(PAYLOAD1, KEY1)]
        with self.assertRaises(ExtractionError) as caught:
            self.parse(names)
        self.assertEqual(caught.exception.kind, "checksum")
        self.assertEqual(self.parse(names, checksum_bypass=True), PAYLOAD1)

    def test_finite_chunk_shape_oracle(self):
        comparisons = 0
        for length in range(10):
            for total in range(1, 4):
                for widths in itertools.product(range(1, 5), repeat=total):
                    payload = b'a' * length
                    names = [f'wmrec_{key_tag(KEY1).hex()}_{length:04x}_{i:04x}_{total:04x}_'
                             f'{(b"a" * width).hex()}_{checksum(payload).hex()}'
                             for i, width in enumerate(widths)]
                    # Independently specified structure: complete four-byte
                    # nonfinal chunks, exact final remainder, and no padding.
                    expected = length > 0 and sum(widths) == length and all(w == 4 for w in widths[:-1])
                    with self.subTest(length=length, widths=widths):
                        if expected:
                            self.assertEqual(self.parse(names), payload)
                        else:
                            with self.assertRaises(ExtractionError) as caught:
                                self.parse(names)
                            self.assertEqual(caught.exception.kind, 'malformed')
                    comparisons += 1
        self.assertEqual(comparisons, 840)

    def test_odd_hex_chunk_is_domain_malformed_not_tool_failure(self):
        fields = symbol_names(b'a', KEY1)[0].split('_')
        fields[5] = 'aaa'
        self.malformed(['_'.join(fields)])


class RelationBoundaryTests(unittest.TestCase):
    def test_relocation_requires_host_equality_not_just_payload(self):
        host = artifact_root() / "hosts/H01-gcd.c"
        with tempfile.TemporaryDirectory() as tmp, patch("tosem02.admission.run_host",
                side_effect=["1"] * 6 + ["2"] * 6):
            outcome = evaluate("MR08", ByteBuildPipeline(), host, Path(tmp) / "case")
        self.assertEqual(outcome.verdict, "INCONSISTENT")
        self.assertTrue(all(outcome.admission.values()))
        self.assertFalse(outcome.observations["host_outputs_agree"])
        self.assertEqual(outcome.observations["followup"]["value"], PAYLOAD1.hex())


class CampaignGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('owned_admission_derivation',
                        artifact_root() / 'scripts/derive_admission_study.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def summary(self):
        return dict(rows=18900, clean_rows=756, unit_count=1296, design_units=72,
                    clean={'SATISFIED': 756}, rerun={'verdict': 'PASS'})

    def test_success_and_failed_gates_propagate_exit_status(self):
        variants = [('complete', {}, 0), ('rerun-difference', {'rerun': {'verdict': 'FAIL'}}, 1),
                    ('clean-inconsistent', {'clean': {'SATISFIED': 755, 'INCONSISTENT': 1}}, 1),
                    ('clean-inadmissible', {'clean': {'SATISFIED': 755, 'INADMISSIBLE': 1}}, 1),
                    ('incomplete', {'rows': 18899}, 1)]
        for label, updates, expected in variants:
            data = self.summary(); data.update(updates)
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(self.module, 'derive', return_value=data), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = self.module.main(['--matrix', 'owned-matrix.csv', '--mutants', 'owned-mutants.json',
                                         '--out', tmp, '--rerun', 'owned-rerun.csv'])
                self.assertEqual(code, expected)
                self.assertTrue((Path(tmp) / 'scientific_checks.json').is_file())

    def test_unknown_fault_units_need_not_all_be_exposed(self):
        data = self.summary(); data.update(units_exposed=0, design_exposed=0)
        self.assertTrue(all(self.module.scientific_checks(data).values()))


if __name__ == "__main__":
    unittest.main()
