"""Automated evaluation of incident-diagnosis quality (KAN-19/20)."""

from __future__ import annotations

from backend.evaluation.chart import render_scores_svg
from backend.evaluation.checks import CheckResult, ScenarioScore, score_scenario
from backend.evaluation.compare import compare_reports, render_comparison_markdown
from backend.evaluation.persistence import persist_report, persistence_enabled
from backend.evaluation.report import render_markdown
from backend.evaluation.runner import (
    EvaluationReport,
    ScenarioResult,
    resolve_scenarios,
    run_evaluation,
    run_scenario,
)

__all__ = [
    "CheckResult",
    "ScenarioScore",
    "score_scenario",
    "render_markdown",
    "render_scores_svg",
    "compare_reports",
    "render_comparison_markdown",
    "persist_report",
    "persistence_enabled",
    "EvaluationReport",
    "ScenarioResult",
    "run_evaluation",
    "run_scenario",
    "resolve_scenarios",
]
