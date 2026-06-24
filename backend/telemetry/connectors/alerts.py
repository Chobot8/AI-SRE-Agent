"""Alert payload connector (KAN-3) — placeholder.

Serves the inbound alert from the sample-data source and normalizes a raw alert
payload into the :class:`Alert` schema. To make this real, accept webhook
payloads from Alertmanager/PagerDuty and map their fields in ``normalize``.
"""

from __future__ import annotations

from backend.telemetry.connectors.base import AlertConnector
from backend.telemetry.connectors.mock_source import MockIncidentSource
from backend.telemetry.schema import Alert


class MockAlertConnector(AlertConnector):
    """Placeholder alert connector backed by mock incident data."""

    def __init__(self, source: MockIncidentSource | None = None) -> None:
        self.source = source or MockIncidentSource()

    def fetch_alert(self, incident_ref: str) -> Alert:
        raw = self.source.load(incident_ref)
        return self.normalize(raw["alert"])
