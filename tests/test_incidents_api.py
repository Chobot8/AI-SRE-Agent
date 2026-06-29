"""API tests for durable incident investigations (KAN-17).

Covers the success, not-found, validation-error, and failed-investigation paths.
Tests that need PostgreSQL are skipped when no database is reachable (keeping CI
green without one); the filter-validation tests run regardless, since FastAPI
validates query params before the handler touches the database.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.analysis.models import IncidentDiagnosis
from backend.main import app

client = TestClient(app)
REPO = Path(__file__).resolve().parents[1]


def _incident(scenario: str) -> dict:
    return json.loads(
        (REPO / "sample-data" / "incidents" / f"{scenario}.json").read_text()
    )


def _db_ready() -> bool:
    try:
        from backend.db import session as db_session

        db_session.reset_engine()
        db_session.check_connection()
        return True
    except Exception:
        return False


DB_READY = _db_ready()
requires_db = pytest.mark.skipif(not DB_READY, reason="No reachable PostgreSQL")


# --- Validation errors for bad filters (no database required) ----------------


def test_list_rejects_unknown_severity() -> None:
    assert client.get("/incidents", params={"severity": "nope"}).status_code == 422


def test_list_rejects_unknown_scenario() -> None:
    assert client.get("/incidents", params={"scenario": "nope"}).status_code == 422


def test_list_rejects_unknown_status() -> None:
    assert client.get("/incidents", params={"status": "weird"}).status_code == 422


def test_list_rejects_out_of_range_limit() -> None:
    assert client.get("/incidents", params={"limit": 0}).status_code == 422


# --- Durable contract for POST /incidents (no real DB required) ---------------


def test_submit_requires_persistence(monkeypatch) -> None:
    """POST /incidents returns 503 (not a fake 201) when no store is configured."""
    monkeypatch.setattr(
        "backend.api.persistence.persistence_enabled", lambda: False
    )
    r = client.post("/incidents", json=_incident("high_latency"))
    assert r.status_code == 503


def test_submit_surfaces_persistence_failure(monkeypatch) -> None:
    """A storage failure surfaces as 503 instead of a 201 with no stored result."""
    monkeypatch.setattr("backend.api.persistence.persistence_enabled", lambda: True)
    monkeypatch.setattr("backend.api.service.persistence_enabled", lambda: True)

    def _boom(payload):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("backend.api.service.persist_investigation", _boom)
    r = client.post("/incidents", json=_incident("high_latency"))
    assert r.status_code == 503


# --- Success path -------------------------------------------------------------


@requires_db
def test_submit_persists_and_can_be_fetched() -> None:
    """Acceptance: a submitted incident is stored and survives a fresh fetch."""
    r = client.post("/incidents", json=_incident("high_latency"))
    assert r.status_code == 201
    investigation_id = r.json()["investigation_id"]
    assert investigation_id

    got = client.get(f"/incidents/{investigation_id}")
    assert got.status_code == 200
    body = got.json()
    assert body["incident"]["scenario"] == "high_latency"
    assert body["incident"]["service"] == "checkout-api"
    assert body["diagnosis"]["summary"]
    assert body["hypotheses"][0]["cause"]
    assert body["recommendations"]
    assert body["agent_runs"][0]["status"] == "succeeded"
    # Enough to reproduce the visible diagnosis output.
    assert isinstance(body["evidence"], list)
    assert isinstance(body["retrieved_chunks"], list)


@requires_db
def test_live_diagnose_endpoint_does_not_persist() -> None:
    """The legacy live endpoint must not write to durable history."""
    r = client.post("/incidents/diagnose", json=_incident("high_latency"))
    assert r.status_code == 201
    assert r.json().get("investigation_id") is None


@requires_db
def test_replay_is_persisted_as_replay() -> None:
    r = client.post("/incidents/replay/db_saturation")
    assert r.status_code == 201
    investigation_id = r.json()["investigation_id"]
    assert investigation_id
    body = client.get(f"/incidents/{investigation_id}").json()
    assert body["incident"]["is_replay"] is True
    assert body["incident"]["intake_source"] == "replay"


@requires_db
def test_list_with_filters() -> None:
    client.post("/incidents", json=_incident("db_saturation"))

    r = client.get("/incidents", params={"scenario": "db_saturation"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert all(item["scenario"] == "db_saturation" for item in data["items"])

    # Status filter on the agent run lifecycle.
    succeeded = client.get("/incidents", params={"status": "succeeded"})
    assert succeeded.status_code == 200
    assert all(item["run_status"] == "succeeded" for item in succeeded.json()["items"])


@requires_db
def test_agent_run_metadata() -> None:
    r = client.post("/incidents", json=_incident("high_latency"))
    investigation_id = r.json()["investigation_id"]
    full = client.get(f"/incidents/{investigation_id}").json()
    run_id = full["agent_runs"][0]["id"]

    got = client.get(f"/agent-runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["status"] in ("succeeded", "failed")
    assert got.json()["incident_id"] == investigation_id


# --- Not found / validation on ids -------------------------------------------


@requires_db
def test_unknown_incident_returns_404() -> None:
    assert client.get(f"/incidents/{uuid.uuid4()}").status_code == 404


@requires_db
def test_unknown_agent_run_returns_404() -> None:
    assert client.get(f"/agent-runs/{uuid.uuid4()}").status_code == 404


@requires_db
def test_malformed_incident_id_returns_422() -> None:
    assert client.get("/incidents/not-a-uuid").status_code == 422


# --- Failed investigation path -----------------------------------------------


@requires_db
def test_failed_investigation_is_persisted(monkeypatch) -> None:
    """A failed diagnosis is stored with a failed run and an error diagnosis."""

    def _force_error(incident, llm=None):
        return IncidentDiagnosis(
            incident_id=str(incident.get("id", "x")),
            service=str(incident.get("service", "x")),
            scenario=str(incident.get("scenario", "x")),
            status="error",
            error="forced failure for test",
        )

    monkeypatch.setattr("backend.api.service.diagnose_incident", _force_error)

    r = client.post("/incidents", json=_incident("high_latency"))
    assert r.status_code == 201
    assert r.json()["status"] == "error"
    investigation_id = r.json()["investigation_id"]
    assert investigation_id

    body = client.get(f"/incidents/{investigation_id}").json()
    assert body["diagnosis"]["status"] == "error"
    assert body["diagnosis"]["error"] == "forced failure for test"
    assert body["agent_runs"][0]["status"] == "failed"
    assert body["hypotheses"] == []
