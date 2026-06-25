"""Symptom detectors (KAN-5).

Deterministic signal extraction from a normalized incident dict. Produces a set
of canonical signal tokens plus an evidence string per token (with real numbers),
which the cause knowledge base matches against. Pure stdlib.
"""

from __future__ import annotations

# Canonical signal tokens -> short human description (for the symptoms list).
SIGNAL_DESCRIPTIONS: dict[str, str] = {
    "latency_rising": "Request latency is rising",
    "dependency_latency_rising": "Downstream dependency latency is rising",
    "throughput_flat": "Throughput is flat (not a traffic surge)",
    "throughput_rising": "Throughput is rising (increased load)",
    "errors_rising": "Error rate is rising",
    "deploy_recent": "A deployment occurred just before the incident",
    "memory_pressure": "Memory usage is at/near its limit",
    "restarts_rising": "Container restart count is climbing",
    "lag_rising": "Queue/consumer lag is rising",
    "consume_collapsed": "Consumer throughput has collapsed",
    "produce_steady": "Producer/ingest rate is steady",
    "connections_high": "Database connections are near the pool maximum",
    "lockwaits_rising": "Database lock-wait events are spiking",
    "cpu_high": "CPU utilization is high",
    "log_oom": "Logs show an OOMKilled / out-of-memory termination",
    "log_slow_query": "Logs show a slow or unindexed query",
    "log_timeout": "Logs show downstream timeouts",
    "log_pool_exhausted": "Logs show connection-pool exhaustion",
    "log_exception": "Logs show an unhandled exception",
    "log_lock": "Logs show a long-running transaction holding a lock",
    "log_crashloop": "Logs show repeated container restarts (back-off)",
    "log_workers_blocked": "Logs show the worker pool blocked on a downstream call",
    "log_deploy": "Logs show a new version starting",
}


def _trend(values: list[float]) -> str:
    if len(values) < 2:
        return "flat"
    first, last = values[0], values[-1]
    if first == 0:
        return "rising" if last > 0 else "flat"
    ratio = last / first
    if ratio >= 1.2 and last > first:
        return "rising"
    if ratio <= 0.8 and last < first:
        return "falling"
    return "flat"


def _metric_signals(metrics: list[dict]) -> tuple[set[str], dict[str, str]]:
    signals: set[str] = set()
    evidence: dict[str, str] = {}

    def add(token: str, detail: str) -> None:
        signals.add(token)
        evidence.setdefault(token, detail)

    for m in metrics:
        name = str(m.get("name", "")).lower()
        unit = str(m.get("unit", ""))
        values = [p.get("value") for p in m.get("points", []) if "value" in p]
        if not values:
            continue
        direction = _trend(values)
        detail = f"{m.get('name')} {values[0]}→{values[-1]} {unit} ({direction})"

        if ("latency" in name or "duration" in name):
            if any(k in name for k in ("db", "query", "dependency", "downstream")):
                if direction == "rising":
                    add("dependency_latency_rising", detail)
            elif direction == "rising":
                add("latency_rising", detail)
        if "request" in name and ("second" in name or unit == "rps"):
            add("throughput_rising" if direction == "rising" else "throughput_flat", detail)
        if "5xx" in name or "error" in name:
            if direction == "rising":
                add("errors_rising", detail)
        if "deploy" in name and any(v >= 1 for v in values):
            add("deploy_recent", detail)
        if "memory" in name and values[-1] == max(values):
            add("memory_pressure", detail)
        if "restart" in name and direction == "rising":
            add("restarts_rising", detail)
        if "lag" in name and direction == "rising":
            add("lag_rising", detail)
        if "consumed" in name and direction == "falling":
            add("consume_collapsed", detail)
        if "produced" in name and direction == "flat":
            add("produce_steady", detail)
        if "connection" in name and (direction == "rising" or values[-1] >= 90):
            add("connections_high", detail)
        if "lock" in name and direction == "rising":
            add("lockwaits_rising", detail)
        if "cpu" in name and values[-1] >= 85:
            add("cpu_high", detail)
    return signals, evidence


# Log keyword -> signal token.
_LOG_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("oomkilled", "out of memory", "exceeded memory limit"), "log_oom"),
    (("slow query", "missing index", "no index"), "log_slow_query"),
    (("timeout", "timed out"), "log_timeout"),
    (("pool exhausted", "could not get db connection", "connection from pool"), "log_pool_exhausted"),
    (("nullpointerexception", "unhandled exception", "internal server error", "traceback"), "log_exception"),
    (("long-running transaction", "holding lock", "lock wait"), "log_lock"),
    (("crashloopbackoff", "back-off restarting"), "log_crashloop"),
    (("workers waiting", "worker pool blocked", "all 8 workers"), "log_workers_blocked"),
    (("starting", "previous v"), "log_deploy"),
]


def _log_signals(logs: list[dict]) -> tuple[set[str], dict[str, str]]:
    signals: set[str] = set()
    evidence: dict[str, str] = {}
    for entry in logs:
        msg = str(entry.get("message", ""))
        low = msg.lower()
        for keywords, token in _LOG_KEYWORDS:
            if any(k in low for k in keywords):
                signals.add(token)
                evidence.setdefault(token, f"log [{entry.get('level','')}]: {msg}")
    return signals, evidence


def detect(incident: dict) -> tuple[set[str], dict[str, str]]:
    """Return (signals, evidence_by_signal) detected in the incident."""
    m_sig, m_ev = _metric_signals(incident.get("metrics", []) or [])
    l_sig, l_ev = _log_signals(incident.get("logs", []) or [])
    evidence = {**m_ev, **l_ev}
    return (m_sig | l_sig), evidence


def symptoms_from_signals(signals: set[str], evidence: dict[str, str]) -> list[str]:
    """Human-readable symptom lines, preferring evidence with real numbers."""
    out: list[str] = []
    for token in sorted(signals):
        desc = SIGNAL_DESCRIPTIONS.get(token, token)
        ev = evidence.get(token)
        out.append(f"{desc} ({ev})" if ev else desc)
    return out
