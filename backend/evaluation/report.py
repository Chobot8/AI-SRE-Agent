"""Human-readable evaluation report (KAN-19/20)."""

from __future__ import annotations

from backend.evaluation.runner import ScenarioResult


def _status(passed: bool) -> str:
    return "PASS ✅" if passed else "FAIL ❌"


def _check_line(check) -> str:
    if not check.applicable:
        mark = "n/a ⚪"
    else:
        mark = "pass ✅" if check.passed else "fail ❌"
    weight = f", w={check.weight}" if check.weight else ""
    return f"  - **{check.name}** — {mark} (score {check.score:.2f}{weight}): {check.detail}"


def _agg_check(results, name):
    passed = applicable = 0
    score_sum = 0.0
    for r in results:
        c = r.check(name)
        if c and c.applicable:
            applicable += 1
            score_sum += c.score
            if c.passed:
                passed += 1
    avg = score_sum / applicable if applicable else 0.0
    return passed, applicable, avg


def _failing(results, name):
    out = []
    for r in results:
        c = r.check(name)
        if c and c.applicable and not c.passed:
            out.append(r.slug)
    return out


def _scenario_section(result: ScenarioResult) -> str:
    lines = [
        f"### {result.slug} — {_status(result.passed)}",
        "",
        f"- scenario id: `{result.scenario_id}`  ·  agent scenario: `{result.agent_scenario}`",
        f"- quality score: **{result.quality_score:.2f}**  ·  duration: {result.duration_ms} ms"
        f"  ·  engine: {result.engine}  ·  llm calls: {result.llm_calls}"
        f"  ·  retrieval calls: {result.retrieval_calls}",
    ]
    if result.error:
        lines.append(f"- **error:** {result.error}")
    lines.append("")
    lines.append("Checks:")
    for check in result.checks:
        lines.append(_check_line(check))
    lines.append("")
    return "\n".join(lines)


def _breakdown(report):
    results = report.results
    rc_p, rc_a, _ = _agg_check(results, "root_cause_match")
    rec_p, rec_a, _ = _agg_check(results, "recommendation_category_match")
    ev_p, ev_a, ev_avg = _agg_check(results, "evidence_coverage")
    mi_p, mi_a, _ = _agg_check(results, "missing_information_handling")
    unsafe = _failing(results, "safety")
    invalid = _failing(results, "output_valid")
    return [
        "## Quality breakdown",
        "",
        f"- **Root-cause accuracy:** {rc_p}/{rc_a} scenarios",
        f"- **Recommendation-category match:** {rec_p}/{rec_a} scenarios",
        f"- **Evidence coverage:** {ev_avg:.2f} average ({ev_p}/{ev_a} ≥ 50%)",
        f"- **Missing-information handling:** {mi_p}/{mi_a} scenarios",
        f"- **Unsafe-recommendation failures:** {len(unsafe)}"
        + (f" ({', '.join(unsafe)})" if unsafe else ""),
        f"- **Schema/output-validity failures:** {len(invalid)}"
        + (f" ({', '.join(invalid)})" if invalid else ""),
        "",
    ]


def render_markdown(report, *, comparison_md=None, chart_path=None) -> str:
    md = report.metadata
    lines = [
        "# AI SRE Agent — Diagnosis Quality Evaluation",
        "",
        f"_Generated: {report.generated_at}_",
        "",
        "## Run metadata",
        "",
        "| Field | Value |",
        "| ----- | ----- |",
        f"| Eval version | {md.get('eval_version')} |",
        f"| Commit SHA | `{md.get('commit_sha')}` |",
        f"| Engine | {md.get('engine')} |",
        f"| LLM provider / model | {md.get('llm_provider')} / {md.get('llm_model')} |",
        f"| LLM invoked | {md.get('llm_invoked')} |",
        f"| Prompt version | {md.get('prompt_version')} |",
        f"| Retrieval backend | {md.get('retrieval_backend')} |",
        f"| Scenarios | {md.get('scenario_count')} |",
        "",
    ]
    if chart_path:
        lines += [f"![Diagnosis quality scores]({chart_path})", ""]
    lines += [
        "## Aggregate",
        "",
        f"- **Pass rate:** {report.passed_count}/{report.total} ({report.pass_rate * 100:.0f}%)",
        f"- **Average quality score:** {report.average_score:.2f}",
        f"- **Average top-hypothesis confidence:** {report.avg_top_confidence:.2f}",
        f"- **Total duration:** {report.total_duration_ms} ms",
        "",
    ]
    lines += _breakdown(report)
    lines += [
        "## Results",
        "",
        "| Scenario | Agent scenario | Result | Score | Duration | LLM | Retrieval |",
        "| -------- | -------------- | ------ | ----- | -------- | --- | --------- |",
    ]
    for r in report.results:
        lines.append(
            f"| {r.slug} | {r.agent_scenario} | {_status(r.passed)} | "
            f"{r.quality_score:.2f} | {r.duration_ms} ms | {r.llm_calls} | {r.retrieval_calls} |"
        )
    lines += [
        "",
        "> Pass requires valid output (gate) **and** no unsafe recommendations "
        "(gate) **and** a weighted quality score ≥ 0.60 over the applicable "
        "checks. Invalid agent output fails outright with the error shown.",
        "",
    ]
    if comparison_md:
        lines += [comparison_md.rstrip(), ""]
    lines += ["## Per-scenario detail", ""]
    for r in report.results:
        lines.append(_scenario_section(r))
    return "\n".join(lines).rstrip() + "\n"
