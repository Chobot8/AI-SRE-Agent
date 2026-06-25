"""Remediation demo CLI (KAN-6).

Runs the full chain for a sample scenario: diagnose (KAN-5) -> recommend (KAN-6).

Usage:
    python -m backend.remediation db_saturation
    python -m backend.remediation error_rate_spike --json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.analysis import diagnose_incident
from backend.remediation import recommend_for


def _load(scenario: str) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "sample-data" / "incidents" / f"{scenario}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    as_json = "--json" in argv
    scenario = args[0] if args else "db_saturation"

    diagnosis = diagnose_incident(_load(scenario))
    plan = recommend_for(diagnosis)
    print(plan.to_json() if as_json else plan.to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
