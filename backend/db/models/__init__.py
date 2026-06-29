"""ORM models mirroring infra/db/schema.sql (KAN-16).

These are persistence models only. The schema itself is created by Alembic /
the schema.sql init (not by ``Base.metadata.create_all``), so these classes are
intentionally limited to what the repositories need to read and write —
CHECK/constraint enforcement lives in the database. All tables are in the ``sre``
schema (set on ``Base.metadata``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _created() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    external_ref: Mapped[str | None] = mapped_column(Text)
    intake_source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'alert'")
    )
    is_replay: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    replay_of_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="SET NULL")
    )
    scenario: Mapped[str | None] = mapped_column(Text)
    service: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'local'")
    )
    severity: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'warning'")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'")
    )
    alert_source: Mapped[str | None] = mapped_column(Text)
    alert_summary: Mapped[str | None] = mapped_column(Text)
    alert_labels: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    symptoms: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    expected_root_cause: Mapped[Any | None] = mapped_column(JSONB)
    raw_payload_ref: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    actor: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'system'")
    )
    correlation_id: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = _created()
    created_at: Mapped[datetime] = _created()


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="CASCADE"), nullable=False
    )
    run_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'full'")
    )
    engine: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'deterministic'")
    )
    model_provider: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    tool_calls: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 5))
    error_type: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="CASCADE"), nullable=False
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.agent_runs.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    score: Mapped[float | None] = mapped_column(Float)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class RetrievedChunk(Base):
    __tablename__ = "retrieved_chunks"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="CASCADE"), nullable=False
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.agent_runs.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str | None] = mapped_column(Text)
    citation: Mapped[str | None] = mapped_column(Text)
    chunk_text: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    vector_store: Mapped[str | None] = mapped_column(Text)
    chunk_external_id: Mapped[str | None] = mapped_column(Text)
    chunk_metadata: Mapped[Any] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    retrieved_at: Mapped[datetime] = _created()
    created_at: Mapped[datetime] = _created()


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="CASCADE"), nullable=False
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.agent_runs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ok'")
    )
    engine: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'deterministic'")
    )
    summary: Mapped[str | None] = mapped_column(Text)
    symptoms: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    reference_citations: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created()


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="CASCADE"), nullable=False
    )
    diagnosis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.diagnoses.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    cause: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    confidence_label: Mapped[str | None] = mapped_column(Text)
    root_cause_category: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    recommended_checks: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    missing_information: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    is_selected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = _created()


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="CASCADE"), nullable=False
    )
    diagnosis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.diagnoses.id", ondelete="SET NULL")
    )
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.hypotheses.id", ondelete="SET NULL")
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.agent_runs.id", ondelete="SET NULL")
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    action_category: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    risk_level: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'low'")
    )
    rollback_note: Mapped[str | None] = mapped_column(Text)
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    production_impacting: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    execution_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'manual_only'")
    )
    created_at: Mapped[datetime] = _created()


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    baseline_version: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[str | None] = mapped_column(Text)
    model_provider: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    git_sha: Mapped[str | None] = mapped_column(Text)
    total_scenarios: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    passed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    pass_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    avg_top_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'running'")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.organizations.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sre.evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    scenario: Mapped[str] = mapped_column(Text, nullable=False)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.incidents.id", ondelete="SET NULL")
    )
    diagnosis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sre.diagnoses.id", ondelete="SET NULL")
    )
    expected_category: Mapped[str | None] = mapped_column(Text)
    expected_top_cause: Mapped[str | None] = mapped_column(Text)
    expected_runbook: Mapped[str | None] = mapped_column(Text)
    predicted_category: Mapped[str | None] = mapped_column(Text)
    predicted_top_cause: Mapped[str | None] = mapped_column(Text)
    top_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    category_match: Mapped[bool | None] = mapped_column(Boolean)
    cause_match: Mapped[bool | None] = mapped_column(Boolean)
    runbook_match: Mapped[bool | None] = mapped_column(Boolean)
    passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    details: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = _created()


__all__ = [
    "Organization",
    "Incident",
    "IncidentEvent",
    "AgentRun",
    "EvidenceItem",
    "RetrievedChunk",
    "Diagnosis",
    "Hypothesis",
    "Recommendation",
    "EvaluationRun",
    "EvaluationResult",
]
