"""Cause knowledge base (KAN-5).

Per-scenario candidate root causes, each with the signals that support it,
recommended diagnostic checks, and the information typically still missing. The
reasoning pipeline scores these against detected signals to rank hypotheses.

This is deterministic, reviewable domain knowledge — the same operational logic
the runbooks (KAN-4) describe, encoded for ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CauseTemplate:
    cause: str
    signals: list[str]                       # supporting signal tokens
    base_confidence: float                   # 0..1 when all signals present
    recommended_checks: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)


# scenario -> ordered candidate causes
CAUSE_TEMPLATES: dict[str, list[CauseTemplate]] = {
    "high_latency": [
        CauseTemplate(
            cause="Slow downstream dependency / unindexed query",
            signals=["dependency_latency_rising", "latency_rising", "throughput_flat", "log_slow_query"],
            base_confidence=0.9,
            recommended_checks=[
                "Inspect slow-query logs for the affected datastore",
                "EXPLAIN the suspect query and confirm a missing index",
                "Check the dependency's own latency/health on the same time range",
            ],
            missing_information=["Query execution plan", "Recent schema/index changes"],
        ),
        CauseTemplate(
            cause="Connection/thread-pool contention",
            signals=["log_timeout", "latency_rising"],
            base_confidence=0.55,
            recommended_checks=["Inspect connection-pool wait/acquire time", "Check pool size vs concurrency"],
            missing_information=["Pool utilization metrics"],
        ),
        CauseTemplate(
            cause="Traffic-driven load",
            signals=["throughput_rising", "latency_rising"],
            base_confidence=0.5,
            recommended_checks=["Correlate latency with request volume", "Check autoscaling status"],
            missing_information=["Capacity headroom"],
        ),
    ],
    "error_rate_spike": [
        CauseTemplate(
            cause="Bad release regression",
            signals=["errors_rising", "deploy_recent", "log_exception", "log_deploy"],
            base_confidence=0.9,
            recommended_checks=[
                "Roll back to the previous known-good version",
                "Diff the suspect release for the failing code path",
                "Confirm error onset aligns with the deploy marker",
            ],
            missing_information=["Exact offending commit", "Whether a feature flag changed"],
        ),
        CauseTemplate(
            cause="Downstream dependency failure",
            signals=["errors_rising", "log_timeout"],
            base_confidence=0.55,
            recommended_checks=["Check health of downstream services", "Inspect dependency error rates"],
            missing_information=["Downstream status"],
        ),
    ],
    "pod_crash_loop": [
        CauseTemplate(
            cause="OOMKilled (memory limit exceeded)",
            signals=["log_oom", "memory_pressure", "restarts_rising"],
            base_confidence=0.9,
            recommended_checks=[
                "kubectl describe pod and read the last termination reason",
                "Plot container memory against its limit around restarts",
                "Raise the memory limit or stream/lazy-load large startup data",
            ],
            missing_information=["Heap/allocation breakdown at startup"],
        ),
        CauseTemplate(
            cause="Failing readiness/liveness probe",
            signals=["restarts_rising", "log_crashloop"],
            base_confidence=0.5,
            recommended_checks=["Review probe thresholds vs startup time", "Check probe endpoint health"],
            missing_information=["Probe configuration"],
        ),
        CauseTemplate(
            cause="Startup config/migration failure",
            signals=["restarts_rising", "log_exception"],
            base_confidence=0.45,
            recommended_checks=["Inspect startup logs before the crash", "Verify config/secrets and migrations"],
            missing_information=["Recent config changes"],
        ),
    ],
    "queue_backlog": [
        CauseTemplate(
            cause="Stuck consumer on unresponsive downstream",
            signals=["consume_collapsed", "produce_steady", "lag_rising", "log_timeout", "log_workers_blocked"],
            base_confidence=0.9,
            recommended_checks=[
                "Check health of the blocking downstream dependency",
                "Shorten downstream timeouts and add a dead-letter queue",
                "Scale out consumers once the dependency is healthy",
            ],
            missing_information=["Downstream dependency status"],
        ),
        CauseTemplate(
            cause="Under-provisioned consumers",
            signals=["lag_rising", "consume_collapsed"],
            base_confidence=0.45,
            recommended_checks=["Compare sustained consume vs produce rate", "Check consumer CPU/replicas"],
            missing_information=["Consumer resource headroom"],
        ),
        CauseTemplate(
            cause="Poison message causing retries",
            signals=["lag_rising", "log_exception"],
            base_confidence=0.4,
            recommended_checks=["Look for a single message retried repeatedly", "Inspect the dead-letter queue"],
            missing_information=["Offending message payload"],
        ),
    ],
    "db_saturation": [
        CauseTemplate(
            cause="Lock contention from a long-running transaction",
            signals=["lockwaits_rising", "log_lock", "connections_high"],
            base_confidence=0.9,
            recommended_checks=[
                "List active transactions and the locks they hold (pg_stat_activity / SHOW PROCESSLIST)",
                "Terminate or commit the blocking transaction to release locks",
                "Add statement/lock timeouts to prevent indefinite holds",
            ],
            missing_information=["Blocking transaction/PID", "Application that opened it"],
        ),
        CauseTemplate(
            cause="Connection-pool exhaustion from slow queries",
            signals=["connections_high", "log_pool_exhausted"],
            base_confidence=0.6,
            recommended_checks=["Identify queries holding connections open", "Right-size the pool"],
            missing_information=["Per-query connection hold time"],
        ),
        CauseTemplate(
            cause="Load-driven saturation",
            signals=["connections_high", "cpu_high", "throughput_rising"],
            base_confidence=0.45,
            recommended_checks=["Correlate connections/CPU with traffic", "Consider read replicas or scaling"],
            missing_information=["Traffic trend vs baseline"],
        ),
    ],
}


# Generic fallback when the scenario is unknown or no template matches.
GENERIC_TEMPLATES: list[CauseTemplate] = [
    CauseTemplate(
        cause="Insufficient signal — manual investigation required",
        signals=[],
        base_confidence=0.2,
        recommended_checks=[
            "Review the alert and recent changes (deploys, config, traffic)",
            "Inspect service metrics and logs around the alert window",
        ],
        missing_information=["A clear dominant symptom in metrics/logs"],
    ),
]
