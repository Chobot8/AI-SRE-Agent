"""Human-readable evaluation report (KAN-19).

Renders an :class:`EvaluationReport` as Markdown: run metadata, an aggregate
summary, a per-scenario results table, and per-scenario check details (including
clear error details for invalid output).
"""

from __future__ import annotations

from backend.evaluation.runner import EvaluationReport, ScenarioResult


def _status(passed: bool) -> str:
    return "PASS ✅" if passed else "FAIL ❌"


def _check_line(check) -> str:
    if not check.applicable:
        mark = "n/a ⚪"
    else:
        mark = "pass ✅" if check.passed else "fail ❌"
    weight = f", w={check.weight}" if check.weight else ""
    return f"  - **{check.name}** — {mark} (score {check.score:.2f}{weight}): {check.detail}"


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


def render_markdown(report: EvaluationReport) -> str:
    md = report.metadata
    agg_pass = report.passed_count
    lines: list[str] = [
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
        "## Aggregate",
        "",
        f"- **Pass rate:** {agg_pass}/{report.total} ({report.pass_rate * 100:.0f}%)",
        f"- **Average quality score:** {report.average_score:.2f}",
        f"- **Total duration:** {report.total_duration_ms} ms",
        "",
        "## Results",
        "",
        "| Scenario | Agent scenario | Result | Score | Duration | LLM | Retrieval |",
        "| -------- | -------------- | ------ | ----- | -------- | --- | --------- |",
    ]
    for r in report.results:
        lines.append(
            f"| {r.slug} | {r.agent_scenario} | {_status(r.passed)} | "
            f"{r.quality_score:.2f} | {r.duration_ms} ms | {r.llm_calls} | "
            f"{r.retrieval_calls} |"
        )
    lines += [
        "",
        "> Pass requires valid output (gate) **and** no unsafe recommendations "
        "(gate) **and** a weighted quality score ≥ 0.60 over the applicable "
        "checks. Invalid agent output fails outright with the error shown.",
        "",
        "## Per-scenario detail",
        "",
    ]
    for r in report.results:
        lines.append(_scenario_section(r))
    return "\n".join(lines).rstrip() + "\n"
