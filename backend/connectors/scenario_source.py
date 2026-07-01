"""Shared local fixtures for mock connectors (KAN-22).

Mock connectors read from the same local, git-committed fixtures already used
elsewhere in the agent, so "mock connectors can power all existing scenario
packs" holds with no separate fixture data to keep in sync:

* ``scenarios/<slug>/`` (KAN-18) -- the richer packs: alert, metrics, logs,
  service/dependency health, and a runbook snippet.
* ``sample-data/incidents/<scenario>.json`` (KAN-3) -- the five flatter samples,
  used as a fallback so the mock connectors also resolve the plain scenario
  names (``high_latency``, ``db_saturation``, ...).
* ``knowledge/runbooks/*.md`` (KAN-4) -- the runbook knowledge base.

Every reader here is tolerant of missing files/fields and returns ``None`` /
``[]`` rather than raising, since a missing fixture is an expected "not found"
outcome for a connector, not a bug.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def repo_root() -> Path:
    # backend/connectors/scenario_source.py -> repo root is 2 parents up.
    return Path(__file__).resolve().parents[2]


def scenarios_dir() -> Path:
    return repo_root() / "scenarios"


def sample_data_incidents_dir() -> Path:
    return repo_root() / "sample-data" / "incidents"


def runbooks_dir() -> Path:
    return repo_root() / "knowledge" / "runbooks"


class ScenarioFixture:
    """Reads one scenario pack's files under ``scenarios/<slug>/``."""

    def __init__(self, slug: str, base_dir: Path | None = None) -> None:
        self.slug = slug
        self.dir = (base_dir or scenarios_dir()) / slug

    def exists(self) -> bool:
        return self.dir.is_dir()

    def _read_json(self, name: str) -> dict | None:
        path = self.dir / name
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def alert(self) -> dict | None:
        return self._read_json("alert.json")

    def metrics(self) -> list[dict]:
        data = self._read_json("metrics.json")
        return (data or {}).get("metrics", [])

    def logs(self) -> list[dict]:
        path = self.dir / "logs.jsonl"
        if not path.exists():
            return []
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def service_health(self) -> dict | None:
        return self._read_json("service_health.json")

    def runbook(self) -> str | None:
        path = self.dir / "runbook.md"
        return path.read_text(encoding="utf-8") if path.exists() else None


def available_scenario_slugs() -> list[str]:
    """Every scenario pack directory under ``scenarios/`` (excludes ``schema``)."""
    d = scenarios_dir()
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir() and p.name != "schema")


@lru_cache(maxsize=None)
def load_sample_incident(scenario: str) -> dict | None:
    """Fallback fixture: the flatter ``sample-data/incidents/<scenario>.json``."""
    path = sample_data_incidents_dir() / f"{scenario}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def list_runbooks() -> dict[str, str]:
    """Every ``knowledge/runbooks/*.md`` file, keyed by stem (e.g. ``pod_crash_loop``)."""
    d = runbooks_dir()
    if not d.exists():
        return {}
    return {p.stem: p.read_text(encoding="utf-8") for p in d.glob("*.md")}


def find_scenario_slug_for_service(service: str) -> str | None:
    """Find the first ``scenarios/`` pack whose alert names ``service``."""
    for slug in available_scenario_slugs():
        alert = ScenarioFixture(slug).alert()
        if alert and alert.get("service") == service:
            return slug
    return None
