"""Jira ticketing connector (KAN-22).

Distinct from the Jira/Atlassian *MCP tooling* used elsewhere in this project's
own dev workflow (moving KAN-** tickets between statuses) -- this is the
agent's own connector for incident follow-up: opening or commenting on a
ticket for a *service* incident it diagnosed. It is advisory only, matching
the rest of the agent: nothing calls ``create_ticket``/``add_comment``
automatically as a side effect of a diagnosis; a human (or an explicitly
approved automation step) triggers it, same as every other guardrailed action
in ``backend/remediation``.

``MockTicketingConnector`` creates/comments on tickets in an in-memory store --
no network access, no credentials -- so ``open_ticket`` remediation actions can
be exercised end to end in tests/demos. ``JiraTicketingConnector`` is the real
placeholder: once ``jira_base_url``/``jira_email``/``jira_api_token`` are
configured it calls the Jira Cloud REST API directly over stdlib ``urllib``;
until then every call returns a ``not_configured`` error rather than failing.

Open question from the ticket ("read-only/comment-only first, or create
tickets in the MVP?") is resolved here as: implement both ``create_ticket`` and
``add_comment`` behind the same advisory-only contract, since the guardrail is
*who/what triggers the call*, not which of the two Jira operations it is.
"""

from __future__ import annotations

import base64
import itertools
import json
import time
import urllib.request

from backend.connectors.base import (
    ConnectorConfig,
    ConnectorError,
    ConnectorErrorKind,
    TicketingConnector,
    call_with_timeout,
    ssl_context_for,
)
from backend.connectors.schemas import AddCommentRequest, CreateTicketRequest, TicketResult


class MockTicketingConnector(TicketingConnector):
    """Placeholder Jira connector backed by an in-memory ticket store."""

    name = "jira"
    _id_counter = itertools.count(1)

    def __init__(self) -> None:
        self._tickets: dict[str, dict] = {}

    def create_ticket(self, request: CreateTicketRequest) -> TicketResult:
        started = time.monotonic()
        ticket_id = f"{request.project_key}-{next(self._id_counter)}"
        self._tickets[ticket_id] = {
            "summary": request.summary,
            "description": request.description,
            "labels": list(request.labels),
            "priority": request.priority,
            "comments": [],
        }
        return TicketResult(
            latency_ms=(time.monotonic() - started) * 1000,
            ticket_id=ticket_id,
            url=f"https://example.atlassian.net/browse/{ticket_id}",
            status="Open",
        )

    def add_comment(self, request: AddCommentRequest) -> TicketResult:
        started = time.monotonic()
        ticket = self._tickets.get(request.ticket_id)
        latency_ms = (time.monotonic() - started) * 1000
        if ticket is None:
            return TicketResult(
                latency_ms=latency_ms,
                ticket_id=request.ticket_id,
                error=ConnectorError(
                    connector=self.name,
                    kind=ConnectorErrorKind.NOT_FOUND,
                    message=f"no mock ticket {request.ticket_id!r} (create it first)",
                ),
            )
        ticket["comments"].append(request.body)
        return TicketResult(
            latency_ms=latency_ms,
            ticket_id=request.ticket_id,
            url=f"https://example.atlassian.net/browse/{request.ticket_id}",
            status="Open",
        )


class JiraTicketingConnector(TicketingConnector):
    """Real Jira connector -- inert until base URL + credentials are set.

    Configuration (``backend.config.Settings`` / ``.env.example``):
        JIRA_BASE_URL        e.g. ``https://your-domain.atlassian.net``
        JIRA_EMAIL           the Atlassian account email for the API token
        JIRA_API_TOKEN       an Atlassian API token (never the account password)
        JIRA_TIMEOUT_SECONDS

    Uses the Jira Cloud REST API v3 (``POST /rest/api/3/issue`` and
    ``POST /rest/api/3/issue/{key}/comment``) with HTTP Basic auth
    (email + API token, the documented Jira Cloud auth scheme) over stdlib
    ``urllib`` -- no extra dependency required.
    """

    name = "jira"

    def __init__(self, config: ConnectorConfig | None = None) -> None:
        self.config = config or ConnectorConfig()

    def _auth_header(self) -> dict[str, str]:
        raw = f"{self.config.username}:{self.config.api_token}".encode()
        return {"Authorization": f"Basic {base64.b64encode(raw).decode()}"}

    def _not_configured(self) -> ConnectorError:
        return ConnectorError(
            connector=self.name,
            kind=ConnectorErrorKind.NOT_CONFIGURED,
            message=(
                "JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN are not fully set; "
                "see backend/connectors/README.md"
            ),
        )

    @property
    def _configured(self) -> bool:
        return bool(self.config.base_url and self.config.username and self.config.api_token)

    def create_ticket(self, request: CreateTicketRequest) -> TicketResult:
        if not self._configured:
            return TicketResult(source="real", error=self._not_configured())

        def _do_call() -> TicketResult:
            url = f"{self.config.base_url}/rest/api/3/issue"
            body = json.dumps(
                {
                    "fields": {
                        "project": {"key": request.project_key},
                        "summary": request.summary,
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": request.description}],
                                }
                            ],
                        },
                        "labels": list(request.labels),
                        "issuetype": {"name": "Task"},
                    }
                }
            ).encode()
            headers = {**self._auth_header(), "Content-Type": "application/json"}
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            context = ssl_context_for(self.config)
            with urllib.request.urlopen(
                req, timeout=self.config.timeout_seconds, context=context
            ) as resp:
                payload = json.loads(resp.read())
            key = payload["key"]
            return TicketResult(
                ticket_id=key,
                url=f"{self.config.base_url}/browse/{key}",
                status="Open",
            )

        result, error = call_with_timeout(
            _do_call, timeout_seconds=self.config.timeout_seconds, connector=self.name
        )
        if error is not None:
            return TicketResult(source="real", error=error)
        assert result is not None
        result.source = "real"
        return result

    def add_comment(self, request: AddCommentRequest) -> TicketResult:
        if not self._configured:
            return TicketResult(
                source="real", ticket_id=request.ticket_id, error=self._not_configured()
            )

        def _do_call() -> TicketResult:
            url = f"{self.config.base_url}/rest/api/3/issue/{request.ticket_id}/comment"
            body = json.dumps(
                {
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": request.body}],
                            }
                        ],
                    }
                }
            ).encode()
            headers = {**self._auth_header(), "Content-Type": "application/json"}
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            context = ssl_context_for(self.config)
            with urllib.request.urlopen(
                req, timeout=self.config.timeout_seconds, context=context
            ):
                pass
            return TicketResult(
                ticket_id=request.ticket_id,
                url=f"{self.config.base_url}/browse/{request.ticket_id}",
                status="Open",
            )

        result, error = call_with_timeout(
            _do_call, timeout_seconds=self.config.timeout_seconds, connector=self.name
        )
        if error is not None:
            return TicketResult(source="real", ticket_id=request.ticket_id, error=error)
        assert result is not None
        result.source = "real"
        return result
