"""Request/response schemas for the KAN-22 connectors.

Stdlib dataclasses, consistent with the rest of the codebase (``backend.analysis``,
``backend.remediation``): no external schema dependency, and every result is
trivially machine-readable via ``to_dict``/``to_json``. Every ``*Result`` extends
:class:`backend.connectors.base.ConnectorResult`, so it carries ``ok`` and an
optional structured ``error`` alongside its payload.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime

from backend.connectors.base import ConnectorResult

# --------------------------------------------------------------------------
# Metrics (Prometheus)
# --------------------------------------------------------------------------


@dataclass
class MetricsQuery:
    """A metrics lookup for one service over a time window."""

    service: str
    query: str  # PromQL in a real connector; a metric-name filter in the mock
    start: datetime
    end: datetime
    step_seconds: int = 60
    # Scenario slug to serve from when using a mock connector. Optional -- if
    # omitted, the mock looks up the pack whose alert.json service matches.
    incident_ref: str | None = None


@dataclass
class MetricPoint:
    t: datetime
    value: float


@dataclass
class MetricSeries:
    name: str
    unit: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    points: list[MetricPoint] = field(default_factory=list)


@dataclass
class MetricsResult(ConnectorResult):
    series: list[MetricSeries] = field(default_factory=list)


# --------------------------------------------------------------------------
# Logs (Loki)
# --------------------------------------------------------------------------


@dataclass
class LogsQuery:
    """A log lookup for one service over a time window."""

    service: str
    query: str = ""  # LogQL in a real connector; a substring filter in the mock
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 500
    incident_ref: str | None = None


@dataclass
class LogLine:
    t: datetime
    level: str
    service: str
    message: str
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class LogsResult(ConnectorResult):
    lines: list[LogLine] = field(default_factory=list)


# --------------------------------------------------------------------------
# Kubernetes
# --------------------------------------------------------------------------


@dataclass
class ServiceHealthQuery:
    service: str
    namespace: str = "default"
    incident_ref: str | None = None


@dataclass
class DependencyStatus:
    name: str
    type: str
    status: str
    latency_ms: float | None = None
    error_rate: float | None = None


@dataclass
class PodStatus:
    name: str
    phase: str  # Running | CrashLoopBackOff | Pending | ...
    ready: bool
    restart_count: int = 0
    last_termination_reason: str | None = None


@dataclass
class ServiceHealthResult(ConnectorResult):
    service: str = ""
    status: str = "unknown"
    version: str | None = None
    replicas_desired: int = 0
    replicas_ready: int = 0
    pods: list[PodStatus] = field(default_factory=list)
    dependencies: list[DependencyStatus] = field(default_factory=list)


# --------------------------------------------------------------------------
# Ticketing (Jira)
# --------------------------------------------------------------------------


@dataclass
class CreateTicketRequest:
    project_key: str
    summary: str
    description: str
    incident_ref: str | None = None
    labels: list[str] = field(default_factory=list)
    priority: str = "Medium"


@dataclass
class AddCommentRequest:
    ticket_id: str
    body: str


@dataclass
class TicketResult(ConnectorResult):
    ticket_id: str | None = None
    url: str | None = None
    status: str | None = None


# --------------------------------------------------------------------------
# Runbook / document retrieval
# --------------------------------------------------------------------------


@dataclass
class RunbookQuery:
    query: str  # free text, e.g. "pod crash loop" or a service name
    service: str | None = None
    top_k: int = 3
    incident_ref: str | None = None


@dataclass
class RunbookDoc:
    id: str
    title: str
    content: str
    source: str = "local"  # e.g. "local", "confluence"
    url: str | None = None
    score: float = 0.0


@dataclass
class RunbookResult(ConnectorResult):
    docs: list[RunbookDoc] = field(default_factory=list)


# --------------------------------------------------------------------------
# Shared (de)serialization helpers
# --------------------------------------------------------------------------


def result_to_dict(result: ConnectorResult) -> dict:
    """JSON-friendly dict for any ``*Result`` -- used by the demo CLI and tests."""
    d = dataclasses.asdict(result)
    d["ok"] = result.ok
    if result.error is not None:
        d["error"] = result.error.to_dict()
    return d


def result_to_json(result: ConnectorResult, indent: int | None = 2) -> str:
    return json.dumps(result_to_dict(result), indent=indent, default=str)
