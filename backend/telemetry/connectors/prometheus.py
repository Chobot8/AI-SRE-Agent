"""Prometheus metrics connector (KAN-3) — placeholder.

Serves mock metrics from the sample-data source. To make this real, replace
``fetch_metrics`` with PromQL range queries against the Prometheus HTTP API
(``/api/v1/query_range``) and map the result vectors onto :class:`Metric`.
"""

from __future__ import annotations

from backend.telemetry.connectors.base import MetricsConnector
from backend.telemetry.connectors.mock_source import MockIncidentSource
from backend.telemetry.schema import Metric


class PrometheusMetricsConnector(MetricsConnector):
    """Placeholder Prometheus connector backed by mock incident data."""

    def __init__(self, source: MockIncidentSource | None = None) -> None:
        self.source = source or MockIncidentSource()

    def fetch_metrics(self, incident_ref: str) -> list[Metric]:
        raw = self.source.load(incident_ref)
        return [Metric(**m) for m in raw.get("metrics", [])]
