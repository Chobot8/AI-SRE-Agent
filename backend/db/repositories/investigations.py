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

from sqlalchemy import func
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

    def latest_run_for_incident(self, incident_id: uuid.UUID) -> models.AgentRun | None:
        """Return the most recent agent run for an incident, if any."""
        stmt = (
            select(models.AgentRun)
            .where(models.AgentRun.incident_id == incident_id)
            .order_by(models.AgentRun.created_at.desc())
        )
        return self.session.scalars(stmt).first()

    def get_agent_run(self, run_id: uuid.UUID) -> dict[str, Any] | None:
        """Return a single agent run's metadata as a JSON-friendly dict, or None."""
        run = self.runs.get(run_id)
        return _row_to_dict(run) if run is not None else None

    def list_recent(
        self,
        org_id: uuid.UUID,
        *,
        service: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        scenario: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return recent investigations (most recent first) as summary dicts.

        ``status`` filters on the latest agent run's status
        (queued/running/succeeded/failed); the remaining filters apply to the
        incident's intake context.
        """
        stmt = select(models.Incident).where(models.Incident.org_id == org_id)
        if service:
            stmt = stmt.where(models.Incident.service == service)
        if severity:
            stmt = stmt.where(models.Incident.severity == severity)
        if scenario:
            stmt = stmt.where(models.Incident.scenario == scenario)
        if status:
            # Match on the *latest* run per incident so the filter is consistent
            # with the run_status shown in the response (not just "any run").
            latest_created = (
                select(
                    models.AgentRun.incident_id.label("incident_id"),
                    func.max(models.AgentRun.created_at).label("max_created"),
                )
                .group_by(models.AgentRun.incident_id)
                .subquery()
            )
            latest_with_status = (
                select(models.AgentRun.incident_id)
                .join(
                    latest_created,
                    (models.AgentRun.incident_id == latest_created.c.incident_id)
                    & (models.AgentRun.created_at == latest_created.c.max_created),
                )
                .where(models.AgentRun.status == status)
            )
            stmt = stmt.where(models.Incident.id.in_(latest_with_status))
        stmt = stmt.order_by(models.Incident.created_at.desc()).limit(limit)

        summaries: list[dict[str, Any]] = []
        for inc in self.session.scalars(stmt):
            diag = self.diagnoses.current_for_incident(inc.id)
            run = self.latest_run_for_incident(inc.id)
            top = self.hypotheses.for_diagnosis(diag.id)[:1] if diag else []
            summaries.append(
                {
                    "incident_id": str(inc.id),
                    "external_ref": inc.external_ref,
                    "service": inc.service,
                    "scenario": inc.scenario,
                    "severity": inc.severity,
                    "status": inc.status,
                    "title": inc.title,
                    "summary": inc.summary,
                    "is_replay": inc.is_replay,
                    "intake_source": inc.intake_source,
                    "run_id": str(run.id) if run else None,
                    "run_status": run.status if run else None,
                    "engine": run.engine if run else None,
                    "diagnosis_status": diag.status if diag else None,
                    "top_hypothesis": top[0].cause if top else None,
                    "created_at": _jsonable(inc.created_at),
                }
            )
        return summaries

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
