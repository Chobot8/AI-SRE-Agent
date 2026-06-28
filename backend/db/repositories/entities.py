"""Per-entity repositories (KAN-16).

One thin repository per persisted aggregate from the data model. They inherit
create/read from ``BaseRepository`` and add a few convenience lookups.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from backend.db import models
from backend.db.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[models.Organization]):
    model = models.Organization

    def get_by_slug(self, slug: str) -> models.Organization | None:
        stmt = select(models.Organization).where(models.Organization.slug == slug)
        return self.session.scalars(stmt).first()

    def ensure(self, slug: str, name: str) -> models.Organization:
        """Return the org with this slug, creating it if absent."""
        existing = self.get_by_slug(slug)
        if existing is not None:
            return existing
        return self.add(slug=slug, name=name)


class IncidentRepository(BaseRepository[models.Incident]):
    model = models.Incident

    def list_for_org(self, org_id: uuid.UUID) -> list[models.Incident]:
        return self.list_by(org_id=org_id)


class IncidentEventRepository(BaseRepository[models.IncidentEvent]):
    model = models.IncidentEvent


class AgentRunRepository(BaseRepository[models.AgentRun]):
    model = models.AgentRun


class EvidenceItemRepository(BaseRepository[models.EvidenceItem]):
    model = models.EvidenceItem


class RetrievedChunkRepository(BaseRepository[models.RetrievedChunk]):
    model = models.RetrievedChunk


class DiagnosisRepository(BaseRepository[models.Diagnosis]):
    model = models.Diagnosis

    def current_for_incident(self, incident_id: uuid.UUID) -> models.Diagnosis | None:
        stmt = select(models.Diagnosis).where(
            models.Diagnosis.incident_id == incident_id,
            models.Diagnosis.is_current.is_(True),
        )
        return self.session.scalars(stmt).first()


class HypothesisRepository(BaseRepository[models.Hypothesis]):
    model = models.Hypothesis

    def for_diagnosis(self, diagnosis_id: uuid.UUID) -> list[models.Hypothesis]:
        stmt = (
            select(models.Hypothesis)
            .where(models.Hypothesis.diagnosis_id == diagnosis_id)
            .order_by(models.Hypothesis.rank)
        )
        return list(self.session.scalars(stmt))


class RecommendationRepository(BaseRepository[models.Recommendation]):
    model = models.Recommendation

    def for_incident(self, incident_id: uuid.UUID) -> list[models.Recommendation]:
        stmt = (
            select(models.Recommendation)
            .where(models.Recommendation.incident_id == incident_id)
            .order_by(models.Recommendation.rank)
        )
        return list(self.session.scalars(stmt))


class EvaluationRunRepository(BaseRepository[models.EvaluationRun]):
    model = models.EvaluationRun


class EvaluationResultRepository(BaseRepository[models.EvaluationResult]):
    model = models.EvaluationResult
