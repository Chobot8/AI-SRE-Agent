"""Prometheus metrics connector (KAN-22).

``MockPrometheusConnector`` serves metric series from the local scenario-pack /
sample-incident fixtures -- no network access, no credentials. ``PrometheusConnector``
is the real placeholder: once ``prometheus_base_url`` is configured it issues an
actual ``/api/v1/query_range`` call over stdlib ``urllib`` (no extra dependency);
until then every call returns a ``not_configured`` error rather than failing.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from backend.connectors.base import (
    ConnectorConfig,
    ConnectorError,
    ConnectorErrorKind,
    MetricsConnector,
    call_with_timeout,
)
from backend.connectors.scenario_source import (
    ScenarioFixture,
    find_scenario_slug_for_service,
    load_sample_incident,
)
from backend.connectors.schemas import MetricPoint, MetricSeries, MetricsQuery, MetricsResult


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _auth_headers(config: ConnectorConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.api_token}"} if config.api_token else {}


class MockPrometheusConnector(MetricsConnector):
    """Placeholder Prometheus connector backed by local mock fixtures."""

    name = "prometheus"

    def query_range(self, request: MetricsQuery) -> MetricsResult:
        started = time.monotonic()
        slug = request.incident_ref or find_scenario_slug_for_service(request.service)

        raw_metrics: list[dict] | None = None
        if slug:
            fixture = ScenarioFixture(slug)
            if fixture.exists():
                raw_metrics = fixture.metrics()
            if raw_metrics is None:
                sample = load_sample_incident(slug)
                if sample is not None:
                    raw_metrics = sample.get("metrics", [])

        latency_ms = (time.monotonic() - started) * 1000
        if raw_metrics is None:
            return MetricsResult(
                latency_ms=latency_ms,
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_FOUND,
                    message=(
                        f"no mock metrics for service={request.service!r} "
                        f"incident_ref={request.incident_ref!r}"
                    ),
                ),
            )

        query = (request.query or "").lower()
        series = [
            MetricSeries(
                name=m["name"],
                unit=m.get("unit", ""),
                points=[
                    MetricPoint(t=_parse_time(p["t"]), value=float(p["value"]))
                    for p in m.get("points", [])
                ],
            )
            for m in raw_metrics
            if not query or query in ("*", "all") or query in m["name"].lower()
        ]
        return MetricsResult(latency_ms=latency_ms, series=series)


class PrometheusConnector(MetricsConnector):
    """Real Prometheus connector -- inert until ``prometheus_base_url`` is set.

    Configuration (``backend.config.Settings`` / ``.env.example``):
        PROMETHEUS_BASE_URL        e.g. ``http://prometheus:9090``
        PROMETHEUS_TIMEOUT_SECONDS

    No credential is modeled by default because most in-cluster Prometheus
    deployments are reached over a trusted network; set ``config.api_token`` to
    add a bearer token (e.g. behind an authenticating proxy) if a deployment
    needs one -- see ``backend/connectors/README.md``.
    """

    name = "prometheus"

    def __init__(self, config: ConnectorConfig | None = None) -> None:
        self.config = config or ConnectorConfig()

    def query_range(self, request: MetricsQuery) -> MetricsResult:
        if not self.config.configured:
            return MetricsResult(
                source="real",
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_CONFIGURED,
                    message="PROMETHEUS_BASE_URL is not set; see backend/connectors/README.md",
                ),
            )

        def _do_call() -> MetricsResult:
            params = urllib.parse.urlencode(
                {
                    "query": request.query,
                    "start": request.start.timestamp(),
                    "end": request.end.timestamp(),
                    "step": request.step_seconds,
                }
            )
            url = f"{self.config.base_url}/api/v1/query_range?{params}"
            headers = _auth_headers(self.config)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                payload = json.loads(resp.read())
            return _map_response(payload, request.query)

        result, error = call_with_timeout(
            _do_call, timeout_seconds=self.config.timeout_seconds, connector=self.name
        )
        if error is not None:
            return MetricsResult(source="real", error=error)
        assert result is not None
        result.source = "real"
        return result


def _map_response(payload: dict, query: str) -> MetricsResult:
    if payload.get("status") != "success":
        return MetricsResult(
            error=ConnectorError(
                connector="prometheus",
                kind=ConnectorErrorKind.INVALID_RESPONSE,
                message=str(payload.get("error") or "unexpected Prometheus response shape"),
            )
        )
    series = []
    for result in payload.get("data", {}).get("result", []):
        labels = result.get("metric", {})
        points = [
            MetricPoint(t=datetime.fromtimestamp(t, tz=timezone.utc), value=float(v))
            for t, v in result.get("values", [])
        ]
        name = labels.get("__name__", query)
        series.append(MetricSeries(name=name, labels=labels, points=points))
    return MetricsResult(series=series)
