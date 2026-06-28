"""API request/response schemas (KAN-7).

The request body reuses the normalized incident schema (KAN-3) so invalid
payloads get clear 422 validation errors automatically. Response models keep the
OpenAPI docs useful; nested diagnosis/remediation content is returned as
structured objects produced by the analysis/remediation layers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Reuse the normalized incident model as the submit request body.
from backend.telemetry.schema import NormalizedIncident

IncidentRequest = NormalizedIncident


class SubmitResponse(BaseModel):
    """Receipt returned when an incident is submitted/replayed."""

    diagnosis_id: str = Field(description="Identifier to fetch the full result.")
    correlation_id: str = Field(description="Trace ID tying together logs for this diagnosis.")
    incident_id: str
    status: str = Field(description='"ok" or "error".')


class ScenarioInfo(BaseModel):
    scenario: str
    replay_url: str = Field(description="POST here to replay this sample scenario.")


class ScenarioList(BaseModel):
    scenarios: list[ScenarioInfo]
