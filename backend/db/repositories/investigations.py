"""Investigation aggregate repository (KAN-16).

Creates and reads back a *complete* incident investigation — incident, agent
run, evidence, retrieved chunks, diagnosis, hypotheses, recommendations — across
the persistence boundary. Inputs and outputs are plain dicts so the agent
workflow never touches ORM instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.repositories.entities import (
    AgentRunRepository,
    DiagnosisRepository,
    EvidenceItemRepository,
    HypothesisRepository,
    IncidentRepository,
    RecommendationRepository,
    RetrievedChunkRepository,
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_to_dict(obj: Any) -> dict[str, Any]:
    mapper = sa_inspect(obj).mapper
    return {attr.key: _jsonable(getattr(obj, attr.key)) for attr in mapper.column_attrs}


class InvestigationRepository:
    """Persist / load a whole investigation as one aggregate."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.incidents = IncidentRepository(session)
        self.runs = AgentRunRepository(session)
        self.evidence = EvidenceItemRepository(session)
        self.chunks = RetrievedChunkRepository(session)
        self.diagnoses = DiagnosisRepository(session)
        self.hypotheses = HypothesisRepository(session)
        self.recommendations = RecommendationRepository(session)

    def create_full(
        self,
        *,
        org_id: uuid.UUID,
        incident: dict[str, Any],
        agent_run: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        retrieved_chunks: list[dict[str, Any]] | None = None,
        diagnosis: dict[str, Any] | None = None,
        hypotheses: list[dict[str, Any]] | None = None,
        recommendations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create an incident and its full investigation chain; return key ids."""
        if hypotheses and diagnosis is None:
            raise ValueError("hypotheses require a diagnosis")

        inc = self.incidents.add(org_id=org_id, **incident)

        run_id: uuid.UUID | None = None
        if agent_run is not None:
            run = self.runs.add(org_id=org_id, incident_id=inc.id, **agent_run)
            run_id = run.id

        for item in evidence or []:
            self.evidence.add(
                org_id=org_id, incident_id=inc.id, agent_run_id=run_id, **item
            )
        for chunk in retrieved_chunks or []:
            self.chunks.add(
                org_id=org_id, incident_id=inc.id, agent_run_id=run_id, **chunk
            )

        diag_id: uuid.UUID | None = None
        if diagnosis is not None:
            diag = self.diagnoses.add(
                org_id=org_id, incident_id=inc.id, agent_run_id=run_id, **diagnosis
            )
            diag_id = diag.id
            for hyp in hypotheses or []:
                self.hypotheses.add(
                    org_id=org_id, incident_id=inc.id, diagnosis_id=diag_id, **hyp
                )

        for rec in recommendations or []:
            self.recommendations.add(
                org_id=org_id,
                incident_id=inc.id,
                diagnosis_id=diag_id,
                agent_run_id=run_id,
                **rec,
            )

        return {
            "incident_id": inc.id,
            "agent_run_id": run_id,
            "diagnosis_id": diag_id,
        }

    def get_full(self, incident_id: uuid.UUID) -> dict[str, Any] | None:
        """Return the whole investigation as JSON-friendly dicts, or None."""
        inc = self.incidents.get(incident_id)
        if inc is None:
            return None

        diag = self.diagnoses.current_for_incident(incident_id)
        if diag is None:
            stmt = (
                select(models.Diagnosis)
                .where(models.Diagnosis.incident_id == incident_id)
                .order_by(models.Diagnosis.created_at.desc())
            )
            diag = self.session.scalars(stmt).first()

        hyps = self.hypotheses.for_diagnosis(diag.id) if diag else []
        return {
            "incident": _row_to_dict(inc),
            "agent_runs": [_row_to_dict(r) for r in self.runs.list_by(incident_id=incident_id)],
            "evidence": [
                _row_to_dict(e) for e in self.evidence.list_by(incident_id=incident_id)
            ],
            "retrieved_chunks": [
                _row_to_dict(c) for c in self.chunks.list_by(incident_id=incident_id)
            ],
            "diagnosis": _row_to_dict(diag) if diag else None,
            "hypotheses": [_row_to_dict(h) for h in hyps],
            "recommendations": [
                _row_to_dict(r) for r in self.recommendations.for_incident(incident_id)
            ],
        }
