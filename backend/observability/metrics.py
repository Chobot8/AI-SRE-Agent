"""In-process metrics registry (KAN-12).

A tiny, dependency-free metrics layer the agent can write to and that can be
scraped locally in Prometheus text exposition format (``GET /metrics``) or
inspected as a dict in tests. It is intentionally minimal — counters and
summaries (count + sum) — which is enough to expose requests, latency, failures,
retrieval counts, and LLM call/token usage without pulling in a metrics SDK.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping

_Labels = tuple[tuple[str, str], ...]


def _key(labels: Mapping[str, str] | None) -> _Labels:
    if not labels:
        return ()
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


def _format_labels(key: _Labels) -> str:
    if not key:
        return ""
    inner = ",".join(f'{name}="{_escape(value)}"' for name, value in key)
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Counter:
    """A monotonically increasing counter, optionally partitioned by labels."""

    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help_text = help_text
        self._values: dict[_Labels, float] = {}
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = _key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def value(self, **labels: str) -> float:
        return self._values.get(_key(labels), 0.0)

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} counter"]
        for key, val in sorted(self._values.items()):
            lines.append(f"{self.name}{_format_labels(key)} {_num(val)}")
        return lines

    def snapshot(self) -> dict[str, float]:
        return {_format_labels(key) or "_": val for key, val in self._values.items()}


class Summary:
    """Tracks observation count and sum (e.g. request latency), by labels."""

    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help_text = help_text
        self._counts: dict[_Labels, float] = {}
        self._sums: dict[_Labels, float] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, **labels: str) -> None:
        key = _key(labels)
        with self._lock:
            self._counts[key] = self._counts.get(key, 0.0) + 1
            self._sums[key] = self._sums.get(key, 0.0) + value

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} summary"]
        for key in sorted(self._counts):
            labels = _format_labels(key)
            lines.append(f"{self.name}_count{labels} {_num(self._counts[key])}")
            lines.append(f"{self.name}_sum{labels} {_num(self._sums[key])}")
        return lines

    def snapshot(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for key in self._counts:
            out[_format_labels(key) or "_"] = {
                "count": self._counts[key],
                "sum": self._sums[key],
            }
        return out


def _num(value: float) -> str:
    """Render a metric value without a trailing ``.0`` for whole numbers."""
    return str(int(value)) if float(value).is_integer() else repr(value)


class MetricsRegistry:
    """Holds the agent's metrics and renders them for scraping."""

    def __init__(self) -> None:
        self.requests_total = Counter(
            "agent_requests_total", "Total HTTP requests handled, by endpoint/method/status."
        )
        self.request_failures_total = Counter(
            "agent_request_failures_total", "HTTP requests that returned 5xx or raised."
        )
        self.request_latency_seconds = Summary(
            "agent_request_latency_seconds", "HTTP request latency in seconds, by endpoint."
        )
        self.diagnoses_total = Counter(
            "agent_diagnoses_total", "Incident diagnoses produced, by status/engine."
        )
        self.retrievals_total = Counter(
            "agent_retrievals_total", "Runbook retrieval operations performed."
        )
        self.retrieved_chunks_total = Counter(
            "agent_retrieved_chunks_total", "Runbook chunks returned by retrieval."
        )
        self.llm_calls_total = Counter(
            "agent_llm_calls_total", "Calls made to an optional LLM client."
        )
        self.llm_tokens_total = Counter(
            "agent_llm_tokens_total", "LLM tokens consumed (when the client reports usage)."
        )

    def _all(self) -> list[Counter | Summary]:
        return [
            self.requests_total,
            self.request_failures_total,
            self.request_latency_seconds,
            self.diagnoses_total,
            self.retrievals_total,
            self.retrieved_chunks_total,
            self.llm_calls_total,
            self.llm_tokens_total,
        ]

    def render(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        blocks = ["\n".join(metric.render()) for metric in self._all()]
        return "\n".join(blocks) + "\n"

    def snapshot(self) -> dict[str, object]:
        """Return a plain-dict view of all metrics (handy for tests/JSON)."""
        return {metric.name: metric.snapshot() for metric in self._all()}


# Process-wide registry. Imported wherever the agent needs to record a metric.
METRICS = MetricsRegistry()

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
