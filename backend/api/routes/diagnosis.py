"""Incident diagnosis API endpoints (KAN-7).

    POST /incidents/diagnose         submit a normalized incident -> diagnosis id
    POST /incidents/replay/{scenario} replay a bundled sample scenario -> diagnosis id
    GET  /diagnoses/{diagnosis_id}    fetch the full diagnosis + remediation
    GET  /scenarios                   list supported scenarios + replay URLs
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import (
    IncidentRequest,
    ScenarioInfo,
    ScenarioList,
    SubmitResponse,
)
from backend.api.service import DiagnosisService, get_service

router = APIRouter(tags=["diagnosis"])


@router.post("/incidents/diagnose", response_model=SubmitResponse, status_code=201)
def submit_incident(
    incident: IncidentRequest,
    service: DiagnosisService = Depends(get_service),
) -> SubmitResponse:
    """Submit a normalized incident (live only — never persisted).

    Returns a diagnosis id to fetch the live result via ``GET /diagnoses/{id}``.
    Use ``POST /incidents`` for the durable, persisted path.
    """
    receipt = service.submit(incident.model_dump(mode="json"))
    return SubmitResponse(**receipt)


@router.post("/incidents/replay/{scenario}", response_model=SubmitResponse, status_code=201)
def replay_scenario(
    scenario: str,
    service: DiagnosisService = Depends(get_service),
) -> SubmitResponse:
    """Replay a bundled sample scenario by name (see GET /scenarios).

    Persisted best-effort: the investigation is stored when a database is
    configured, but a live result is still returned (``investigation_id: null``)
    without one, so the demo works DB-free. For a guaranteed durable write use
    ``POST /incidents``.
    """
    receipt = service.replay(scenario)
    if receipt is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scenario '{scenario}'. See GET /scenarios.",
        )
    return SubmitResponse(**receipt)


@router.get("/diagnoses/{diagnosis_id}")
def get_diagnosis(
    diagnosis_id: str,
    service: DiagnosisService = Depends(get_service),
) -> dict:
    """Return the full diagnosis: summary, hypotheses, evidence, recommendations."""
    result = service.get(diagnosis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Diagnosis not found.")
    return result


@router.get("/scenarios", response_model=ScenarioList)
def list_scenarios(service: DiagnosisService = Depends(get_service)) -> ScenarioList:
    """List supported incident scenarios and their replay URLs."""
    return ScenarioList(
        scenarios=[
            ScenarioInfo(scenario=s, replay_url=f"/incidents/replay/{s}")
            for s in service.available_scenarios()
        ]
    )
