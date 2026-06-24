"""Tests for the telemetry ingestion layer (KAN-3)."""

import tempfile
from pathlib import Path

import pytest

from backend.telemetry import build_default_ingestor, normalize_alert
from backend.telemetry.connectors.mock_source import MockIncidentSource
from backend.telemetry.ingest import TelemetryIngestor
from backend.telemetry.connectors.alerts import MockAlertConnector
from backend.telemetry.connectors.grafana import GrafanaDashboardConnector
from backend.telemetry.connectors.loki import LokiLogsConnector
from backend.telemetry.connectors.prometheus import PrometheusMetricsConnector
from backend.telemetry.schema import Alert, NormalizedIncident, Severity
from backend.telemetry.store import IncidentStore


def _ingestor(tmp_path: Path) -> TelemetryIngestor:
    source = MockIncidentSource()
    return TelemetryIngestor(
        source=source,
        store=IncidentStore(data_dir=tmp_path),
        alert_connector=MockAlertConnector(source),
        metrics_connector=PrometheusMetricsConnector(source),
        logs_connector=LokiLogsConnector(source),
        dashboard_connector=GrafanaDashboardConnector(source),
    )


def test_normalize_alert_from_payload() -> None:
    """Acceptance: a sample alert payload transforms into the normalized schema."""
    payload = {
        "source": "prometheus",
        "severity": "critical",
        "summary": "p99 latency over SLO",
        "started_at": "2026-06-24T08:12:00Z",
        "labels": {"service": "checkout-api"},
    }
    alert = normalize_alert(payload)
    assert isinstance(alert, Alert)
    assert alert.severity is Severity.critical
    assert alert.labels["service"] == "checkout-api"


def test_ingest_scenario_has_metrics_and_logs(tmp_path: Path) -> None:
    """Acceptance: mock metrics and logs exist for at least one scenario."""
    incident = _ingestor(tmp_path).ingest("high_latency")
    assert isinstance(incident, NormalizedIncident)
    assert incident.alert.summary
    assert len(incident.metrics) >= 1
    assert len(incident.logs) >= 1
    # every metric series carries at least one data point
    assert all(len(m.points) >= 1 for m in incident.metrics)


def test_store_roundtrip(tmp_path: Path) -> None:
    """Normalized incident is persisted and can be read back."""
    ingestor = _ingestor(tmp_path)
    incident = ingestor.ingest("db_saturation")
    loaded = ingestor.store.get_normalized(incident.id)
    assert loaded is not None
    assert loaded.id == incident.id
    assert loaded.scenario == incident.scenario
    # raw payload was also persisted
    assert (tmp_path / "raw" / "db_saturation.json").exists()


def test_default_ingestor_covers_all_scenarios() -> None:
    """The bundled sample data exposes the five documented scenarios."""
    ingestor = build_default_ingestor()
    scenarios = set(ingestor.source.available_scenarios())
    assert {
        "high_latency",
        "error_rate_spike",
        "pod_crash_loop",
        "queue_backlog",
        "db_saturation",
    } <= scenarios


def test_unknown_scenario_raises() -> None:
    source = MockIncidentSource()
    with pytest.raises(FileNotFoundError):
        source.load("does_not_exist")
