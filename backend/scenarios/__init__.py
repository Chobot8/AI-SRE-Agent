"""Scenario pack loading, validation, and replay (KAN-18).

Richer, structured incident scenarios under the repo-root ``scenarios/`` folder.
Each pack is a directory with ``alert.json``, ``logs.jsonl``, ``metrics.json``,
``service_health.json``, ``runbook.md``, and ``expected.yaml``. The loader
validates file presence and schema, and can assemble a ``NormalizedIncident``
so a pack can be replayed through the existing agent (KAN-3/5/6/7).
"""

from __future__ import annotations

from backend.scenarios.loader import (
    REQUIRED_FILES,
    SCENARIOS_DIR,
    ScenarioError,
    candidate_packs,
    list_packs,
    load_pack,
    to_normalized_incident,
    validate_all,
    validate_pack,
)

__all__ = [
    "REQUIRED_FILES",
    "SCENARIOS_DIR",
    "ScenarioError",
    "candidate_packs",
    "list_packs",
    "load_pack",
    "to_normalized_incident",
    "validate_all",
    "validate_pack",
]
