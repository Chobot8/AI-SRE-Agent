"""Diagnosis service layer (KAN-7).

Framework-agnostic orchestration behind the API: submit/replay an incident, run
the analysis (KAN-5) + remediation (KAN-6), store the result, and fetch it by id.
Kept free of FastAPI so it can be unit-tested without the web stack.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from backend.analysis import diagnose_incident
from backend.remediation import recommend_for


def _sample_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "sample-data" / "incidents"


class DiagnosisService:
    """Runs diagnoses and keeps results in an in-memory store."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def submit(self, incident: dict) -> dict:
        """Diagnose + recommend for an incident; store and return a receipt."""
        diagnosis = diagnose_incident(incident)
        plan = recommend_for(diagnosis)

        diagnosis_id = uuid.uuid4().hex
        result = {
            "diagnosis_id": diagnosis_id,
            **diagnosis.to_dict(),
            "remediation": plan.to_dict(),
        }
        self._store[diagnosis_id] = result
        return {
            "diagnosis_id": diagnosis_id,
            "incident_id": diagnosis.incident_id,
            "status": diagnosis.status,
        }

    def get(self, diagnosis_id: str) -> dict | None:
        """Return the full stored diagnosis result, or None."""
        return self._store.get(diagnosis_id)

    def available_scenarios(self) -> list[str]:
        d = _sample_dir()
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []

    def load_sample(self, scenario: str) -> dict | None:
        path = _sample_dir() / f"{scenario}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def replay(self, scenario: str) -> dict | None:
        """Submit a bundled sample scenario; None if the scenario is unknown."""
        sample = self.load_sample(scenario)
        if sample is None:
            return None
        return self.submit(sample)


_service: DiagnosisService | None = None


def get_service() -> DiagnosisService:
    """Return the process-wide service singleton (FastAPI dependency)."""
    global _service
    if _service is None:
        _service = DiagnosisService()
    return _service
