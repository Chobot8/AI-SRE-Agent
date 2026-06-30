"""CLI for the scenario packs (KAN-18).

Examples:
    python -m backend.scenarios list
    python -m backend.scenarios validate
    python -m backend.scenarios validate checkout-latency-ambiguous
    python -m backend.scenarios show payment-error-spike
    python -m backend.scenarios replay payment-error-spike
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.scenarios.loader import (
    candidate_packs,
    list_packs,
    load_pack,
    to_normalized_incident,
    validate_pack,
)


def _flags(expected: dict) -> str:
    tags = []
    if expected.get("is_ambiguous"):
        tags.append("ambiguous")
    if expected.get("is_multi_cause"):
        tags.append("multi-cause")
    if expected.get("is_false_positive"):
        tags.append("false-positive")
    return f" [{', '.join(tags)}]" if tags else ""


def _cmd_list(_: argparse.Namespace) -> int:
    slugs = list_packs()
    if not slugs:
        print("No scenario packs found under scenarios/.")
        return 1
    for slug in slugs:
        expected = load_pack(slug)["expected"] or {}
        title = expected.get("title", "")
        scenario = expected.get("agent_scenario", "?")
        print(f"- {slug} ({scenario}){_flags(expected)}\n    {title}")
    print(f"\n{len(slugs)} scenario pack(s).")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    # Default to every candidate directory (not just complete packs) so an
    # incomplete pack missing expected.yaml is discovered and flagged.
    targets = args.slugs or candidate_packs()
    total_errors = 0
    for slug in targets:
        errs = validate_pack(slug)
        if errs:
            total_errors += len(errs)
            print(f"FAIL {slug}")
            for e in errs:
                print(f"    - {e}")
        else:
            print(f"OK   {slug}")
    print(f"\n{len(targets)} pack(s), {total_errors} error(s).")
    return 1 if total_errors else 0


def _cmd_show(args: argparse.Namespace) -> int:
    incident = to_normalized_incident(load_pack(args.slug))
    print(json.dumps(incident, indent=2))
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    # Imported lazily: replay needs the analysis/remediation layers.
    from backend.analysis import diagnose_incident
    from backend.remediation import recommend_for

    pack = load_pack(args.slug)
    incident = to_normalized_incident(pack)
    diagnosis = diagnose_incident(incident)
    plan = recommend_for(diagnosis)
    expected = pack["expected"] or {}

    print(f"# Scenario replay: {args.slug}{_flags(expected)}")
    print(f"agent_scenario : {incident['scenario']}")
    print(f"status         : {diagnosis.status}")
    print(f"summary        : {diagnosis.summary}")
    print("\n## Ranked hypotheses (agent)")
    for i, h in enumerate(diagnosis.hypotheses, start=1):
        print(f"  {i}. {h.cause} ({h.confidence_label}, {h.confidence:.2f})")
    print("\n## Recommended actions (agent)")
    for i, r in enumerate(plan.recommendations, start=1):
        flag = " [approval-required]" if r.approval_required else ""
        print(f"  {i}. [{r.action.value}] {r.title}{flag}")
    print("\n## Expected (ground truth)")
    print(f"  root cause : {expected.get('root_cause', {}).get('summary', '').strip()}")
    direction = expected.get("expected_remediation", {}).get("direction")
    print(f"  remediation: {direction}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.scenarios")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List scenario packs").set_defaults(func=_cmd_list)

    p_val = sub.add_parser("validate", help="Validate file presence + schema")
    p_val.add_argument("slugs", nargs="*", help="Specific packs (default: all)")
    p_val.set_defaults(func=_cmd_validate)

    p_show = sub.add_parser("show", help="Print the assembled NormalizedIncident")
    p_show.add_argument("slug")
    p_show.set_defaults(func=_cmd_show)

    p_replay = sub.add_parser("replay", help="Run a pack through the agent locally")
    p_replay.add_argument("slug")
    p_replay.set_defaults(func=_cmd_replay)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
