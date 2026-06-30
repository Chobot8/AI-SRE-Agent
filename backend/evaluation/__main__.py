"""CLI for the evaluation runner (KAN-19).

    python -m backend.evaluation --scenario all --output reports/eval-latest.md
    python -m backend.evaluation --scenario payment-error-spike,orders-db-saturation
    python -m backend.evaluation --list

(The ticket suggested ``app.evaluation.run``; this repo's package root is
``backend``, so the equivalent command is ``python -m backend.evaluation``.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.evaluation.report import render_markdown
from backend.evaluation.runner import resolve_scenarios, run_evaluation
from backend.scenarios import loader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.evaluation")
    parser.add_argument(
        "--scenario",
        default="all",
        help='"all" (default) or a comma-separated list of scenario slugs.',
    )
    parser.add_argument(
        "--output",
        default="reports/eval-latest.md",
        help="Path to write the Markdown report (default: reports/eval-latest.md).",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        default=None,
        help="Optional path to also write the raw results as JSON.",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available scenario packs and exit."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any scenario fails (useful for CI).",
    )
    args = parser.parse_args(argv)

    if args.list:
        for slug in loader.list_packs():
            print(slug)
        return 0

    try:
        slugs = resolve_scenarios(args.scenario)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not slugs:
        print("error: no scenario packs found.", file=sys.stderr)
        return 2

    report = run_evaluation(slugs)
    markdown = render_markdown(report)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    if args.json_output:
        jpath = Path(args.json_output)
        jpath.parent.mkdir(parents=True, exist_ok=True)
        jpath.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    print(
        f"Evaluated {report.total} scenario(s): "
        f"{report.passed_count} passed, {report.total - report.passed_count} failed "
        f"(pass rate {report.pass_rate * 100:.0f}%, avg score {report.average_score:.2f})."
    )
    print(f"Report written to {out_path}")
    if args.json_output:
        print(f"JSON written to {args.json_output}")

    if args.strict and report.passed_count < report.total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
