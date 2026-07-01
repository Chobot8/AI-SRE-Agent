"""Tests for the KAN-22 SRE tool connectors.

Covers the ticket's acceptance criteria: mock connectors power every existing
scenario pack, connector errors come back as structured results (never an
unhandled exception), timeout handling works, and every real connector stays
inert (returns `not_configured`, makes no network call) with no credentials
configured.
"""

from __future__ import annotations

import ssl
import time
from datetime import datetime, timedelta, timezone

import pytest

from backend.connectors.base import (
    ConnectorConfig,
    ConnectorError,
    ConnectorErrorKind,
    call_with_timeout,
    ssl_context_for,
)
from backend.connectors.jira import JiraTicketingConnector, MockTicketingConnector
from backend.connectors.kubernetes import KubernetesApiConnector, MockKubernetesConnector
from backend.connectors.loki import LokiConnector, MockLokiConnector
from backend.connectors.prometheus import MockPrometheusConnector, PrometheusConnector
from backend.connectors.runbook import MockRunbookConnector, RunbookDocsConnector
from backend.connectors.scenario_source import ScenarioFixture, available_scenario_slugs
from backend.connectors.schemas import (
    AddCommentRequest,
    CreateTicketRequest,
    LogsQuery,
    MetricsQuery,
    RunbookQuery,
    ServiceHealthQuery,
)

SLUGS = available_scenario_slugs()
NOW = datetime.now(tz=timezone.utc)
WINDOW_START = NOW - timedelta(hours=1)


def test_scenario_packs_exist() -> None:
    assert len(SLUGS) >= 5, f"expected the KAN-18 scenario packs, found {SLUGS}"


# --- Mock connectors power every existing scenario pack ----------------------


@pytest.mark.parametrize("slug", SLUGS)
def test_mock_prometheus_covers_every_pack(slug: str) -> None:
    service = ScenarioFixture(slug).alert()["service"]
    result = MockPrometheusConnector().query_range(
        MetricsQuery(service=service, query="", start=WINDOW_START, end=NOW, incident_ref=slug)
    )
    assert result.ok, result.diagnostic_notes()
    assert result.source == "mock"
    assert len(result.series) >= 1
    assert all(len(s.points) >= 1 for s in result.series)


@pytest.mark.parametrize("slug", SLUGS)
def test_mock_loki_covers_every_pack(slug: str) -> None:
    service = ScenarioFixture(slug).alert()["service"]
    result = MockLokiConnector().query_range(LogsQuery(service=service, incident_ref=slug))
    assert result.ok, result.diagnostic_notes()
    assert len(result.lines) >= 1


@pytest.mark.parametrize("slug", SLUGS)
def test_mock_kubernetes_covers_every_pack(slug: str) -> None:
    service = ScenarioFixture(slug).alert()["service"]
    result = MockKubernetesConnector().get_service_health(
        ServiceHealthQuery(service=service, incident_ref=slug)
    )
    assert result.ok, result.diagnostic_notes()
    assert result.replicas_desired >= result.replicas_ready >= 0
    assert len(result.pods) == result.replicas_desired


@pytest.mark.parametrize("slug", SLUGS)
def test_mock_runbook_covers_every_pack(slug: str) -> None:
    result = MockRunbookConnector().search(RunbookQuery(query=slug.replace("-", " ")))
    assert result.ok, result.diagnostic_notes()
    assert len(result.docs) >= 1


def test_mock_ticketing_create_then_comment() -> None:
    connector = MockTicketingConnector()
    created = connector.create_ticket(
        CreateTicketRequest(project_key="KAN", summary="s", description="d")
    )
    assert created.ok
    assert created.ticket_id and created.ticket_id.startswith("KAN-")

    commented = connector.add_comment(AddCommentRequest(ticket_id=created.ticket_id, body="hi"))
    assert commented.ok


# --- Errors are structured results, never unhandled exceptions ---------------


def test_unknown_service_is_not_found_not_an_exception() -> None:
    result = MockPrometheusConnector().query_range(
        MetricsQuery(service="does-not-exist", query="", start=WINDOW_START, end=NOW)
    )
    assert not result.ok
    assert result.error is not None
    assert result.error.kind is ConnectorErrorKind.NOT_FOUND
    assert result.error.connector == "prometheus"
    # the shape callers append to evidence/diagnostic warnings
    assert result.diagnostic_notes() == [result.error.as_diagnostic_note()]
    assert "prometheus" in result.diagnostic_notes()[0]


def test_comment_on_unknown_ticket_is_not_found() -> None:
    result = MockTicketingConnector().add_comment(AddCommentRequest(ticket_id="KAN-999", body="x"))
    assert not result.ok
    assert result.error.kind is ConnectorErrorKind.NOT_FOUND


# --- Timeout handling ---------------------------------------------------------


def test_call_with_timeout_success() -> None:
    value, error = call_with_timeout(lambda: 42, timeout_seconds=1.0, connector="test")
    assert value == 42
    assert error is None


def test_call_with_timeout_times_out() -> None:
    def _slow() -> int:
        time.sleep(0.3)
        return 1

    value, error = call_with_timeout(_slow, timeout_seconds=0.05, connector="test")
    assert value is None
    assert error is not None
    assert error.kind is ConnectorErrorKind.TIMEOUT
    assert error.retryable is True


def test_call_with_timeout_converts_exception() -> None:
    def _boom() -> int:
        raise RuntimeError("upstream exploded")

    value, error = call_with_timeout(_boom, timeout_seconds=1.0, connector="test")
    assert value is None
    assert error.kind is ConnectorErrorKind.UNAVAILABLE
    assert "upstream exploded" in error.message


# --- Real connectors are inert without configuration --------------------------


@pytest.mark.parametrize(
    "connector_cls",
    [PrometheusConnector, LokiConnector, KubernetesApiConnector, RunbookDocsConnector],
)
def test_real_connectors_report_not_configured(connector_cls) -> None:
    connector = connector_cls(ConnectorConfig())  # no base_url
    if connector_cls is PrometheusConnector:
        result = connector.query_range(
            MetricsQuery(service="checkout-api", query="up", start=WINDOW_START, end=NOW)
        )
    elif connector_cls is LokiConnector:
        result = connector.query_range(LogsQuery(service="checkout-api"))
    elif connector_cls is KubernetesApiConnector:
        result = connector.get_service_health(ServiceHealthQuery(service="checkout-api"))
    else:
        result = connector.search(RunbookQuery(query="crash loop"))

    assert not result.ok
    assert result.error.kind is ConnectorErrorKind.NOT_CONFIGURED
    assert result.source == "real"


def test_real_jira_connector_reports_not_configured() -> None:
    connector = JiraTicketingConnector(ConnectorConfig())
    result = connector.create_ticket(
        CreateTicketRequest(project_key="KAN", summary="s", description="d")
    )
    assert not result.ok
    assert result.error.kind is ConnectorErrorKind.NOT_CONFIGURED
    assert result.source == "real"


def test_connector_config_configured_property() -> None:
    assert ConnectorConfig().configured is False
    assert ConnectorConfig(base_url="http://x").configured is True


# --- call_with_timeout must actually return around the timeout budget ---------


def test_call_with_timeout_returns_promptly_not_after_slow_call_finishes() -> None:
    """Regression: a `with ThreadPoolExecutor(...)` block blocks on __exit__
    (shutdown(wait=True)) until the worker thread finishes, which used to make
    a 50ms timeout around a much slower call return only once the slow call
    completed -- silently defeating the timeout contract."""

    def _slow() -> int:
        time.sleep(1.0)
        return 1

    started = time.monotonic()
    value, error = call_with_timeout(_slow, timeout_seconds=0.05, connector="test")
    elapsed = time.monotonic() - started

    assert value is None
    assert error.kind is ConnectorErrorKind.TIMEOUT
    # generous upper bound vs. the 1s the slow call actually takes -- this
    # call must return close to the requested 0.05s timeout, not ~1s later
    assert elapsed < 0.5, f"call_with_timeout blocked for {elapsed:.2f}s past its timeout"


# --- ssl_context_for must honor ConnectorConfig.verify_tls --------------------


def test_ssl_context_for_default_verifies() -> None:
    context = ssl_context_for(ConnectorConfig())
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_ssl_context_for_respects_verify_tls_false() -> None:
    """Regression: KUBERNETES_VERIFY_TLS (and the general verify_tls config
    field) was documented/exposed but never actually applied to the urlopen
    call, so a self-signed local cluster would fail even with it set false."""
    context = ssl_context_for(ConnectorConfig(verify_tls=False))
    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False


def test_connector_error_diagnostic_note_format() -> None:
    err = ConnectorError(
        connector="loki", kind=ConnectorErrorKind.TIMEOUT, message="timed out after 5s"
    )
    assert err.as_diagnostic_note() == "[loki] timeout: timed out after 5s"
    assert err.to_dict()["kind"] == "timeout"
