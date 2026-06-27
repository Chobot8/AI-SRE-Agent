"""Tests for agent observability: correlation IDs, logs, metrics (KAN-12)."""

from __future__ import annotations

import io
import json
import logging

import pytest

from backend.api.service import DiagnosisService
from backend.observability import METRICS, get_logger, log_event, redact
from backend.observability.logging import JsonFormatter, configure_logging


def _sample(scenario: str = "high_latency") -> dict:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = root / "sample-data" / "incidents" / f"{scenario}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _capture_agent_logs() -> io.StringIO:
    configure_logging("INFO", "json")
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    agent = logging.getLogger("agent")
    for existing in list(agent.handlers):
        agent.removeHandler(existing)
    agent.addHandler(handler)
    return buf


def test_each_diagnosis_has_a_correlation_id() -> None:
    service = DiagnosisService()
    receipt = service.submit(_sample())
    assert len(receipt["correlation_id"]) == 32

    stored = service.get(receipt["diagnosis_id"])
    assert stored is not None
    assert stored["correlation_id"] == receipt["correlation_id"]


def test_distinct_diagnoses_get_distinct_correlation_ids() -> None:
    service = DiagnosisService()
    first = service.submit(_sample())
    second = service.submit(_sample("db_saturation"))
    assert first["correlation_id"] != second["correlation_id"]


def test_metrics_increment_on_diagnosis() -> None:
    service = DiagnosisService()
    before = METRICS.diagnoses_total.value(status="ok", engine="deterministic")
    retrievals_before = METRICS.retrievals_total.value()

    service.submit(_sample())

    assert METRICS.diagnoses_total.value(status="ok", engine="deterministic") == before + 1
    assert METRICS.retrievals_total.value() == retrievals_before + 1
    assert METRICS.retrieved_chunks_total.value() >= 1


def test_logs_show_workflow_steps_with_correlation_id() -> None:
    buf = _capture_agent_logs()
    service = DiagnosisService()
    receipt = service.submit(_sample())

    records = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    events = [r["event"] for r in records]
    assert "diagnosis.received" in events
    assert "diagnosis.completed" in events
    assert all(r.get("correlation_id") == receipt["correlation_id"] for r in records)


def test_redact_masks_secret_fields() -> None:
    cleaned = redact({"openai_api_key": "sk-123", "scenario": "high_latency"})
    assert cleaned["openai_api_key"] == "***"
    assert cleaned["scenario"] == "high_latency"


def test_logs_do_not_leak_secrets() -> None:
    buf = _capture_agent_logs()
    log_event(get_logger("test"), "config.loaded", anthropic_api_key="sk-TOPSECRET")
    assert "sk-TOPSECRET" not in buf.getvalue()
    record = json.loads(buf.getvalue().splitlines()[-1])
    assert record["anthropic_api_key"] == "***"


def test_metrics_render_prometheus_text() -> None:
    DiagnosisService().submit(_sample())
    text = METRICS.render()
    assert "# TYPE agent_diagnoses_total counter" in text
    assert "# TYPE agent_request_latency_seconds summary" in text
    assert "agent_diagnoses_total{" in text


def test_metrics_endpoint_and_correlation_header() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.observability import CORRELATION_HEADER

    client = TestClient(app)
    replay = client.post("/incidents/replay/high_latency")
    assert replay.status_code == 201
    assert CORRELATION_HEADER in replay.headers
    assert replay.json()["correlation_id"]

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "agent_requests_total" in metrics.text
