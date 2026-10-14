"""Benign byte fixtures for historical native-input binding; no native tools."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_native_records import verify_native_source_binding

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/current-native'


class NativeSourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='native-binding-test-')
        self.addCleanup(self.temporary.cleanup)
        base=Path(self.temporary.name)
        self.current=base/'current'
        self.data=base/'data'
        self.binding=json.loads((DATA/'native-inputs.json').read_text(encoding='utf-8'))
        self.provenance=json.loads((DATA/'provenance.json').read_text(encoding='utf-8'))
        self.recovery=json.loads((DATA/'historical-source-recovery.json').read_text(encoding='utf-8'))
        for entry in self.binding['native_paths']:
            self.copy(ROOT/entry['path'],self.current/entry['path'])
        for entry in self.provenance['source_snapshot']['files']:
            path=entry['path']
            self.copy(DATA/'source-snapshot'/path,self.data/'source-snapshot'/path)
        for entry in self.recovery['files']:
            path=entry['path']
            self.copy(DATA/'historical-source-recovery'/path,self.data/'historical-source-recovery'/path)
        self.copy(DATA/'provenance.json',self.data/'provenance.json')
        self.copy(DATA/'historical-source-recovery.json',self.data/'historical-source-recovery.json')

    @staticmethod
    def copy(source,target):
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)

    def verify(self,**kwargs):
        return verify_native_source_binding(self.binding,self.current,self.data,**kwargs)

    def test_historical_bytes_are_verified_without_claiming_current_execution(self):
        report=self.verify()
        self.assertEqual(report['historical_native_input_files'],71)
        self.assertEqual(report['original_snapshot_files_used'],6)
        self.assertEqual(report['later_recovered_files_used'],2)
        self.assertEqual(report['current_identical_files'],63)
        self.assertIn('scripts/derive_admission_study.py',report['current_diverged_paths'])
        self.assertEqual(report['current_only_paths'],[])

    def test_corrupted_recovered_byte_is_rejected(self):
        path=self.data/'historical-source-recovery/tests/test_evidence_catalog.py'
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'Later recovery bytes differ'):
            self.verify()

    def test_corrupted_historical_package_verifier_is_rejected(self):
        path=self.data/'historical-source-recovery/scripts/verify_package.py'
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'Later recovery bytes differ'):
            self.verify()

    def test_missing_original_snapshot_is_rejected(self):
        (self.data/'source-snapshot/scripts/derive_admission_study.py').unlink()
        with self.assertRaisesRegex(ValueError,'Original snapshot bytes differ'):
            self.verify()

    def test_changed_manifest_digest_is_not_rebased(self):
        changed=copy.deepcopy(self.binding)
        next(e for e in changed['native_paths'] if e['path']=='scripts/derive_admission_study.py')['git_blob_sha']='0'*40
        with self.assertRaisesRegex(ValueError,'declaration differs from historical manifest'):
            verify_native_source_binding(changed,self.current,self.data)

    def test_current_only_file_is_disclosed_not_added_to_old_campaign(self):
        extra=self.current/'tests/new_current_test.py'
        extra.write_text('pass\n',encoding='utf-8')
        self.assertEqual(self.verify()['current_only_paths'],['tests/new_current_test.py'])

    def test_explicit_preserved_root_requires_all_historical_bytes(self):
        with self.assertRaisesRegex(ValueError,'Historical native input changed'):
            self.verify(source_root=self.current)
        for entry in self.binding['native_paths']:
            path=entry['path']; current=self.current/path
            if path in {e['path'] for e in self.provenance['source_snapshot']['files']}:
                source=self.data/'source-snapshot'/path
            elif path in {e['path'] for e in self.recovery['files']}:
                source=self.data/'historical-source-recovery'/path
            else:
                continue
            self.copy(source,current)
        self.assertEqual(self.verify(source_root=self.current)['source_binding'],'explicit-preserved-v2-root')


if __name__=='__main__':
    unittest.main()
