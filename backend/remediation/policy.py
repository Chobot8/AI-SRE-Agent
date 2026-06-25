"""Safety guardrails (KAN-6).

Central policy that (1) assigns a default risk level and approval requirement to
each action category, and (2) enforces that the MVP never auto-executes anything.

Separation of concerns: the advisor decides *what* to suggest; this policy decides
*how risky* it is and *whether a human must approve it* — so guardrails can't be
bypassed by a single recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.remediation.models import ActionCategory, RiskLevel

# Global kill-switch for the MVP. Auto-execution is not implemented; this constant
# documents and enforces that intent (see enforce_no_auto_execution / execute).
AUTO_EXECUTION_ENABLED = False


@dataclass(frozen=True)
class CategoryPolicy:
    risk: RiskLevel
    approval_required: bool
    production_impacting: bool


# Default guardrail per category. Destructive / production-impacting actions are
# approval-required; observational/notification actions are safe.
CATEGORY_POLICY: dict[ActionCategory, CategoryPolicy] = {
    ActionCategory.INVESTIGATE: CategoryPolicy(RiskLevel.low, False, False),
    ActionCategory.PAGE_OWNER:  CategoryPolicy(RiskLevel.low, False, False),
    ActionCategory.OPEN_TICKET: CategoryPolicy(RiskLevel.low, False, False),
    ActionCategory.SCALE:       CategoryPolicy(RiskLevel.medium, True, True),
    ActionCategory.TUNE_CONFIG: CategoryPolicy(RiskLevel.medium, True, True),
    ActionCategory.RESTART:     CategoryPolicy(RiskLevel.high, True, True),
    ActionCategory.ROLLBACK:    CategoryPolicy(RiskLevel.high, True, True),
}

# Categories considered safe (no approval, non-mutating or purely additive).
SAFE_CATEGORIES = {
    ActionCategory.INVESTIGATE,
    ActionCategory.PAGE_OWNER,
    ActionCategory.OPEN_TICKET,
}


def policy_for(category: ActionCategory) -> CategoryPolicy:
    """Return the guardrail policy for a category."""
    return CATEGORY_POLICY[category]


def is_destructive(category: ActionCategory) -> bool:
    """True if the action mutates production and must be approval-gated."""
    return CATEGORY_POLICY[category].approval_required


class AutoExecutionForbidden(RuntimeError):
    """Raised if anything attempts to auto-execute a remediation."""


def enforce_no_auto_execution() -> None:
    """Guard invoked anywhere execution might be attempted."""
    if AUTO_EXECUTION_ENABLED:  # pragma: no cover - constant is False in the MVP
        raise AutoExecutionForbidden(
            "Auto-execution is disabled in the MVP and must not be enabled."
        )


def execute(_recommendation) -> None:
    """Intentionally non-functional execution entry point.

    The MVP is advisory only. This exists so that any caller attempting to run a
    remediation fails loudly instead of silently acting on production.
    """
    enforce_no_auto_execution()
    raise AutoExecutionForbidden(
        "Remediation execution is not available: the agent only recommends "
        "actions for a human to review and perform."
    )
