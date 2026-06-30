"""Tests for evaluation comparison, chart, and persistence mapping (KAN-20).

Pure / local: comparison and chart operate on report dicts/objects, and the
persistence row mapping is exercised without a database.
"""

from __future__ import annotations

from backend.evaluation import persistence
from backend.evaluation.chart import render_scores_svg
from backend.evaluation.compare import compare_reports, render_comparison_markdown
from backend.evaluation.runner import run_evaluation
from backend.scenarios import loader


def _report(scenarios: list[dict]) -> dict:
    passed = sum(1 for s in scenarios if s["passed"])
    total = len(scenarios)
    avg = sum(s["quality_score"] for s in scenarios) / total if total else 0.0
    return {
        "generated_at": "2026-06-30T00:00:00Z",
        "metadata": {"commit_sha": "abc123", "eval_version": "test"},
        "aggregate": {
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "average_score": round(avg, 3),
            "avg_top_confidence": 0.5,
        },
        "results": scenarios,
    }


def _scn(slug, passed, score, checks=None):
    return {
        "slug": slug,
        "passed": passed,
        "quality_score": score,
        "checks": checks or [],
    }


def test_compare_detects_regressions_and_improvements() -> None:
    base = _report([_scn("a", True, 0.9), _scn("b", False, 0.3)])
    cur = _report([_scn("a", False, 0.4), _scn("b", True, 0.8)])
    cmp = compare_reports(base, cur)
    assert cmp["regressions"] == ["a"]
    assert cmp["improvements"] == ["b"]
    by_slug = {r["slug"]: r for r in cmp["rows"]}
    assert by_slug["a"]["status"] == "regressed"
    assert by_slug["a"]["delta_score"] == -0.5
    assert by_slug["b"]["status"] == "improved"


def test_removed_passing_scenario_counts_as_regression() -> None:
    base = _report([_scn("a", True, 0.9), _scn("b", True, 0.8)])
    cur = _report([_scn("a", True, 0.9)])  # "b" was dropped
    cmp = compare_reports(base, cur)
    assert "b" in cmp["regressions"]
    by_slug = {r["slug"]: r for r in cmp["rows"]}
    assert by_slug["b"]["status"] == "removed"


def test_removed_failing_scenario_is_not_a_regression() -> None:
    base = _report([_scn("a", True, 0.9), _scn("b", False, 0.2)])
    cur = _report([_scn("a", True, 0.9)])  # dropping a failing scenario
    cmp = compare_reports(base, cur)
    assert cmp["regressions"] == []


def test_compare_no_change() -> None:
    base = _report([_scn("a", True, 0.9)])
    cmp = compare_reports(base, base)
    assert cmp["regressions"] == []
    assert cmp["improvements"] == []
    assert cmp["pass_rate_delta"] == 0.0


def test_render_comparison_markdown_has_sections() -> None:
    base = _report([_scn("a", True, 0.9), _scn("b", True, 0.7)])
    cur = _report([_scn("a", True, 0.9), _scn("b", False, 0.2)])
    md = render_comparison_markdown(compare_reports(base, cur))
    assert "Regression notes" in md
    assert "Per-scenario" in md
    assert "Metric summary" in md
    assert "Regressions" in md  # b regressed
    assert "`b`" in md


def test_metric_summary_counts_check_passes() -> None:
    checks = [
        {"name": "root_cause_match", "applicable": True, "passed": True},
        {"name": "safety", "applicable": True, "passed": False},
    ]
    base = _report([_scn("a", True, 0.9, checks)])
    cmp = compare_reports(base, base)
    ms = cmp["metric_summary"]["current"]
    assert ms["root_cause_match"] == {"applicable": 1, "passed": 1}
    assert ms["safety"] == {"applicable": 1, "passed": 0}


def test_render_scores_svg() -> None:
    report = run_evaluation(loader.list_packs()[:2])
    svg = render_scores_svg(report)
    assert svg.lstrip().startswith("<svg")
    assert "</svg>" in svg
    assert "diagnosis quality" in svg
    for r in report.results:
        assert r.slug in svg


def test_persistence_result_rows_mapping() -> None:
    report = run_evaluation(loader.list_packs()[:1])
    rows = persistence._result_rows(report)
    assert len(rows) == 1
    row = rows[0]
    for key in (
        "scenario",
        "expected_category",
        "predicted_category",
        "predicted_top_cause",
        "top_confidence",
        "passed",
        "details",
    ):
        assert key in row
    assert row["scenario"] == report.results[0].slug
    assert isinstance(row["details"], dict)


def test_persistence_disabled_without_database(monkeypatch) -> None:
    import types

    # Patch settings (not just os.environ) so a local .env can't flip the result.
    monkeypatch.setattr(
        "backend.config.get_settings",
        lambda: types.SimpleNamespace(database_url=None),
    )
    assert persistence.persistence_enabled() is False
    report = run_evaluation(loader.list_packs()[:1])
    assert persistence.persist_report(report) is None
