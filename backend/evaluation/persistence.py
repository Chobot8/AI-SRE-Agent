"""Persist evaluation runs + per-scenario results to PostgreSQL (KAN-20)."""

from __future__ import annotations

from typing import Any

DEFAULT_ORG_SLUG = "local"
DEFAULT_ORG_NAME = "Local Dev"


def persistence_enabled() -> bool:
    """True when a database is configured (via settings, which also loads .env)."""
    from backend.config import get_settings

    return bool(get_settings().database_url)


def _result_rows(report: Any) -> list[dict[str, Any]]:
    from backend.scenarios import loader

    rows: list[dict[str, Any]] = []
    for r in report.results:
        try:
            expected = loader.load_pack(r.slug)["expected"] or {}
        except Exception:
            expected = {}
        root = expected.get("root_cause") or {}
        runbooks = expected.get("runbook_references") or []
        rc = r.check("root_cause_match")
        rc_match = bool(rc.passed) if (rc and rc.applicable) else None
        summary = (root.get("summary") or "").strip()
        rows.append(
            {
                "scenario": r.slug,
                "expected_category": root.get("category"),
                "expected_top_cause": (summary[:1000] or None),
                "expected_runbook": runbooks[0] if runbooks else None,
                "predicted_category": r.agent_scenario,
                "predicted_top_cause": r.predicted_top_cause or None,
                "top_confidence": round(r.top_confidence, 3),
                "category_match": rc_match,
                "cause_match": rc_match,
                "runbook_match": None,
                "passed": r.passed,
                "details": r.to_dict(),
            }
        )
    return rows


def persist_report(report: Any) -> str | None:
    if not persistence_enabled():
        return None

    from backend.db.repositories.entities import (
        EvaluationResultRepository,
        EvaluationRunRepository,
        OrganizationRepository,
    )
    from backend.db.session import session_scope

    md = report.metadata
    git_sha = md.get("commit_sha")
    if git_sha == "unknown":
        git_sha = None

    with session_scope() as session:
        org = OrganizationRepository(session).ensure(DEFAULT_ORG_SLUG, DEFAULT_ORG_NAME)
        session.flush()
        run = EvaluationRunRepository(session).add(
            org_id=org.id,
            baseline_version=md.get("eval_version", "eval"),
            engine="llm" if md.get("llm_invoked") else "deterministic",
            model_provider=md.get("llm_provider"),
            model_name=md.get("llm_model"),
            prompt_version=md.get("prompt_version"),
            git_sha=git_sha,
            total_scenarios=report.total,
            passed=report.passed_count,
            failed=report.total - report.passed_count,
            pass_rate=round(report.pass_rate, 4),
            avg_top_confidence=round(report.avg_top_confidence, 3),
            status="completed",
            notes="evaluation runner (KAN-19/20)",
        )
        session.flush()
        results_repo = EvaluationResultRepository(session)
        for row in _result_rows(report):
            results_repo.add(org_id=org.id, evaluation_run_id=run.id, **row)
        return str(run.id)
