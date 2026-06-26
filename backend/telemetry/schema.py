"""Normalized incident-context schema (KAN-3).

This is the canonical, machine-readable shape the agent reasons over. It mirrors
`sample-data/schema/incident.schema.json` and is the contract every telemetry
connector produces. Downstream tickets (RAG KAN-4, reasoning KAN-5) consume
`NormalizedIncident`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Scenario(str, Enum):
    """Supported incident scenarios (see docs/scope.md)."""

    high_latency = "high_latency"
    error_rate_spike = "error_rate_spike"
    pod_crash_loop = "pod_crash_loop"
    queue_backlog = "queue_backlog"
    db_saturation = "db_saturation"


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class Environment(str, Enum):
    local = "local"
    staging = "staging"
    production = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Alert(BaseModel):
    """An inbound alert that opens an incident."""

    source: str = Field(description="Origin system, e.g. prometheus, alertmanager, grafana.")
    severity: Severity
    summary: str
    started_at: datetime
    labels: dict[str, str] = Field(default_factory=dict)


class MetricPoint(BaseModel):
    t: datetime
    value: float


class Metric(BaseModel):
    """A single named time series."""

    name: str
    unit: str
    description: str | None = None
    points: list[MetricPoint] = Field(default_factory=list)


class LogEntry(BaseModel):
    t: datetime
    level: LogLevel
    service: str
    message: str


class ExpectedRootCause(BaseModel):
    """Ground truth for evaluation (KAN-9). Optional in production ingestion."""

    summary: str
    category: str | None = None
    key_signals: list[str] = Field(default_factory=list)
    runbook_references: list[str] = Field(default_factory=list)


class NormalizedIncident(BaseModel):
    """The normalized incident context consumed by the agent."""

    id: str
    scenario: Scenario
    service: str
    environment: Environment
    alert: Alert
    metrics: list[Metric] = Field(default_factory=list)
    logs: list[LogEntry] = Field(default_factory=list)
    expected_root_cause: ExpectedRootCause | None = None
