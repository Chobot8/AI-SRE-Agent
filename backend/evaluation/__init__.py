"""Automated evaluation of incident-diagnosis quality (KAN-19).

Runs scenario packs (KAN-18) through the agent, scores each with deterministic
checks (root-cause match, evidence coverage, recommendation-category match,
unsafe-recommendation detection, missing-information handling, output validity),
and renders a human-readable report. Fully local and deterministic for the MVP.

CLI:  ``python -m backend.evaluation --scenario all --output reports/eval-latest.md``
"""

from __future__ import annotations

from backend.evaluation.checks import CheckResult, ScenarioScore, score_scenario
from backend.evaluation.report import render_markdown
from backend.evaluation.runner import (
    EvaluationReport,
    ScenarioResult,
    run_evaluation,
    run_scenario,
    resolve_scenarios,
)

__all__ = [
    "CheckResult",
    "ScenarioScore",
    "score_scenario",
    "render_markdown",
    "EvaluationReport",
    "ScenarioResult",
    "run_evaluation",
    "run_scenario",
    "resolve_scenarios",
]
