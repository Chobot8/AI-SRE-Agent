"""Mock incident data source (KAN-3).

Loads bundled sample incidents from ``sample-data/incidents/<scenario>.json`` so
the placeholder connectors have realistic data to serve during local development
and tests. Each sample file contains the alert, metrics, logs, and ground-truth
root cause for one scenario.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def default_sample_data_dir() -> Path:
    """Locate the repo's ``sample-data`` directory relative to this file."""
    # backend/telemetry/connectors/mock_source.py -> repo root is 3 parents up.
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "sample-data"


class MockIncidentSource:
    """Reads raw incident dicts from the sample-data folder, keyed by scenario."""

    def __init__(self, sample_data_dir: Path | None = None) -> None:
        self.sample_data_dir = sample_data_dir or default_sample_data_dir()
        self.incidents_dir = self.sample_data_dir / "incidents"

    @lru_cache(maxsize=None)
    def load(self, scenario: str) -> dict:
        """Return the raw incident dict for ``scenario`` (e.g. 'high_latency')."""
        path = self.incidents_dir / f"{scenario}.json"
        if not path.exists():
            available = ", ".join(self.available_scenarios()) or "(none found)"
            raise FileNotFoundError(
                f"No mock incident for scenario '{scenario}' at {path}. "
                f"Available: {available}"
            )
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def available_scenarios(self) -> list[str]:
        """List scenario names available in the sample-data folder."""
        if not self.incidents_dir.exists():
            return []
        return sorted(p.stem for p in self.incidents_dir.glob("*.json"))
