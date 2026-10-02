import copy,csv,json,unittest
from tosem02.evidence_catalog import load,validate
from tosem02.catalog import artifact_root
class EvidenceCatalogTests(unittest.TestCase):
 def test_declared_facts_match_clean_rows(self):
  catalog={x['id']:x for x in load()}
  with (artifact_root()/'results/admission-study/matrix.csv').open() as f:
   for r in csv.DictReader(f):
    if r['defect_id']=='CLEAN':
     self.assertEqual(set(catalog[r['relation_id']]['required_admission_facts']),set(json.loads(r['admission_json'])))
     self.assertEqual(set(catalog[r['relation_id']]['observation_keys']),set(json.loads(r['observations_json'])))
 def test_missing_observer_is_rejected(self):
  rows=copy.deepcopy(load());rows[0]['observer_boundary']=''
  with self.assertRaises(ValueError):validate({'relations':rows})
 def test_duplicate_identity_is_rejected(self):
  rows=copy.deepcopy(load());rows[1]['id']=rows[0]['id']
  with self.assertRaises(ValueError):validate({'relations':rows})
