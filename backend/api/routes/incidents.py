"""Durable incident investigation endpoints (KAN-17).

    POST /incidents                  submit an incident -> persisted investigation
    GET  /incidents                  list recent investigations (with filters)
    GET  /incidents/{incident_id}    retrieve a full stored investigation
    GET  /agent-runs/{run_id}        inspect agent run metadata

Processing is synchronous for MVP simplicity: a submission runs the agent and
returns once the investigation is stored, so a client never has to poll. The
agent_run status therefore lands as ``succeeded`` or ``failed`` immediately
(the queued/running states are reserved for a future async path).

These endpoints require the persistence layer (DATABASE_URL). When it is not
configured they return 503 with a clear message; the live, in-memory endpoints
under ``/diagnoses`` remain available regardless.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api import persistence
from backend.api.schemas import (
    AgentRunResponse,
    IncidentListResponse,
    IncidentRequest,
    IncidentSummary,
    InvestigationResponse,
    RunStatusFilter,
    SubmitResponse,
)
from backend.api.service import DiagnosisService, get_service
from backend.telemetry.schema import Scenario, Severity

router = APIRouter(tags=["incidents"])


def _require_persistence() -> None:
    if not persistence.persistence_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Persistence is not configured. Set DATABASE_URL to enable durable "
                "incident history (see .env.example)."
            ),
        )


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=422, detail=f"{label} must be a valid UUID.")


@router.post("/incidents", response_model=SubmitResponse, status_code=201)
def submit_incident(
    incident: IncidentRequest,
    service: DiagnosisService = Depends(get_service),
) -> SubmitResponse:
    """Submit a normalized incident; runs the agent and persists the result."""
    receipt = service.submit(incident.model_dump(mode="json"))
    return SubmitResponse(**receipt)


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(
    service: str | None = Query(default=None, description="Filter by service name."),
    severity: Severity | None = Query(default=None, description="Filter by severity."),
    status: RunStatusFilter | None = Query(
        default=None, description="Filter by agent run status."
    ),
    scenario: Scenario | None = Query(default=None, description="Filter by scenario."),
    limit: int = Query(default=50, ge=1, le=200, description="Max rows to return."),
) -> IncidentListResponse:
    """List recent investigations, most recent first, with optional filters."""
    _require_persistence()
    rows = persistence.list_investigations(
        service=service,
        severity=severity.value if severity else None,
        status=status.value if status else None,
        scenario=scenario.value if scenario else None,
        limit=limit,
    )
    return IncidentListResponse(
        count=len(rows), items=[IncidentSummary(**r) for r in rows]
    )


@router.get("/incidents/{incident_id}", response_model=InvestigationResponse)
def get_incident(incident_id: str) -> InvestigationResponse:
    """Return the full stored investigation for an incident id."""
    _require_persistence()
    iid = _parse_uuid(incident_id, "incident_id")
    full = persistence.fetch_investigation(iid)
    if full is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return InvestigationResponse(**full)


@router.get("/agent-runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(run_id: str) -> AgentRunResponse:
    """Return metadata for a single agent run."""
    _require_persistence()
    rid = _parse_uuid(run_id, "run_id")
    run = persistence.fetch_agent_run(rid)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return AgentRunResponse(**run)
