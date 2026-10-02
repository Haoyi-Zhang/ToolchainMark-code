from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def artifact_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_relations() -> list[dict[str, Any]]:
    data = json.loads((artifact_root() / 'specs/mrspec.json').read_text())
    return data['relations']


def load_mutants() -> list[dict[str, Any]]:
    data = json.loads((artifact_root() / 'specs/mutants.json').read_text())
    return data['mutants']


def relation_map() -> dict[str, dict[str, Any]]:
    return {row['id']: row for row in load_relations()}


def mutant_map() -> dict[str, dict[str, Any]]:
    return {row['id']: row for row in load_mutants()}
