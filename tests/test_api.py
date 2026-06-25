"""API endpoint tests (KAN-7) — requires fastapi + httpx (run via pytest)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
REPO = Path(__file__).resolve().parents[1]


def _incident(scenario: str) -> dict:
    return json.loads((REPO / "sample-data" / "incidents" / f"{scenario}.json").read_text())


def test_submit_then_fetch() -> None:
    """Acceptance: submit returns an id; fetching it returns the full diagnosis."""
    r = client.post("/incidents/diagnose", json=_incident("high_latency"))
    assert r.status_code == 201
    diagnosis_id = r.json()["diagnosis_id"]

    got = client.get(f"/diagnoses/{diagnosis_id}")
    assert got.status_code == 200
    body = got.json()
    assert body["summary"]
    assert body["hypotheses"][0]["evidence"]
    assert body["remediation"]["recommendations"]


def test_replay_endpoint() -> None:
    r = client.post("/incidents/replay/db_saturation")
    assert r.status_code == 201
    assert r.json()["status"] == "ok"


def test_replay_unknown_scenario_404() -> None:
    r = client.post("/incidents/replay/does_not_exist")
    assert r.status_code == 404


def test_scenarios_endpoint() -> None:
    r = client.get("/scenarios")
    assert r.status_code == 200
    names = {s["scenario"] for s in r.json()["scenarios"]}
    assert {"high_latency", "db_saturation"} <= names


def test_invalid_payload_returns_422() -> None:
    """Acceptance: invalid payloads return clear validation errors."""
    r = client.post("/incidents/diagnose", json={"id": "x"})  # missing required fields
    assert r.status_code == 422
    assert r.json()["detail"]  # structured validation errors


def test_unknown_diagnosis_404() -> None:
    assert client.get("/diagnoses/deadbeef").status_code == 404


def test_openapi_available() -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/incidents/diagnose" in paths and "/scenarios" in paths
