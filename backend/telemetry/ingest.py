"""Telemetry ingestion pipeline (KAN-3).

Orchestrates the source connectors into a single normalized incident:

    alert payload + metrics + logs  ->  NormalizedIncident  ->  stored (raw + normalized)

`build_default_ingestor()` wires the mock/placeholder connectors and a filesystem
store so the whole flow runs locally with no external dependencies.
"""

from __future__ import annotations

from backend.telemetry.connectors.alerts import MockAlertConnector
from backend.telemetry.connectors.base import (
    AlertConnector,
    DashboardConnector,
    LogsConnector,
    MetricsConnector,
)
from backend.telemetry.connectors.grafana import GrafanaDashboardConnector
from backend.telemetry.connectors.loki import LokiLogsConnector
from backend.telemetry.connectors.mock_source import MockIncidentSource
from backend.telemetry.connectors.prometheus import PrometheusMetricsConnector
from backend.telemetry.schema import Alert, NormalizedIncident
from backend.telemetry.store import IncidentStore


def normalize_alert(payload: dict) -> Alert:
    """Convenience: transform a raw alert payload dict into a normalized Alert."""
    return AlertConnector.normalize(payload)


class TelemetryIngestor:
    """Combines source connectors into stored, normalized incidents."""

    def __init__(
        self,
        source: MockIncidentSource,
        store: IncidentStore,
        alert_connector: AlertConnector,
        metrics_connector: MetricsConnector,
        logs_connector: LogsConnector,
        dashboard_connector: DashboardConnector | None = None,
    ) -> None:
        self.source = source
        self.store = store
        self.alerts = alert_connector
        self.metrics = metrics_connector
        self.logs = logs_connector
        self.dashboards = dashboard_connector

    def ingest(self, scenario: str) -> NormalizedIncident:
        """Ingest one scenario into a stored, normalized incident."""
        raw = self.source.load(scenario)
        self.store.save_raw(scenario, raw)

        incident = NormalizedIncident(
            id=raw["id"],
            scenario=raw["scenario"],
            service=raw["service"],
            environment=raw["environment"],
            alert=self.alerts.fetch_alert(scenario),
            metrics=self.metrics.fetch_metrics(scenario),
            logs=self.logs.fetch_logs(scenario),
            expected_root_cause=raw.get("expected_root_cause"),
        )
        self.store.save_normalized(incident)
        return incident

    def ingest_all(self) -> list[NormalizedIncident]:
        """Ingest every scenario available in the source."""
        return [self.ingest(s) for s in self.source.available_scenarios()]


def build_default_ingestor() -> TelemetryIngestor:
    """Wire the placeholder connectors + filesystem store for local use."""
    source = MockIncidentSource()
    return TelemetryIngestor(
        source=source,
        store=IncidentStore(),
        alert_connector=MockAlertConnector(source),
        metrics_connector=PrometheusMetricsConnector(source),
        logs_connector=LokiLogsConnector(source),
        dashboard_connector=GrafanaDashboardConnector(source),
    )
