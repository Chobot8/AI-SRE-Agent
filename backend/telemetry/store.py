"""Incident storage (KAN-3).

Persists both the **raw** ingested payloads (exactly as received from a source)
and the **normalized** incident produced by the pipeline. Raw + normalized are
kept separately so downstream analysis is reproducible and auditable.

The MVP uses a simple filesystem store under ``data/`` plus an in-memory cache.
A real deployment would swap this for a database or object store while keeping
the same interface.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.telemetry.schema import NormalizedIncident


def default_data_dir() -> Path:
    """Repo-root ``data/`` directory for stored incidents."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data"


class IncidentStore:
    """Filesystem-backed store for raw and normalized incident data."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.raw_dir = self.data_dir / "raw"
        self.normalized_dir = self.data_dir / "normalized"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self._normalized_cache: dict[str, NormalizedIncident] = {}

    def save_raw(self, key: str, raw: dict) -> Path:
        """Persist a raw payload under ``raw/<key>.json``."""
        path = self.raw_dir / f"{key}.json"
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        return path

    def save_normalized(self, incident: NormalizedIncident) -> Path:
        """Persist a normalized incident under ``normalized/<id>.json``."""
        self._normalized_cache[incident.id] = incident
        path = self.normalized_dir / f"{incident.id}.json"
        path.write_text(incident.model_dump_json(indent=2), encoding="utf-8")
        return path

    def get_normalized(self, incident_id: str) -> NormalizedIncident | None:
        """Return a stored normalized incident, from cache or disk."""
        if incident_id in self._normalized_cache:
            return self._normalized_cache[incident_id]
        path = self.normalized_dir / f"{incident_id}.json"
        if not path.exists():
            return None
        incident = NormalizedIncident.model_validate_json(path.read_text(encoding="utf-8"))
        self._normalized_cache[incident_id] = incident
        return incident
