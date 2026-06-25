"""Tests for the diagnosis service layer (KAN-7) — no web stack required."""

import json
from pathlib import Path

from backend.api.service import DiagnosisService

REPO = Path(__file__).resolve().parents[1]


def _incident(scenario: str) -> dict:
    return json.loads((REPO / "sample-data" / "incidents" / f"{scenario}.json").read_text())


def test_submit_returns_diagnosis_id() -> None:
    """Acceptance: submitting an incident returns a diagnosis id."""
    svc = DiagnosisService()
    receipt = svc.submit(_incident("high_latency"))
    assert receipt["diagnosis_id"]
    assert receipt["status"] == "ok"


def test_get_returns_full_result() -> None:
    """Acceptance: the result has summary, hypotheses, evidence, recommendations."""
    svc = DiagnosisService()
    diagnosis_id = svc.submit(_incident("db_saturation"))["diagnosis_id"]
    result = svc.get(diagnosis_id)
    assert result is not None
    assert result["summary"]
    assert result["hypotheses"] and result["hypotheses"][0]["evidence"]
    assert result["remediation"]["recommendations"]
    # remediation never auto-executes
    assert result["remediation"]["auto_execution"] is False


def test_replay_known_and_unknown() -> None:
    svc = DiagnosisService()
    assert svc.replay("error_rate_spike") is not None
    assert svc.replay("nope_not_a_scenario") is None


def test_scenarios_listed() -> None:
    svc = DiagnosisService()
    scenarios = svc.available_scenarios()
    assert {"high_latency", "db_saturation"} <= set(scenarios)


def test_unknown_diagnosis_id() -> None:
    assert DiagnosisService().get("deadbeef") is None
