"""Loki (log-search) connector (KAN-22).

``MockLokiConnector`` serves log lines from the local scenario-pack /
sample-incident fixtures -- no network access, no credentials. ``LokiConnector``
is the real placeholder: once ``loki_base_url`` is configured it issues an
actual ``/loki/api/v1/query_range`` call over stdlib ``urllib``; until then
every call returns a ``not_configured`` error rather than failing.
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
    LogsConnector,
    call_with_timeout,
    ssl_context_for,
)
from backend.connectors.scenario_source import (
    ScenarioFixture,
    find_scenario_slug_for_service,
    load_sample_incident,
)
from backend.connectors.schemas import LogLine, LogsQuery, LogsResult


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _auth_headers(config: ConnectorConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.api_token}"} if config.api_token else {}


class MockLokiConnector(LogsConnector):
    """Placeholder Loki connector backed by local mock fixtures."""

    name = "loki"

    def query_range(self, request: LogsQuery) -> LogsResult:
        started = time.monotonic()
        slug = request.incident_ref or find_scenario_slug_for_service(request.service)

        raw_logs: list[dict] | None = None
        if slug:
            fixture = ScenarioFixture(slug)
            if fixture.exists():
                raw_logs = fixture.logs()
            if not raw_logs:
                sample = load_sample_incident(slug)
                if sample is not None:
                    raw_logs = sample.get("logs", [])

        latency_ms = (time.monotonic() - started) * 1000
        if raw_logs is None:
            return LogsResult(
                latency_ms=latency_ms,
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_FOUND,
                    message=(
                        f"no mock logs for service={request.service!r} "
                        f"incident_ref={request.incident_ref!r}"
                    ),
                ),
            )

        needle = (request.query or "").lower()
        lines = [
            LogLine(
                t=_parse_time(entry["t"]),
                level=entry.get("level", "INFO"),
                service=entry.get("service", request.service),
                message=entry.get("message", ""),
            )
            for entry in raw_logs
            if not needle or needle in entry.get("message", "").lower()
        ][: request.limit]
        return LogsResult(latency_ms=latency_ms, lines=lines)


class LokiConnector(LogsConnector):
    """Real Loki connector -- inert until ``loki_base_url`` is set.

    Configuration (``backend.config.Settings`` / ``.env.example``):
        LOKI_BASE_URL           e.g. ``http://loki:3100``
        LOKI_TIMEOUT_SECONDS
    """

    name = "loki"

    def __init__(self, config: ConnectorConfig | None = None) -> None:
        self.config = config or ConnectorConfig()

    def query_range(self, request: LogsQuery) -> LogsResult:
        if not self.config.configured:
            return LogsResult(
                source="real",
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_CONFIGURED,
                    message="LOKI_BASE_URL is not set; see backend/connectors/README.md",
                ),
            )

        def _do_call() -> LogsResult:
            logql = request.query or f'{{service="{request.service}"}}'
            params: dict[str, str] = {"query": logql, "limit": str(request.limit)}
            if request.start is not None:
                params["start"] = str(int(request.start.timestamp() * 1e9))
            if request.end is not None:
                params["end"] = str(int(request.end.timestamp() * 1e9))
            query_string = urllib.parse.urlencode(params)
            url = f"{self.config.base_url}/loki/api/v1/query_range?{query_string}"
            headers = _auth_headers(self.config)
            req = urllib.request.Request(url, headers=headers)
            context = ssl_context_for(self.config)
            with urllib.request.urlopen(
                req, timeout=self.config.timeout_seconds, context=context
            ) as resp:
                payload = json.loads(resp.read())
            return _map_response(payload, request.service)

        result, error = call_with_timeout(
            _do_call, timeout_seconds=self.config.timeout_seconds, connector=self.name
        )
        if error is not None:
            return LogsResult(source="real", error=error)
        assert result is not None
        result.source = "real"
        return result


def _map_response(payload: dict, service: str) -> LogsResult:
    if payload.get("status") != "success":
        return LogsResult(
            error=ConnectorError(
                connector="loki",
                kind=ConnectorErrorKind.INVALID_RESPONSE,
                message=str(payload.get("error") or "unexpected Loki response shape"),
            )
        )
    lines: list[LogLine] = []
    for stream in payload.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        for ts_ns, message in stream.get("values", []):
            lines.append(
                LogLine(
                    t=datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc),
                    level=labels.get("level", "INFO"),
                    service=labels.get("service", service),
                    message=message,
                    labels=labels,
                )
            )
    return LogsResult(lines=lines)
