"""Incident analysis CLI / demo (KAN-5).

Usage:
    python -m backend.analysis high_latency           # readable diagnosis
    python -m backend.analysis db_saturation --json   # machine-readable JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.analysis.pipeline import diagnose_incident


def _load(scenario: str) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "sample-data" / "incidents" / f"{scenario}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    as_json = "--json" in argv
    scenario = args[0] if args else "high_latency"

    diagnosis = diagnose_incident(_load(scenario))
    print(diagnosis.to_json() if as_json else diagnosis.to_markdown())
    return 0 if diagnosis.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
