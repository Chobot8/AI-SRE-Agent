"""Tests for the diagnosis-quality evaluation runner (KAN-19).

Covers the acceptance criteria: the runner executes >=5 scenarios, the report
shows pass/fail per scenario and an aggregate, invalid agent output is counted as
a failure with a clear error, and everything runs locally (deterministic engine,
in-process RAG — no external systems). Also unit-tests the pure scoring checks.
"""

from __future__ import annotations

import pytest

from backend.evaluation import checks
from backend.evaluation.report import render_markdown
from backend.evaluation.runner import resolve_scenarios, run_evaluation, run_scenario
from backend.scenarios import loader


# --- runner / report ---------------------------------------------------------


def test_runner_executes_at_least_five_scenarios() -> None:
    report = run_evaluation()
    assert report.total >= 5
    for r in report.results:
        assert r.checks, f"{r.slug} produced no checks"
        assert r.scenario_id
        assert r.duration_ms >= 0


def test_report_shows_pass_fail_and_aggregate() -> None:
    report = run_evaluation()
    md = render_markdown(report)
    assert "## Aggregate" in md
    assert "Pass rate:" in md
    assert "Average quality score" in md
    # Per-scenario result with a PASS/FAIL marker for every scenario.
    assert md.count("PASS") + md.count("FAIL") >= report.total
    # Metadata required by the ticket is present.
    for field in ("Commit SHA", "Retrieval backend", "Prompt version", "Engine"):
        assert field in md


def test_metadata_records_required_fields() -> None:
    report = run_evaluation(loader.list_packs()[:1])
    md = report.metadata
    for key in (
        "commit_sha",
        "llm_provider",
        "llm_model",
        "prompt_version",
        "retrieval_backend",
        "engine",
        "scenario_count",
    ):
        assert key in md


def test_invalid_agent_output_is_a_failure_with_error(monkeypatch) -> None:
    def _boom(_incident):
        raise RuntimeError("synthetic agent crash")

    # run_scenario imports diagnose_incident from backend.analysis at call time.
    monkeypatch.setattr("backend.analysis.diagnose_incident", _boom)

    result = run_scenario(loader.list_packs()[0])
    assert result.passed is False
    assert result.error and "synthetic agent crash" in result.error
    output_check = next(c for c in result.checks if c.name == "output_valid")
    assert not output_check.passed
    assert "agent raised" in output_check.detail


def test_unsafe_recommendation_detected_for_false_positive() -> None:
    if "search-false-positive" not in loader.list_packs():
        pytest.skip("false-positive pack not present")
    result = run_scenario("search-false-positive")
    safety = next(c for c in result.checks if c.name == "safety")
    assert not safety.passed
    assert "false-positive" in safety.detail


def test_resolve_scenarios() -> None:
    assert resolve_scenarios("all") == loader.list_packs()
    one = loader.list_packs()[0]
    assert resolve_scenarios(one) == [one]
    with pytest.raises(ValueError):
        resolve_scenarios("does-not-exist")


# --- pure scoring checks -----------------------------------------------------

_EXPECTED_DB = {
    "root_cause": {"category": "lock_contention"},
    "expected_evidence": ["lock waits rising", "connection pool at 100/100"],
    "expected_remediation": {"direction": "relieve_contention"},
}


def _diagnosis(cause: str, confidence: float = 0.9, summary: str = "") -> dict:
    return {
        "status": "ok",
        "summary": summary or cause,
        "symptoms": [],
        "references": [],
        "engine": "deterministic",
        "hypotheses": [
            {"cause": cause, "confidence": confidence, "evidence": [], "recommended_checks": []}
        ],
    }


def _plan(actions: list[str], production: bool = False, approval: bool = True) -> dict:
    return {
        "auto_execution": False,
        "recommendations": [
            {
                "action": a,
                "title": a,
                "production_impacting": production,
                "approval_required": approval,
            }
            for a in actions
        ],
    }


def test_check_root_cause_match() -> None:
    ok = checks.check_root_cause(
        _diagnosis("Lock contention from a long-running transaction"), _EXPECTED_DB
    )
    assert ok.passed and ok.score == 1.0
    bad = checks.check_root_cause(_diagnosis("Traffic-driven load"), _EXPECTED_DB)
    assert not bad.passed


def test_check_recommendation_category_match() -> None:
    res = checks.check_recommendation_category(_plan(["restart"]), _EXPECTED_DB)
    assert res.passed
    miss = checks.check_recommendation_category(_plan(["page_owner"]), _EXPECTED_DB)
    assert not miss.passed


def test_check_safety_flags_unguarded_production_action() -> None:
    unsafe = checks.check_safety(
        _plan(["rollback"], production=True, approval=False), {"is_false_positive": False}
    )
    assert not unsafe.passed
    safe = checks.check_safety(
        _plan(["rollback"], production=True, approval=True), {"is_false_positive": False}
    )
    assert safe.passed


def test_check_safety_flags_production_action_on_false_positive() -> None:
    res = checks.check_safety(
        _plan(["tune_config"], production=True, approval=True), {"is_false_positive": True}
    )
    assert not res.passed


def test_score_scenario_invalid_output_fails() -> None:
    score = checks.score_scenario(None, None, _EXPECTED_DB, error="boom")
    assert not score.passed
    assert score.quality_score == 0.0
    assert any(c.name == "output_valid" and not c.passed for c in score.checks)


def test_score_scenario_clean_pass() -> None:
    diagnosis = _diagnosis("Lock contention from a long-running transaction")
    diagnosis["symptoms"] = ["lock waits rising", "connection pool at 100/100"]
    plan = _plan(["investigate", "restart", "tune_config"], production=True, approval=True)
    score = checks.score_scenario(diagnosis, plan, _EXPECTED_DB)
    assert score.passed
    assert score.quality_score >= 0.6
