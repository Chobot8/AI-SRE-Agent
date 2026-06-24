"""Loki logs connector (KAN-3) — placeholder.

Serves mock logs from the sample-data source. To make this real, replace
``fetch_logs`` with LogQL queries against the Loki HTTP API
(``/loki/api/v1/query_range``) and map streams onto :class:`LogEntry`.
"""

from __future__ import annotations

from backend.telemetry.connectors.base import LogsConnector
from backend.telemetry.connectors.mock_source import MockIncidentSource
from backend.telemetry.schema import LogEntry


class LokiLogsConnector(LogsConnector):
    """Placeholder Loki connector backed by mock incident data."""

    def __init__(self, source: MockIncidentSource | None = None) -> None:
        self.source = source or MockIncidentSource()

    def fetch_logs(self, incident_ref: str) -> list[LogEntry]:
        raw = self.source.load(incident_ref)
        return [LogEntry(**entry) for entry in raw.get("logs", [])]
