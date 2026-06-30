"""Tests for the richer incident scenario packs and their loader (KAN-18).

Validates the acceptance criteria: at least five packs exist, at least two are
intentionally ambiguous or multi-cause, every pack has machine-readable expected
outputs, and the loader validates file presence + schema. Also checks that each
pack assembles into a schema-valid NormalizedIncident so it can be replayed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from backend.scenarios import loader
from backend.telemetry.schema import NormalizedIncident

REPO_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_SCHEMA = REPO_ROOT / "sample-data" / "schema" / "incident.schema.json"
RUNBOOKS_DIR = REPO_ROOT / "knowledge" / "runbooks"

PACKS = loader.list_packs()


def test_at_least_five_packs() -> None:
    assert len(PACKS) >= 5, f"expected >=5 scenario packs, found {len(PACKS)}: {PACKS}"


def test_at_least_two_ambiguous_or_multi_cause() -> None:
    flagged = []
    for slug in PACKS:
        expected = loader.load_pack(slug)["expected"]
        if expected.get("is_ambiguous") or expected.get("is_multi_cause"):
            flagged.append(slug)
    assert len(flagged) >= 2, f"expected >=2 ambiguous/multi-cause packs, got {flagged}"


@pytest.mark.parametrize("slug", PACKS)
def test_required_files_present(slug: str) -> None:
    d = loader.pack_dir(slug)
    missing = [f for f in loader.REQUIRED_FILES if not (d / f).exists()]
    assert not missing, f"{slug} missing files: {missing}"


@pytest.mark.parametrize("slug", PACKS)
def test_pack_validates(slug: str) -> None:
    errors = loader.validate_pack(slug)
    assert not errors, f"{slug} failed validation: {errors}"


@pytest.mark.parametrize("slug", PACKS)
def test_expected_outputs_machine_readable(slug: str) -> None:
    expected = loader.load_pack(slug)["expected"]
    assert expected.get("root_cause", {}).get("summary"), slug
    assert expected.get("expected_evidence"), slug
    assert expected.get("expected_remediation", {}).get("direction"), slug
    assert expected.get("agent_scenario"), slug


@pytest.mark.parametrize("slug", PACKS)
def test_assembles_into_schema_valid_incident(slug: str) -> None:
    schema = json.loads(INCIDENT_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    incident = loader.to_normalized_incident(loader.load_pack(slug))
    errors = [e.message for e in validator.iter_errors(incident)]
    assert not errors, f"{slug} -> incident schema errors: {errors}"
    # And it parses with the pydantic contract the agent consumes.
    NormalizedIncident.model_validate(incident)


@pytest.mark.parametrize("slug", PACKS)
def test_runbook_references_exist(slug: str) -> None:
    expected = loader.load_pack(slug)["expected"]
    for ref in expected.get("runbook_references", []):
        assert (RUNBOOKS_DIR / ref).exists(), f"{slug}: missing runbook {ref}"


def test_validate_all_is_clean() -> None:
    results = loader.validate_all()
    bad = {slug: errs for slug, errs in results.items() if errs}
    assert not bad, f"packs with validation errors: {bad}"


def test_a_false_positive_pack_exists() -> None:
    """The dataset includes the 'recovers before action' case for the demo."""
    assert any(
        loader.load_pack(slug)["expected"].get("is_false_positive") for slug in PACKS
    ), "expected at least one false-positive scenario pack"


# --- robustness fixes (KAN-18 review) ----------------------------------------


def _write_valid_pack(d: Path, slug: str, incident_id: str = "SCN-T") -> None:
    """Write a complete, valid pack into directory ``d``."""
    d.mkdir(parents=True, exist_ok=True)
    alert = {
        "id": incident_id,
        "service": "svc",
        "environment": "production",
        "source": "prometheus",
        "severity": "warning",
        "summary": "test",
        "started_at": "2026-06-25T00:00:00Z",
    }
    (d / "alert.json").write_text(json.dumps(alert), encoding="utf-8")
    metric = {
        "name": "m",
        "unit": "ms",
        "points": [{"t": "2026-06-25T00:00:00Z", "value": 1}],
    }
    (d / "metrics.json").write_text(json.dumps({"metrics": [metric]}), encoding="utf-8")
    log_entry = {
        "t": "2026-06-25T00:00:00Z",
        "level": "INFO",
        "service": "svc",
        "message": "x",
    }
    (d / "logs.jsonl").write_text(json.dumps(log_entry) + "\n", encoding="utf-8")
    health = {"service": "svc", "status": "healthy", "dependencies": []}
    (d / "service_health.json").write_text(json.dumps(health), encoding="utf-8")
    (d / "runbook.md").write_text("# runbook\n", encoding="utf-8")
    # YAML is a superset of JSON, so JSON content is valid expected.yaml.
    expected = {
        "id": incident_id,
        "slug": slug,
        "title": "t",
        "agent_scenario": "high_latency",
        "root_cause": {"summary": "s"},
        "expected_evidence": ["e"],
        "expected_remediation": {"direction": "investigate"},
    }
    (d / "expected.yaml").write_text(json.dumps(expected), encoding="utf-8")


def test_validate_pack_reports_malformed_json_without_crashing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(loader, "SCENARIOS_DIR", tmp_path)
    d = tmp_path / "broken-json"
    _write_valid_pack(d, "broken-json")
    (d / "alert.json").write_text("{ this is not valid json", encoding="utf-8")

    errors = loader.validate_pack("broken-json")  # must not raise
    assert any("alert.json" in e and "not valid JSON" in e for e in errors), errors


def test_validate_pack_reports_malformed_yaml_without_crashing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(loader, "SCENARIOS_DIR", tmp_path)
    d = tmp_path / "broken-yaml"
    _write_valid_pack(d, "broken-yaml")
    (d / "expected.yaml").write_text("key: [unclosed\n  - a\n :::", encoding="utf-8")

    errors = loader.validate_pack("broken-yaml")  # must not raise
    assert any("expected.yaml" in e for e in errors), errors


def test_validation_discovers_incomplete_pack_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(loader, "SCENARIOS_DIR", tmp_path)
    # A half-added pack with no expected.yaml must still be discovered + flagged.
    d = tmp_path / "half-added"
    d.mkdir()
    (d / "alert.json").write_text("{}", encoding="utf-8")

    assert "half-added" in loader.candidate_packs()
    results = loader.validate_all()
    assert "half-added" in results
    assert any("missing required file expected.yaml" in e for e in results["half-added"])


@pytest.mark.parametrize("slug", PACKS)
def test_service_health_is_folded_into_incident(slug: str) -> None:
    pack = loader.load_pack(slug)
    incident = loader.to_normalized_incident(pack)
    # Every dependency in service_health appears in the incident logs.
    messages = " ".join(log["message"] for log in incident["logs"])
    for dep in pack["service_health"].get("dependencies", []):
        assert dep["name"] in messages, f"{slug}: dependency {dep['name']} dropped"
    assert len(incident["logs"]) >= len(pack["logs"])
