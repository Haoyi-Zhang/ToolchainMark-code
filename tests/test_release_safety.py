import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from tosem02.catalog import artifact_root
class ReleaseSafetyTests(unittest.TestCase):
 def test_new_run_requires_explicit_output(self):
  p=subprocess.run([sys.executable,'-m','tosem02.cli','run'],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('--out',p.stderr)
 def test_existing_matrix_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'matrix.csv';out.write_text('sentinel')
   p=subprocess.run([sys.executable,'-m','tosem02.cli','run','--out',str(out),'--clean-only','--design-only'],capture_output=True,text=True)
   self.assertNotEqual(p.returncode,0);self.assertEqual(out.read_text(),'sentinel')
 def test_citation_presence_is_not_external_verification(self):
  path=artifact_root()/'scripts/audit_references.py';spec=importlib.util.spec_from_file_location('reference_checker',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  s=module.structural_audit(r'claim \cite{a}.',{'a':{}},[{'citation_key':'a','doi':'10.0/a'}],[{'citation_key':'a','record_located_this_revision':False}])
  self.assertEqual(s['fresh_record_checks'],0);self.assertFalse(s['full_text_review_claimed'])

 def test_design_alias_requires_output_without_running(self):
  p=subprocess.run(['bash',str(artifact_root()/'scripts/run_base.sh')],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('NEW matrix file',p.stderr)
 def test_complete_alias_requires_output_without_running(self):
  p=subprocess.run(['bash',str(artifact_root()/'scripts/run_complete.sh')],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('NEW output directory',p.stderr)
