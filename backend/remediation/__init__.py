"""Remediation recommendations with safety guardrails (KAN-6).

Advisory-only: the agent recommends operational actions (with evidence, risk,
rollback note, and approval flags) but never executes them in the MVP.
"""

from backend.remediation.models import (
    ActionCategory,
    Recommendation,
    RemediationPlan,
    RiskLevel,
)
from backend.remediation.policy import (
    AUTO_EXECUTION_ENABLED,
    AutoExecutionForbidden,
    execute,
    is_destructive,
    policy_for,
)
from backend.remediation.recommend import RemediationAdvisor, recommend_for

__all__ = [
    "ActionCategory",
    "RiskLevel",
    "Recommendation",
    "RemediationPlan",
    "RemediationAdvisor",
    "recommend_for",
    "policy_for",
    "is_destructive",
    "execute",
    "AutoExecutionForbidden",
    "AUTO_EXECUTION_ENABLED",
]
