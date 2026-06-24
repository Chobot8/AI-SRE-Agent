"""Connector interfaces (KAN-3).

These abstract base classes define the contract for pulling incident context from
an observability source. The MVP ships *placeholder* implementations backed by
mock data (see prometheus.py, grafana.py, loki.py, alerts.py); real connectors
(live Prometheus/Grafana/Loki APIs) implement the same interfaces, so the
ingestion pipeline never changes when a source is swapped.

To add a real connector:
    1. Subclass the relevant interface below.
    2. Implement the single abstract method, returning the normalized type.
    3. Register it when constructing the `TelemetryIngestor`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.telemetry.schema import Alert, LogEntry, Metric


class MetricsConnector(ABC):
    """Source of time-series metrics for an incident (e.g. Prometheus)."""

    @abstractmethod
    def fetch_metrics(self, incident_ref: str) -> list[Metric]:
        """Return the metrics relevant to ``incident_ref`` as normalized series."""


class LogsConnector(ABC):
    """Source of log lines for an incident (e.g. Loki)."""

    @abstractmethod
    def fetch_logs(self, incident_ref: str) -> list[LogEntry]:
        """Return the log entries relevant to ``incident_ref``."""


class AlertConnector(ABC):
    """Source of the inbound alert that opens an incident (e.g. Alertmanager)."""

    @abstractmethod
    def fetch_alert(self, incident_ref: str) -> Alert:
        """Return the normalized alert for ``incident_ref``."""

    @staticmethod
    def normalize(payload: dict) -> Alert:
        """Transform a raw alert payload dict into the normalized :class:`Alert`.

        Real connectors override this to map their provider-specific payload
        (Alertmanager, PagerDuty, etc.) onto the normalized fields.
        """
        return Alert(**payload)


class DashboardConnector(ABC):
    """Source of dashboard references for an incident's service (e.g. Grafana)."""

    @abstractmethod
    def fetch_dashboard_links(self, incident_ref: str) -> list[str]:
        """Return URLs of dashboards relevant to ``incident_ref``."""
