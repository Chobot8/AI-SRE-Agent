"""Shared connector contract (KAN-22).

This package defines a uniform contract for connectors to *live* SRE systems --
Prometheus, Loki, Kubernetes, Jira, and runbook/document sources. It is
deliberately separate from ``backend/telemetry/connectors`` (KAN-3), which
ingests a fixed incident payload once at replay time; these connectors model
the *ad hoc*, on-demand calls a future agent tool-calling loop would make while
investigating an incident (pull more metrics, check pod health, open a
follow-up ticket, look up a runbook) -- so they carry a timeout and structured
error model that batch ingestion did not need.

Contract every connector follows:

* Each method takes a typed request (see ``schemas.py``) and returns a typed
  result. The result always carries ``ok`` plus an optional structured
  :class:`ConnectorError` instead of raising for *expected* failure modes
  (timeout, not configured, not found, auth, upstream error) -- callers turn a
  failed result into an evidence/diagnostic-warning string via
  :meth:`ConnectorResult.diagnostic_notes`, never an unhandled exception.
* Every connector has a **mock** implementation backed by local, git-committed
  fixtures (the ``scenarios/`` packs and ``knowledge/runbooks/``) that needs no
  network access or credentials, so it can power every scenario pack and the
  test suite offline.
* Every connector also has an optional **real** implementation. It is inert
  (returns a ``not_configured`` error, makes no network call) until the
  relevant setting in ``backend.config.Settings`` is supplied, so the local
  demo never requires real production credentials.

To add/complete a real connector: subclass the relevant interface, read
connection details from a :class:`ConnectorConfig` (sourced from
``backend.config.get_settings()``), and wrap the network call in
:func:`call_with_timeout`. Nothing downstream changes -- callers only depend on
the interface and the typed result, exactly as the KAN-3 telemetry connectors
already do for ingestion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from backend.connectors.schemas import (
        AddCommentRequest,
        CreateTicketRequest,
        LogsQuery,
        LogsResult,
        MetricsQuery,
        MetricsResult,
        RunbookQuery,
        RunbookResult,
        ServiceHealthQuery,
        ServiceHealthResult,
        TicketResult,
    )

T = TypeVar("T")

# Default wall-clock budget for a single connector call when the caller does
# not override it via ConnectorConfig.timeout_seconds.
DEFAULT_TIMEOUT_SECONDS = 5.0


class ConnectorErrorKind(str, Enum):
    """The closed set of failure modes a connector may report.

    Kept small and stable so callers (the analysis/remediation pipeline, or a
    future agent loop) can branch on ``kind`` without knowing about any single
    connector's internals.
    """

    TIMEOUT = "timeout"
    NOT_CONFIGURED = "not_configured"
    NOT_FOUND = "not_found"
    AUTH = "auth"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"
    RATE_LIMITED = "rate_limited"


@dataclass
class ConnectorError:
    """A structured, non-fatal connector failure.

    Never raised as an exception by connector methods -- it is returned inside
    a :class:`ConnectorResult` so a failed call degrades to evidence/a
    diagnostic warning instead of crashing the caller.
    """

    connector: str
    kind: ConnectorErrorKind
    message: str
    retryable: bool = False

    def to_dict(self) -> dict:
        return {
            "connector": self.connector,
            "kind": self.kind.value,
            "message": self.message,
            "retryable": self.retryable,
        }

    def as_diagnostic_note(self) -> str:
        """One-line, human-readable form suitable for an evidence/warning list."""
        return f"[{self.connector}] {self.kind.value}: {self.message}"


@dataclass
class ConnectorResult:
    """Base outcome shared by every connector response.

    Subclasses (see ``schemas.py``) add the payload fields. A result is
    successful iff ``error`` is ``None`` -- check :attr:`ok` rather than
    inspecting the payload directly.
    """

    source: str = "mock"  # "mock" | "real"
    error: ConnectorError | None = None
    latency_ms: float | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def diagnostic_notes(self) -> list[str]:
        """Zero-or-one-element list -- the shape callers append to evidence/warnings."""
        return [self.error.as_diagnostic_note()] if self.error else []


@dataclass
class ConnectorConfig:
    """Connection + credential settings for a real connector.

    Every field is optional. A connector whose ``base_url`` is unset stays
    inert -- real methods return a ``not_configured`` :class:`ConnectorError`
    and make no network call, which is how the local demo runs with zero
    production credentials (acceptance criterion). Populate these from
    ``backend.config.get_settings()`` (env-driven, ``.env`` is gitignored);
    never hardcode real values.
    """

    base_url: str | None = None
    api_token: str | None = None
    username: str | None = None  # e.g. a Jira account email for basic auth
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    verify_tls: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.base_url)


def call_with_timeout(
    fn: Callable[[], T],
    *,
    timeout_seconds: float,
    connector: str,
) -> tuple[T | None, ConnectorError | None]:
    """Run ``fn`` under a hard wall-clock timeout; never let it raise.

    Used by both real connectors (to bound a blocking network call even if the
    underlying client's own timeout misbehaves) and, in tests, to exercise
    timeout handling deterministically. Any exception ``fn`` raises -- network
    error, malformed response, etc. -- is caught here and converted into an
    ``unavailable`` :class:`ConnectorError`; callers only ever see the tuple.

    Returns ``(value, None)`` on success or ``(None, ConnectorError)`` on
    failure.
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_seconds), None
        except FuturesTimeout:
            future.cancel()
            return None, ConnectorError(
                connector=connector,
                kind=ConnectorErrorKind.TIMEOUT,
                message=f"timed out after {timeout_seconds}s",
                retryable=True,
            )
        except Exception as exc:  # noqa: BLE001 - connectors must not raise
            return None, ConnectorError(
                connector=connector,
                kind=ConnectorErrorKind.UNAVAILABLE,
                message=str(exc),
                retryable=True,
            )


class MetricsConnector(ABC):
    """Source of time-series metrics for a service (e.g. Prometheus)."""

    name: str = "metrics"

    @abstractmethod
    def query_range(self, request: "MetricsQuery") -> "MetricsResult":
        """Return the metric series matching ``request`` over its time window."""


class LogsConnector(ABC):
    """Source of log lines for a service (e.g. Loki)."""

    name: str = "logs"

    @abstractmethod
    def query_range(self, request: "LogsQuery") -> "LogsResult":
        """Return the log lines matching ``request`` over its time window."""


class KubernetesConnector(ABC):
    """Kubernetes service/pod health for a service."""

    name: str = "kubernetes"

    @abstractmethod
    def get_service_health(self, request: "ServiceHealthQuery") -> "ServiceHealthResult":
        """Return replica/pod status and dependency health for a service."""


class TicketingConnector(ABC):
    """Issue creation/commenting for incident follow-up (e.g. Jira).

    Advisory only, matching the rest of the agent: creating or commenting on a
    ticket is something a human (or an explicitly approved automation step)
    triggers -- this interface never gets called as a side effect of a
    diagnosis alone.
    """

    name: str = "ticketing"

    @abstractmethod
    def create_ticket(self, request: "CreateTicketRequest") -> "TicketResult":
        """Open a new follow-up ticket; return its id/url or a connector error."""

    @abstractmethod
    def add_comment(self, request: "AddCommentRequest") -> "TicketResult":
        """Append a comment to an existing ticket."""


class RunbookConnector(ABC):
    """Runbook/document retrieval for a service or free-text query.

    Distinct from ``backend/rag`` (KAN-4): the RAG package does embedding-based
    chunk retrieval to *ground* a diagnosis. This connector is the simpler,
    document-level "fetch/search runbooks" tool call an agent loop would use on
    demand (e.g. "get the runbook for checkout-api").
    """

    name: str = "runbook"

    @abstractmethod
    def search(self, request: "RunbookQuery") -> "RunbookResult":
        """Return up to ``request.top_k`` runbook documents matching the query."""
