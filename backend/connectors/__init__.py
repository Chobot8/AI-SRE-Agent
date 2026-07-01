"""SRE tool connectors (KAN-22): Prometheus, Loki, Kubernetes, Jira, runbooks.

See ``backend/connectors/README.md`` for the interface contract and which
connectors are real, mocked, or planned.
"""

from backend.connectors.base import (
    ConnectorConfig,
    ConnectorError,
    ConnectorErrorKind,
    ConnectorResult,
    KubernetesConnector,
    LogsConnector,
    MetricsConnector,
    RunbookConnector,
    TicketingConnector,
    call_with_timeout,
    ssl_context_for,
)
from backend.connectors.jira import JiraTicketingConnector, MockTicketingConnector
from backend.connectors.kubernetes import KubernetesApiConnector, MockKubernetesConnector
from backend.connectors.loki import LokiConnector, MockLokiConnector
from backend.connectors.prometheus import MockPrometheusConnector, PrometheusConnector
from backend.connectors.runbook import MockRunbookConnector, RunbookDocsConnector

__all__ = [
    # Base contract
    "ConnectorConfig",
    "ConnectorError",
    "ConnectorErrorKind",
    "ConnectorResult",
    "call_with_timeout",
    "ssl_context_for",
    # Interfaces
    "KubernetesConnector",
    "LogsConnector",
    "MetricsConnector",
    "RunbookConnector",
    "TicketingConnector",
    # Prometheus
    "MockPrometheusConnector",
    "PrometheusConnector",
    # Loki
    "MockLokiConnector",
    "LokiConnector",
    # Kubernetes
    "MockKubernetesConnector",
    "KubernetesApiConnector",
    # Jira / ticketing
    "MockTicketingConnector",
    "JiraTicketingConnector",
    # Runbooks
    "MockRunbookConnector",
    "RunbookDocsConnector",
]
