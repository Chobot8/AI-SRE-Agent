"""Runbook/document retrieval connector (KAN-22).

Distinct from ``backend/rag`` (KAN-4): the RAG package does embedding-based
chunk retrieval to *ground* a diagnosis. This connector is the simpler,
document-level "fetch/search runbooks" tool call an agent loop would use on
demand (e.g. "get the runbook for checkout-api" or "search runbooks for
crash loop").

``MockRunbookConnector`` searches ``knowledge/runbooks/*.md`` plus each
scenario pack's ``runbook.md`` snippet with plain keyword scoring -- no network
access, no embeddings, no credentials. ``RunbookDocsConnector`` is the real
placeholder: once ``runbook_source_base_url`` is configured it fetches
documents from a configurable HTTP document source (e.g. an internal wiki or
Confluence-compatible search endpoint) over stdlib ``urllib``; until then every
call returns a ``not_configured`` error rather than failing.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from backend.connectors.base import (
    ConnectorConfig,
    ConnectorError,
    ConnectorErrorKind,
    RunbookConnector,
    call_with_timeout,
    ssl_context_for,
)
from backend.connectors.scenario_source import (
    ScenarioFixture,
    available_scenario_slugs,
    list_runbooks,
)
from backend.connectors.schemas import RunbookDoc, RunbookQuery, RunbookResult


def _score(text: str, terms: list[str]) -> float:
    lowered = text.lower()
    return float(sum(lowered.count(t) for t in terms if t))


def _auth_headers(config: ConnectorConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.api_token}"} if config.api_token else {}


class MockRunbookConnector(RunbookConnector):
    """Placeholder runbook connector backed by local Markdown fixtures."""

    name = "runbook"

    def search(self, request: RunbookQuery) -> RunbookResult:
        started = time.monotonic()
        terms = [t for t in request.query.lower().split() if t]
        candidates: list[RunbookDoc] = []

        for stem, content in list_runbooks().items():
            candidates.append(
                RunbookDoc(id=f"knowledge/{stem}", title=stem.replace("_", " "), content=content)
            )

        for slug in available_scenario_slugs():
            fixture = ScenarioFixture(slug)
            content = fixture.runbook()
            if content:
                candidates.append(
                    RunbookDoc(
                        id=f"scenarios/{slug}",
                        title=f"{slug} runbook snippet",
                        content=content,
                    )
                )

        latency_ms = (time.monotonic() - started) * 1000
        if not candidates:
            return RunbookResult(
                latency_ms=latency_ms,
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_FOUND,
                    message="no runbook fixtures found under knowledge/ or scenarios/",
                ),
            )

        service_term = [request.service.lower()] if request.service else []
        for doc in candidates:
            doc.score = _score(doc.title + " " + doc.content, terms + service_term)

        ranked = [d for d in candidates if d.score > 0] or candidates
        ranked.sort(key=lambda d: d.score, reverse=True)
        return RunbookResult(latency_ms=latency_ms, docs=ranked[: request.top_k])


class RunbookDocsConnector(RunbookConnector):
    """Real runbook connector -- inert until ``runbook_source_base_url`` is set.

    Configuration (``backend.config.Settings`` / ``.env.example``):
        RUNBOOK_SOURCE_BASE_URL     e.g. an internal wiki/Confluence search API
        RUNBOOK_SOURCE_API_TOKEN
        RUNBOOK_TIMEOUT_SECONDS

    The exact query contract depends on the wiki/document system in use; this
    placeholder assumes a simple ``GET {base_url}/search?q=...`` endpoint that
    returns a JSON list of ``{id, title, content, url}`` objects, and maps that
    response onto :class:`RunbookDoc`. Adjust ``_map_response`` for the real
    system (Confluence, Notion, an internal docs service, ...).
    """

    name = "runbook"

    def __init__(self, config: ConnectorConfig | None = None) -> None:
        self.config = config or ConnectorConfig()

    def search(self, request: RunbookQuery) -> RunbookResult:
        if not self.config.configured:
            return RunbookResult(
                source="real",
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_CONFIGURED,
                    message=(
                        "RUNBOOK_SOURCE_BASE_URL is not set; see backend/connectors/README.md"
                    ),
                ),
            )

        def _do_call() -> RunbookResult:
            params = urllib.parse.urlencode({"q": request.query, "limit": request.top_k})
            url = f"{self.config.base_url}/search?{params}"
            headers = _auth_headers(self.config)
            req = urllib.request.Request(url, headers=headers)
            context = ssl_context_for(self.config)
            with urllib.request.urlopen(
                req, timeout=self.config.timeout_seconds, context=context
            ) as resp:
                payload = json.loads(resp.read())
            return _map_response(payload)

        result, error = call_with_timeout(
            _do_call, timeout_seconds=self.config.timeout_seconds, connector=self.name
        )
        if error is not None:
            return RunbookResult(source="real", error=error)
        assert result is not None
        result.source = "real"
        return result


def _map_response(payload: list[dict]) -> RunbookResult:
    docs = [
        RunbookDoc(
            id=item.get("id", ""),
            title=item.get("title", ""),
            content=item.get("content", ""),
            source="remote",
            url=item.get("url"),
        )
        for item in payload
    ]
    return RunbookResult(docs=docs)
