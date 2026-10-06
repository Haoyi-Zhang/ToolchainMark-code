from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from tosem02.admission import evaluate
from tosem02.catalog import artifact_root
from tosem02.pipeline import Pipeline

class AdmissionTests(unittest.TestCase):
    def setUp(self): self.host=artifact_root()/'hosts/H01-gcd.c'
    def call(self,rel,defect='CLEAN',carrier='string'):
        with tempfile.TemporaryDirectory() as td:
            return evaluate(rel,Pipeline(carrier,defect),self.host,Path(td)/'case')
    def test_clean_all_relations_all_carriers(self):
        for c in ['string','symbol','section']:
            for i in range(1,15):
                with self.subTest(carrier=c,relation=i):
                    outcome = self.call(f'MR{i:02d}',carrier=c)
                    self.assertEqual(outcome.verdict,'SATISFIED',repr(outcome))
    def test_timeout_is_not_a_kill(self):
        with patch.object(Pipeline,'build',side_effect=TimeoutError()):
            o=self.call('MR01','M01')
        self.assertEqual(o.verdict,'INADMISSIBLE'); self.assertFalse(o.exposed)
    def test_missing_utility_is_not_a_kill(self):
        with patch.object(Pipeline,'build',side_effect=FileNotFoundError()):
            self.assertEqual(self.call('MR01','M01').verdict,'INADMISSIBLE')
    def test_failed_source_is_not_relocation_violation(self):
        self.assertEqual(self.call('MR08','M01').verdict,'INADMISSIBLE')
    def test_skipped_removal_is_not_extractor_failure(self):
        o=self.call('MR09','M15')
        self.assertEqual(o.verdict,'INADMISSIBLE'); self.assertEqual(o.reason,'carrier_removed')
    def test_invalid_corruption_is_not_integrity_bypass(self):
        o=self.call('MR10','M18')
        self.assertEqual(o.verdict,'INADMISSIBLE'); self.assertEqual(o.reason,'integrity_corruption_established')
    def test_direct_integrity_bypass_remains_exposed(self):
        self.assertEqual(self.call('MR10','M16').verdict,'INCONSISTENT')
    def test_configuration_substitution_is_not_compiler_diversity(self):
        self.assertEqual(self.call('MR06','M13').verdict,'INADMISSIBLE')
        self.assertEqual(self.call('MR11','M13').verdict,'INCONSISTENT')
    def test_domain_rejection_is_evidence_not_infrastructure(self):
        self.assertEqual(self.call('MR01','M01').verdict,'INCONSISTENT')
    def test_relocation_binding_violation_is_still_exposed(self):
        o=self.call('MR08','M07'); self.assertEqual(o.verdict,'INCONSISTENT')
        self.assertTrue(all(o.admission.values()))
    def test_unknown_relation_is_not_success(self):
        self.assertEqual(self.call('MR99').verdict,'INADMISSIBLE')
