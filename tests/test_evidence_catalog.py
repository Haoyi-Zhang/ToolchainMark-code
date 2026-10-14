import copy,csv,json,unittest
from tosem02.evidence_catalog import load,validate
from tosem02.catalog import artifact_root
class EvidenceCatalogTests(unittest.TestCase):
 def test_declared_facts_match_clean_rows_with_explicit_retained_protocol(self):
  catalog={x['id']:x for x in load()}
  added_facts={'nonintervened_payload_preserved','checksum_material_changed','nonchecksum_material_preserved',
               'source_snapshot_matches_request','followup_snapshot_current','followup_unchanged_during_extraction'}
  with (artifact_root()/'results/admission-study/matrix.csv').open() as f:
   for r in csv.DictReader(f):
    if r['defect_id']=='CLEAN':
     facts=set(catalog[r['relation_id']]['required_admission_facts'])
     observations=set(catalog[r['relation_id']]['observation_keys'])
     if r['relation_id']=='MR10':
      self.assertTrue(added_facts<=facts)
      self.assertEqual(facts-added_facts,set(json.loads(r['admission_json'])))
      self.assertEqual(observations-{'integrity_intervention','integrity_snapshots'},set(json.loads(r['observations_json'])))
     else:
      self.assertEqual(facts,set(json.loads(r['admission_json'])))
      self.assertEqual(observations,set(json.loads(r['observations_json'])))
 def test_missing_observer_is_rejected(self):
  rows=copy.deepcopy(load());rows[0]['observer_boundary']=''
  with self.assertRaises(ValueError):validate({'relations':rows})
 def test_duplicate_identity_is_rejected(self):
  rows=copy.deepcopy(load());rows[1]['id']=rows[0]['id']
  with self.assertRaises(ValueError):validate({'relations':rows})
