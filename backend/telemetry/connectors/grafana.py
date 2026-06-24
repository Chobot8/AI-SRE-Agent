"""Grafana dashboard connector (KAN-3) — placeholder.

Returns mock dashboard links for an incident's service. To make this real, query
the Grafana HTTP API (``/api/search``) for dashboards tagged with the service and
return deep links scoped to the incident time window.
"""

from __future__ import annotations

from backend.telemetry.connectors.base import DashboardConnector
from backend.telemetry.connectors.mock_source import MockIncidentSource


class GrafanaDashboardConnector(DashboardConnector):
    """Placeholder Grafana connector backed by mock incident data."""

    def __init__(
        self,
        source: MockIncidentSource | None = None,
        base_url: str = "https://grafana.example.com",
    ) -> None:
        self.source = source or MockIncidentSource()
        self.base_url = base_url.rstrip("/")

    def fetch_dashboard_links(self, incident_ref: str) -> list[str]:
        raw = self.source.load(incident_ref)
        service = raw.get("service", "unknown")
        return [f"{self.base_url}/d/{service}/{service}-overview"]
