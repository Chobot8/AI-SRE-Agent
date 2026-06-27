"""Remediation advisor (KAN-6).

Maps a KAN-5 incident diagnosis to a ranked, guardrailed remediation plan. Each
recommendation's risk and approval requirement come from the central policy
(policy.py), not from the templates — so guardrails are applied uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.remediation.models import (
    ActionCategory,
    Recommendation,
    RemediationPlan,
)
from backend.remediation.policy import policy_for


@dataclass
class ActionTemplate:
    category: ActionCategory
    title: str
    rationale: str
    rollback_note: str = "N/A — non-mutating action."


# Per-scenario suggested actions, ordered operationally:
# investigate first, then the targeted fix, then notify / follow up.
ACTION_TEMPLATES: dict[str, list[ActionTemplate]] = {
    "high_latency": [
        ActionTemplate(
            ActionCategory.INVESTIGATE,
            "Confirm the slow downstream query",
            "Latency rises with dependency latency while traffic is flat — inspect the "
            "slow/unindexed query before changing anything.",
        ),
        ActionTemplate(
            ActionCategory.TUNE_CONFIG,
            "Add the missing index / optimize the query",
            "A missing index on the hot query is the leading cause of the p99 breach.",
            "Indexes can be dropped; build concurrently to avoid locking.",
        ),
        ActionTemplate(
            ActionCategory.PAGE_OWNER,
            "Page the service owner if SLO stays breached",
            "p99 over SLO for a sustained window warrants owner involvement.",
        ),
    ],
    "error_rate_spike": [
        ActionTemplate(
            ActionCategory.INVESTIGATE,
            "Confirm the error onset aligns with the deploy",
            "5xx jumped right after the rollout — verify the regression before rolling back.",
        ),
        ActionTemplate(
            ActionCategory.ROLLBACK,
            "Roll back to the previous known-good release",
            "A release regression is the leading cause; rollback is the fastest "
            "reversible mitigation.",
            "Re-deploy the previous version; keep the bad build for post-incident analysis.",
        ),
        ActionTemplate(
            ActionCategory.PAGE_OWNER,
            "Page the on-call owner",
            "A critical error-rate breach needs an owner engaged immediately.",
        ),
    ],
    "pod_crash_loop": [
        ActionTemplate(
            ActionCategory.INVESTIGATE,
            "Confirm OOMKilled as the termination reason",
            "Memory hits the limit before each restart — confirm OOM before changing limits.",
        ),
        ActionTemplate(
            ActionCategory.TUNE_CONFIG,
            "Raise the memory limit or lazy-load startup data",
            "The container exceeds its memory limit at startup; more headroom or "
            "streaming the data stops the loop.",
            "Revert the limit/manifest change if it does not resolve the loop.",
        ),
        ActionTemplate(
            ActionCategory.OPEN_TICKET,
            "Open a follow-up to fix startup memory usage",
            "Raising the limit is a mitigation; the startup memory pattern should be "
            "fixed properly.",
        ),
    ],
    "queue_backlog": [
        ActionTemplate(
            ActionCategory.INVESTIGATE,
            "Check the blocking downstream dependency",
            "Consume rate collapsed while ingest held steady — workers are blocked on a "
            "downstream call.",
        ),
        ActionTemplate(
            ActionCategory.TUNE_CONFIG,
            "Shorten downstream timeouts and add a dead-letter queue",
            "Long downstream timeouts block the worker pool; a DLQ prevents poison "
            "messages from stalling it.",
            "Restore prior timeout/DLQ settings if behaviour regresses.",
        ),
        ActionTemplate(
            ActionCategory.SCALE,
            "Scale out consumers once the dependency is healthy",
            "Extra consumers drain the backlog after the blocking dependency recovers.",
            "Scale back to the baseline replica count after the backlog clears.",
        ),
    ],
    "db_saturation": [
        ActionTemplate(
            ActionCategory.INVESTIGATE,
            "Identify the blocking long-running transaction",
            "Lock waits spike and connections hit the pool max — find the transaction "
            "holding the lock.",
        ),
        ActionTemplate(
            ActionCategory.RESTART,
            "Terminate the blocking transaction",
            "Killing the long-running transaction releases the lock and relieves saturation.",
            "Terminated work may need to be retried by the owning service; coordinate "
            "before killing.",
        ),
        ActionTemplate(
            ActionCategory.TUNE_CONFIG,
            "Add statement/lock timeouts",
            "Statement timeouts prevent any single transaction from holding locks indefinitely.",
            "Revert the timeout settings if they cause unexpected query failures.",
        ),
    ],
}

_GENERIC = [
    ActionTemplate(
        ActionCategory.INVESTIGATE,
        "Investigate the alert and recent changes",
        "No dominant cause matched; review metrics, logs, and recent deploys/config.",
    ),
    ActionTemplate(
        ActionCategory.PAGE_OWNER,
        "Page the service owner",
        "Engage the owner when the cause is unclear.",
    ),
    ActionTemplate(
        ActionCategory.OPEN_TICKET,
        "Open a follow-up ticket",
        "Track investigation if the incident is not immediately resolved.",
    ),
]


def _as_dict(diagnosis) -> dict:
    """Accept either an IncidentDiagnosis (KAN-5) or a plain dict."""
    return diagnosis.to_dict() if hasattr(diagnosis, "to_dict") else dict(diagnosis)


class RemediationAdvisor:
    """Turns a diagnosis into a guardrailed remediation plan."""

    def recommend(self, diagnosis) -> RemediationPlan:
        d = _as_dict(diagnosis)
        scenario = str(d.get("scenario", "unknown"))
        hypotheses = d.get("hypotheses") or []
        top = hypotheses[0] if hypotheses else {}
        # Evidence comes from the leading hypothesis (grounds each recommendation).
        evidence = list(top.get("evidence", []))[:3]

        templates = ACTION_TEMPLATES.get(scenario, _GENERIC)
        recs: list[Recommendation] = []
        for tpl in templates:
            pol = policy_for(tpl.category)
            recs.append(
                Recommendation(
                    action=tpl.category,
                    title=tpl.title,
                    rationale=tpl.rationale,
                    evidence=evidence,
                    risk=pol.risk,
                    rollback_note=tpl.rollback_note,
                    approval_required=pol.approval_required,
                    production_impacting=pol.production_impacting,
                )
            )

        return RemediationPlan(
            incident_id=str(d.get("incident_id", "unknown")),
            scenario=scenario,
            service=str(d.get("service", "unknown")),
            recommendations=recs,
        )


def recommend_for(diagnosis) -> RemediationPlan:
    """Convenience wrapper."""
    return RemediationAdvisor().recommend(diagnosis)
