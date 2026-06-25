"""Telemetry ingestion layer (KAN-3).

Provides the normalized incident-context schema, extensible source connectors
(Prometheus / Grafana / Loki / alert payloads), mock data ingestion for local
development, and storage for raw and normalized incident data.
"""

from backend.telemetry.ingest import TelemetryIngestor, build_default_ingestor, normalize_alert
from backend.telemetry.schema import (
    Alert,
    LogEntry,
    Metric,
    MetricPoint,
    NormalizedIncident,
)

__all__ = [
    "Alert",
    "LogEntry",
    "Metric",
    "MetricPoint",
    "NormalizedIncident",
    "TelemetryIngestor",
    "build_default_ingestor",
    "normalize_alert",
]
