"""CLI for the evaluation runner (KAN-19/20)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from backend.evaluation.chart import render_scores_svg
from backend.evaluation.compare import compare_reports, render_comparison_markdown
from backend.evaluation.persistence import persist_report, persistence_enabled
from backend.evaluation.report import render_markdown
from backend.evaluation.runner import resolve_scenarios, run_evaluation
from backend.scenarios import loader

_DEFAULT_OUTPUT = "reports/eval-latest.md"


def _write(path: str, content: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _cmd_compare(args: argparse.Namespace) -> int:
    base_path, cur_path = args.compare
    baseline = json.loads(Path(base_path).read_text(encoding="utf-8"))
    current = json.loads(Path(cur_path).read_text(encoding="utf-8"))
    cmp = compare_reports(baseline, current)
    out = args.output if args.output != _DEFAULT_OUTPUT else "reports/eval-comparison.md"
    p = _write(out, render_comparison_markdown(cmp, standalone=True))
    regressions = cmp["regressions"]
    print(
        f"Compared {base_path} -> {cur_path}: "
        f"{len(regressions)} regression(s), {len(cmp['improvements'])} improvement(s)."
    )
    print(f"Comparison written to {p}")
    if args.strict and regressions:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.evaluation")
    parser.add_argument("--scenario", default="all", help='"all" or comma-separated slugs.')
    parser.add_argument("--output", default=_DEFAULT_OUTPUT, help="Markdown report path.")
    parser.add_argument("--json", dest="json_output", default=None, help="Also write raw JSON.")
    parser.add_argument("--svg", default="reports/eval-scores.svg", help="SVG chart path.")
    parser.add_argument("--no-svg", action="store_true", help="Do not write the SVG chart.")
    parser.add_argument("--baseline", default=None, help="Baseline JSON to compare the run to.")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BASELINE_JSON", "CURRENT_JSON"),
        help="Compare two existing JSON reports and exit (no agent run).",
    )
    parser.add_argument("--no-persist", action="store_true", help="Skip PostgreSQL persistence.")
    parser.add_argument("--list", action="store_true", help="List scenario packs and exit.")
    parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero on failures/regressions."
    )
    args = parser.parse_args(argv)

    if args.list:
        for slug in loader.list_packs():
            print(slug)
        return 0

    if args.compare:
        return _cmd_compare(args)

    try:
        slugs = resolve_scenarios(args.scenario)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not slugs:
        print("error: no scenario packs found.", file=sys.stderr)
        return 2

    report = run_evaluation(slugs)
    report_dict = report.to_dict()

    chart_embed = None
    if not args.no_svg and args.svg:
        svg_path = _write(args.svg, render_scores_svg(report))
        chart_embed = os.path.relpath(svg_path, Path(args.output).parent)

    comparison_md = None
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        cmp = compare_reports(baseline, report_dict)
        comparison_md = render_comparison_markdown(cmp, standalone=False)

    markdown = render_markdown(report, comparison_md=comparison_md, chart_path=chart_embed)
    out_path = _write(args.output, markdown)
    if args.json_output:
        _write(args.json_output, json.dumps(report_dict, indent=2))

    run_id = None
    if persistence_enabled() and not args.no_persist:
        try:
            run_id = persist_report(report)
        except Exception as exc:
            print(f"warning: persistence failed ({type(exc).__name__}: {exc})", file=sys.stderr)

    print(
        f"Evaluated {report.total} scenario(s): "
        f"{report.passed_count} passed, {report.total - report.passed_count} failed "
        f"(pass rate {report.pass_rate * 100:.0f}%, avg score {report.average_score:.2f})."
    )
    print(f"Report written to {out_path}")
    if chart_embed:
        print(f"Chart written to {args.svg}")
    if args.json_output:
        print(f"JSON written to {args.json_output}")
    if run_id:
        print(f"Persisted evaluation run {run_id}")
    elif not persistence_enabled():
        print("Persistence skipped (DATABASE_URL not set).")

    if args.strict and report.passed_count < report.total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
