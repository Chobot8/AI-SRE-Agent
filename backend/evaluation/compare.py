"""Compare two evaluation runs and render regression notes (KAN-20)."""

from __future__ import annotations

from typing import Any

_METRIC_CHECKS = [
    ("Root-cause accuracy", "root_cause_match"),
    ("Evidence coverage", "evidence_coverage"),
    ("Recommendation-category match", "recommendation_category_match"),
    ("Missing-information handling", "missing_information_handling"),
    ("Safety (no unsafe rec.)", "safety"),
    ("Schema/output validity", "output_valid"),
]


def _metric_counts(results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for r in results:
        for c in r.get("checks", []):
            name = c.get("name")
            bucket = counts.setdefault(name, {"applicable": 0, "passed": 0})
            if c.get("applicable"):
                bucket["applicable"] += 1
                if c.get("passed"):
                    bucket["passed"] += 1
    return counts


def compare_reports(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    b_results = {r["slug"]: r for r in baseline.get("results", [])}
    c_results = {r["slug"]: r for r in current.get("results", [])}
    slugs = sorted(set(b_results) | set(c_results))

    rows: list[dict[str, Any]] = []
    regressions: list[str] = []
    improvements: list[str] = []
    for slug in slugs:
        b = b_results.get(slug)
        c = c_results.get(slug)
        b_score = b["quality_score"] if b else None
        c_score = c["quality_score"] if c else None
        delta = (
            round(c_score - b_score, 3)
            if (b_score is not None and c_score is not None)
            else None
        )
        if b is None:
            status = "new"
        elif c is None:
            status = "removed"
            if b["passed"]:
                regressions.append(slug)
        elif b["passed"] and not c["passed"]:
            status = "regressed"
            regressions.append(slug)
        elif (not b["passed"]) and c["passed"]:
            status = "improved"
            improvements.append(slug)
        else:
            status = "unchanged"
        rows.append(
            {
                "slug": slug,
                "baseline_passed": b["passed"] if b else None,
                "current_passed": c["passed"] if c else None,
                "baseline_score": b_score,
                "current_score": c_score,
                "delta_score": delta,
                "status": status,
            }
        )

    b_agg = baseline.get("aggregate", {})
    c_agg = current.get("aggregate", {})

    def _delta(key: str):
        bv, cv = b_agg.get(key), c_agg.get(key)
        if bv is None or cv is None:
            return None
        return round(cv - bv, 3)

    return {
        "baseline": {
            "generated_at": baseline.get("generated_at"),
            "commit_sha": baseline.get("metadata", {}).get("commit_sha"),
            "eval_version": baseline.get("metadata", {}).get("eval_version"),
            "aggregate": b_agg,
        },
        "current": {
            "generated_at": current.get("generated_at"),
            "commit_sha": current.get("metadata", {}).get("commit_sha"),
            "eval_version": current.get("metadata", {}).get("eval_version"),
            "aggregate": c_agg,
        },
        "rows": rows,
        "regressions": regressions,
        "improvements": improvements,
        "pass_rate_delta": _delta("pass_rate"),
        "average_score_delta": _delta("average_score"),
        "avg_top_confidence_delta": _delta("avg_top_confidence"),
        "metric_summary": {
            "baseline": _metric_counts(baseline.get("results", [])),
            "current": _metric_counts(current.get("results", [])),
        },
    }


def _fmt_delta(v, *, pct: bool = False) -> str:
    if v is None:
        return "—"
    scaled = v * 100 if pct else v
    sign = "+" if scaled >= 0 else ""
    return f"{sign}{scaled:.0f}%" if pct else f"{sign}{scaled:.2f}"


def _pf(passed) -> str:
    if passed is None:
        return "—"
    return "PASS ✅" if passed else "FAIL ❌"


def render_comparison_markdown(cmp: dict[str, Any], *, standalone: bool = True) -> str:
    h = "#" if standalone else "##"
    b, c = cmp["baseline"], cmp["current"]
    ba, ca = b["aggregate"], c["aggregate"]
    lines: list[str] = []
    if standalone:
        lines += ["# Evaluation comparison", ""]
    else:
        lines += ["## Comparison vs baseline", ""]

    b_id = f"`{b.get('commit_sha')}` ({b.get('eval_version')}, {b.get('generated_at')})"
    c_id = f"`{c.get('commit_sha')}` ({c.get('eval_version')}, {c.get('generated_at')})"
    lines += [
        f"- **Baseline:** {b_id}",
        f"- **Current:** {c_id}",
        "",
        f"{h}# Aggregate change",
        "",
        "| Metric | Baseline | Current | Δ |",
        "| ------ | -------- | ------- | - |",
        f"| Pass rate | {ba.get('pass_rate', 0) * 100:.0f}% | "
        f"{ca.get('pass_rate', 0) * 100:.0f}% | {_fmt_delta(cmp['pass_rate_delta'], pct=True)} |",
        f"| Average score | {ba.get('average_score', 0):.2f} | "
        f"{ca.get('average_score', 0):.2f} | {_fmt_delta(cmp['average_score_delta'])} |",
        f"| Avg top confidence | {ba.get('avg_top_confidence', 0):.2f} | "
        f"{ca.get('avg_top_confidence', 0):.2f} | {_fmt_delta(cmp['avg_top_confidence_delta'])} |",
        "",
        f"{h}# Regression notes",
        "",
    ]
    if cmp["regressions"]:
        lines.append("⚠️ **Regressions** (passed on baseline, now failing or dropped):")
        lines += [f"- `{s}`" for s in cmp["regressions"]]
    else:
        lines.append("✅ No regressions vs baseline.")
    if cmp["improvements"]:
        lines.append("")
        lines.append("🎉 **Improvements** (failed on baseline, now passing):")
        lines += [f"- `{s}`" for s in cmp["improvements"]]
    lines += [
        "",
        f"{h}# Per-scenario",
        "",
        "| Scenario | Baseline | Current | Δ score | Status |",
        "| -------- | -------- | ------- | ------- | ------ |",
    ]
    for row in cmp["rows"]:
        lines.append(
            f"| {row['slug']} | {_pf(row['baseline_passed'])} | {_pf(row['current_passed'])} | "
            f"{_fmt_delta(row['delta_score'])} | {row['status']} |"
        )

    lines += [
        "",
        f"{h}# Metric summary",
        "",
        "| Metric | Baseline | Current |",
        "| ------ | -------- | ------- |",
    ]
    bm = cmp["metric_summary"]["baseline"]
    cm = cmp["metric_summary"]["current"]
    for label, name in _METRIC_CHECKS:
        bcell = bm.get(name, {"passed": 0, "applicable": 0})
        ccell = cm.get(name, {"passed": 0, "applicable": 0})
        lines.append(
            f"| {label} | {bcell['passed']}/{bcell['applicable']} | "
            f"{ccell['passed']}/{ccell['applicable']} |"
        )
    return "\n".join(lines).rstrip() + "\n"
