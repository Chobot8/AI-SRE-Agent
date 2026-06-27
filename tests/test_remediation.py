"""Tests for remediation recommendations + safety guardrails (KAN-6)."""

import json

import pytest

from backend.remediation import (
    ActionCategory,
    AutoExecutionForbidden,
    execute,
    recommend_for,
)
from backend.remediation.policy import SAFE_CATEGORIES, is_destructive

# Minimal diagnosis fixtures (shape produced by KAN-5 IncidentDiagnosis.to_dict()).
def _diag(scenario: str) -> dict:
    return {
        "incident_id": f"INC-{scenario}",
        "service": "svc",
        "scenario": scenario,
        "hypotheses": [{"cause": "x", "evidence": ["metric rose 1->9", "log: boom"]}],
    }


SCENARIOS = ["high_latency", "error_rate_spike", "pod_crash_loop", "queue_backlog", "db_saturation"]


def test_every_recommendation_has_required_fields() -> None:
    """Acceptance: recommendations include action, rationale, evidence, risk, rollback."""
    for s in SCENARIOS:
        plan = recommend_for(_diag(s))
        assert plan.recommendations
        for r in plan.recommendations:
            assert isinstance(r.action, ActionCategory)
            assert r.rationale.strip()
            assert r.evidence            # grounded in the diagnosis
            assert r.risk.value in {"low", "medium", "high"}
            assert r.rollback_note.strip()


def test_destructive_actions_are_approval_required() -> None:
    """Acceptance: unsafe actions are flagged approval-required."""
    plan = recommend_for(_diag("db_saturation"))
    by_action = {r.action: r for r in plan.recommendations}
    # RESTART (kill transaction) and TUNE_CONFIG are destructive -> approval-required.
    assert by_action[ActionCategory.RESTART].approval_required is True
    assert by_action[ActionCategory.RESTART].production_impacting is True
    # INVESTIGATE is safe.
    assert by_action[ActionCategory.INVESTIGATE].approval_required is False


def test_rollback_is_approval_required() -> None:
    plan = recommend_for(_diag("error_rate_spike"))
    rollback = next(r for r in plan.recommendations if r.action is ActionCategory.ROLLBACK)
    assert rollback.approval_required is True
    assert rollback.risk.value == "high"


def test_safe_categories_never_require_approval() -> None:
    for s in SCENARIOS:
        for r in recommend_for(_diag(s)).recommendations:
            if r.action in SAFE_CATEGORIES:
                assert r.approval_required is False
            if r.approval_required:
                assert is_destructive(r.action)


def test_plan_declares_no_auto_execution() -> None:
    """Acceptance: the system never executes remediation automatically."""
    plan = recommend_for(_diag("high_latency"))
    data = json.loads(plan.to_json())
    assert data["auto_execution"] is False
    assert "advisory only" in plan.note.lower()
    for r in plan.recommendations:
        assert r.execution == "manual_only"


def test_execute_always_refuses() -> None:
    """Guardrail: any attempt to execute a remediation raises, never acts."""
    plan = recommend_for(_diag("db_saturation"))
    with pytest.raises(AutoExecutionForbidden):
        execute(plan.recommendations[0])


def test_output_is_machine_readable_and_renderable() -> None:
    plan = recommend_for(_diag("queue_backlog"))
    data = json.loads(plan.to_json())
    assert data["recommendations"][0]["action"]
    md = plan.to_markdown()
    assert "Remediation plan" in md and "approval-required" in md
