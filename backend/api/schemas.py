"""API request/response schemas (KAN-7).

The request body reuses the normalized incident schema (KAN-3) so invalid
payloads get clear 422 validation errors automatically. Response models keep the
OpenAPI docs useful; nested diagnosis/remediation content is returned as
structured objects produced by the analysis/remediation layers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Reuse the normalized incident model as the submit request body.
from backend.telemetry.schema import NormalizedIncident

IncidentRequest = NormalizedIncident


class SubmitResponse(BaseModel):
    """Receipt returned when an incident is submitted/replayed."""

    diagnosis_id: str = Field(description="Identifier to fetch the live (in-memory) result.")
    correlation_id: str = Field(description="Trace ID tying together logs for this diagnosis.")
    incident_id: str
    status: str = Field(description='"ok" or "error".')
    investigation_id: str | None = Field(
        default=None,
        description=(
            "Persisted investigation id (use with GET /incidents/{id}). "
            "Null when persistence is disabled (no DATABASE_URL)."
        ),
    )


class RunStatusFilter(str, Enum):
    """Agent run status used to filter the investigations list (KAN-17)."""

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class IncidentSummary(BaseModel):
    """Compact view of a stored investigation for the history list."""

    incident_id: str
    external_ref: str | None = None
    service: str
    scenario: str | None = None
    severity: str
    status: str
    title: str
    summary: str | None = None
    is_replay: bool = False
    intake_source: str | None = None
    run_id: str | None = None
    run_status: str | None = None
    engine: str | None = None
    diagnosis_status: str | None = None
    top_hypothesis: str | None = None
    created_at: str | None = None


class IncidentListResponse(BaseModel):
    """Recent investigations, most recent first."""

    count: int
    items: list[IncidentSummary]


class AgentRunResponse(BaseModel):
    """Agent run metadata (status, engine, timing, correlation)."""

    id: str
    incident_id: str
    run_type: str
    engine: str
    status: str
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    correlation_id: str | None = None
    created_at: str | None = None
    model_config = {"extra": "allow"}


class InvestigationResponse(BaseModel):
    """Full persisted investigation: incident + run(s) + evidence + diagnosis."""

    incident: dict[str, Any]
    agent_runs: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    diagnosis: dict[str, Any] | None = None
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioInfo(BaseModel):
    scenario: str
    replay_url: str = Field(description="POST here to replay this sample scenario.")


class ScenarioList(BaseModel):
    scenarios: list[ScenarioInfo]
