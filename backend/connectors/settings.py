"""Build a :class:`ConnectorConfig` for each real connector from app settings.

Centralizes the mapping from ``backend.config.Settings`` (env-driven) onto the
per-connector config so real connectors are wired the same way everywhere
(API startup, CLI, tests) and so there is exactly one place that reads
credential-shaped settings.
"""

from __future__ import annotations

from backend.config import Settings, get_settings
from backend.connectors.base import ConnectorConfig


def prometheus_config(settings: Settings | None = None) -> ConnectorConfig:
    s = settings or get_settings()
    return ConnectorConfig(
        base_url=s.prometheus_base_url, timeout_seconds=s.prometheus_timeout_seconds
    )


def loki_config(settings: Settings | None = None) -> ConnectorConfig:
    s = settings or get_settings()
    return ConnectorConfig(base_url=s.loki_base_url, timeout_seconds=s.loki_timeout_seconds)


def kubernetes_config(settings: Settings | None = None) -> ConnectorConfig:
    s = settings or get_settings()
    return ConnectorConfig(
        base_url=s.kubernetes_api_base_url,
        api_token=s.kubernetes_bearer_token,
        verify_tls=s.kubernetes_verify_tls,
        timeout_seconds=s.kubernetes_timeout_seconds,
    )


def jira_config(settings: Settings | None = None) -> ConnectorConfig:
    s = settings or get_settings()
    return ConnectorConfig(
        base_url=s.jira_base_url,
        username=s.jira_email,
        api_token=s.jira_api_token,
        timeout_seconds=s.jira_timeout_seconds,
    )


def runbook_config(settings: Settings | None = None) -> ConnectorConfig:
    s = settings or get_settings()
    return ConnectorConfig(
        base_url=s.runbook_source_base_url,
        api_token=s.runbook_source_api_token,
        timeout_seconds=s.runbook_timeout_seconds,
    )
