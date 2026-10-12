"""Benign CLI planning and pure observer classification; no campaigns/tools."""
import contextlib
import gzip
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tosem02 import cli

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('utility_classification', ROOT/'scripts/run_adverse_transformations.py')
utility = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utility)  # Definitions only; main is not invoked.


class UtilityClassificationTests(unittest.TestCase):
    def test_only_absent_satisfies_expected_rejection(self):
        for kind in ('absent','wrong-key','checksum','malformed','version','tool','unknown'):
            with self.subTest(kind=kind):
                observed, passed = utility.classify_observation('reject',0,error_kind=kind)
                self.assertEqual(passed,kind=='absent')
                if kind in {'tool','unknown'}:
                    self.assertEqual(observed,'infrastructure_failure')

    def test_transform_failure_dominates_even_an_absence_observation(self):
        for code in (1,None):
            with self.subTest(code=code):
                self.assertEqual(utility.classify_observation('reject',code,error_kind='absent'),
                                 ('infrastructure_failure',False))

    def test_unknown_observation_exception_cannot_pass(self):
        self.assertEqual(utility.classify_observation('preserve',0,payload_equal=True,
                         host_outputs_equal=True,exception_class='OSError'),
                         ('infrastructure_failure',False))

    def test_preservation_needs_payload_and_host_observations(self):
        for payload,host in ((False,False),(False,True),(True,False),(True,True)):
            with self.subTest(payload=payload,host=host):
                _, passed = utility.classify_observation('preserve',0,
                    payload_equal=payload,host_outputs_equal=host)
                self.assertEqual(passed,payload and host)

    def test_domain_absence_does_not_satisfy_preservation(self):
        self.assertEqual(utility.classify_observation('preserve',0,error_kind='absent'),('reject',False))

    def test_payload_acceptance_does_not_satisfy_rejection(self):
        self.assertEqual(utility.classify_observation('reject',0,payload_equal=True,
                         host_outputs_equal=True),('preserve',False))

    def test_unknown_expected_outcome_is_rejected(self):
        with self.assertRaises(ValueError):
            utility.classify_observation('infrastructure_failure',0)


class CurrentDerivationTests(unittest.TestCase):
    def test_help_does_not_claim_draft_authorship_verification(self):
        with patch.object(sys,'argv',['cli','--help']), patch('tosem02.cli.recheck') as recheck:
            with contextlib.redirect_stdout(io.StringIO()) as stdout, self.assertRaises(SystemExit) as raised:
                cli.main()
            self.assertEqual(raised.exception.code,0)
            self.assertIn('legacy retained-evidence checks',stdout.getvalue())
            self.assertNotIn('draft authorship',stdout.getvalue())
            recheck.assert_not_called()

    def fixture(self, base):
        root = base/'supplied-project/artifact'
        current = root/'results/current-native'
        current.mkdir(parents=True)
        for name in ('first','second'):
            (current/(name+'.csv.gz')).write_bytes(gzip.compress((name+'-owned-data\n').encode(),mtime=0))
        paper = root.parent/'paper/generated'
        paper.mkdir(parents=True)
        (paper/'admission-results.tex').write_bytes(b'current-paper-sentinel')
        legacy = root/'results/admission-study'
        legacy.mkdir()
        (legacy/'matrix.csv').write_bytes(b'historical-sentinel')
        return root

    def test_cli_requires_new_output_argument(self):
        with patch.object(sys,'argv',['cli','derive']), patch('tosem02.cli.subprocess.run') as run:
            with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as raised:
                cli.main()
            self.assertEqual(raised.exception.code,2)
            self.assertIn('--out',stderr.getvalue())
            run.assert_not_called()

    def test_current_gzip_inputs_and_single_data_only_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self.fixture(base)
            output = base/'new-derived'
            captured = []
            def stub(command, **kwargs):
                captured.append(command)
                self.assertTrue(kwargs['check'])
                self.assertEqual(Path(command[command.index('--matrix')+1]).read_bytes(),b'first-owned-data\n')
                self.assertEqual(Path(command[command.index('--rerun')+1]).read_bytes(),b'second-owned-data\n')
                self.assertEqual(Path(command[command.index('--out')+1]),output.resolve())
                return subprocess.CompletedProcess(command,0)
            with patch('tosem02.cli.artifact_root',return_value=root), \
                 patch.object(sys,'argv',['cli','derive','--out',str(output)]), \
                 patch('tosem02.cli.subprocess.run',side_effect=stub):
                cli.main()
            self.assertEqual(len(captured),1)
            self.assertTrue(captured[0][1].endswith('derive_admission_study.py'))
            self.assertNotIn('generate_admission_tables.py',' '.join(captured[0]))
            self.assertEqual((root/'results/admission-study/matrix.csv').read_bytes(),b'historical-sentinel')
            self.assertEqual((root.parent/'paper/generated/admission-results.tex').read_bytes(),b'current-paper-sentinel')
            self.assertTrue(output.is_dir())

    def test_existing_file_and_directory_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self.fixture(base)
            existing_file = base/'existing-file'
            existing_file.write_bytes(b'existing-sentinel')
            existing_directory = base/'existing-directory'
            existing_directory.mkdir()
            for output in (existing_file,existing_directory):
                with self.subTest(output=output.name), patch('tosem02.cli.subprocess.run') as run:
                    with self.assertRaises(SystemExit):
                        cli.derive_current_native(root,output)
                    run.assert_not_called()
            self.assertEqual(existing_file.read_bytes(),b'existing-sentinel')

    def test_output_inside_supplied_project_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(Path(temporary))
            output = root/'results/new-output'
            with patch('tosem02.cli.subprocess.run') as run, self.assertRaises(SystemExit):
                cli.derive_current_native(root,output)
            run.assert_not_called()
            self.assertFalse(output.exists())

    def test_data_derivation_failure_is_propagated(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self.fixture(base)
            output = base/'new-output'
            with patch('tosem02.cli.subprocess.run',side_effect=subprocess.CalledProcessError(1,['owned-stub'])):
                with self.assertRaises(subprocess.CalledProcessError):
                    cli.derive_current_native(root,output)
            self.assertTrue(output.is_dir())


if __name__=='__main__':
    unittest.main()
