"""Validate the declared evidence interface without treating it as a proof."""
from pathlib import Path
import json
from .catalog import artifact_root
REQUIRED={'id','name','polarity','stages','applicability','required_admission_facts','observation_keys','observer_boundary','predicate','exposure_rule'}
def validate(document: dict) -> list[dict]:
    relations=document.get('relations')
    if not isinstance(relations,list) or len(relations)!=14:raise ValueError('expected fourteen relation declarations')
    ids=[r.get('id') for r in relations]
    if len(set(ids))!=14 or set(ids)!={f'MR{i:02d}' for i in range(1,15)}:raise ValueError('relation identities are not unique and complete')
    for row in relations:
        if not REQUIRED<=row.keys():raise ValueError('missing evidence declaration field')
        if row['polarity'] not in {'preserve','reject','separate','trace'}:raise ValueError('unknown polarity')
        if not row['stages'] or not row['observer_boundary'] or not row['predicate']:raise ValueError('empty semantic declaration')
        if not {'subject_exists','isolated_workspace'}<=set(row['required_admission_facts']):raise ValueError('missing base admission facts')
    return relations

def load()->list[dict]:
    return validate(json.loads((artifact_root()/'specs/evidence_relations.json').read_text()))
