"""Schema checks for the bundled sample incidents (KAN-11).

Validates every `sample-data/incidents/*.json` against the project's
`incident.schema.json`. These run as part of the test suite so CI's "schema
checks" gate fails fast if sample data drifts from the contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "sample-data" / "schema" / "incident.schema.json"
INCIDENTS_DIR = REPO_ROOT / "sample-data" / "incidents"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_itself_is_valid() -> None:
    schema = _load_json(SCHEMA_PATH)
    # Raises SchemaError if the schema document is malformed.
    Draft7Validator.check_schema(schema)


def _incident_files() -> list[Path]:
    return sorted(INCIDENTS_DIR.glob("*.json"))


def test_incident_samples_exist() -> None:
    assert _incident_files(), "no sample incidents found to validate"


@pytest.mark.parametrize("incident_path", _incident_files(), ids=lambda p: p.name)
def test_incident_matches_schema(incident_path: Path) -> None:
    schema = _load_json(SCHEMA_PATH)
    validator = Draft7Validator(schema)
    incident = _load_json(incident_path)
    errors = [e.message for e in validator.iter_errors(incident)]
    assert not errors, f"{incident_path.name} failed schema: {errors}"
