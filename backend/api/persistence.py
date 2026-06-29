"""Investigation persistence bridge (KAN-17).

Turns the live agent output (a normalized incident, a diagnosis, and a
remediation plan) into the plain-dict aggregate the storage layer (KAN-16)
expects, and wraps the read/write paths the API exposes.

Design notes:
* ``build_investigation_payload`` is a pure dict-in / dict-out transform with no
  database or framework dependencies, so it is trivially unit-testable.
* All database imports are lazy (inside the functions) so importing this module
  never requires SQLAlchemy/psycopg — callers that only need the pure builder
  (and environments without the DB libs) import cleanly.
* The agent workflow keeps exchanging plain dicts; ORM objects never cross this
  boundary.
"""

from __future__ import annotations

import uuid
from typing import Any

# Default tenant for the single-tenant MVP (matches backend.db.seed).
DEFAULT_ORG_SLUG = "local"
DEFAULT_ORG_NAME = "Local Dev"

# Evidence is derived from the incident's own telemetry; cap how much we store.
_MAX_METRIC_EVIDENCE = 10
_MAX_LOG_EVIDENCE = 5
_NOTABLE_LOG_LEVELS = {"ERROR", "FATAL"}


def _evidence_from_incident(incident_request: dict[str, Any]) -> list[dict[str, Any]]:
    """Build evidence_items rows from the incident's metrics and notable logs."""
    evidence: list[dict[str, Any]] = []

    for metric in (incident_request.get("metrics") or [])[:_MAX_METRIC_EVIDENCE]:
        points = metric.get("points") or []
        last_value = points[-1].get("value") if points else None
        unit = metric.get("unit")
        evidence.append(
            {
                "kind": "metric",
                "source": "telemetry",
                "title": str(metric.get("name", "metric")),
                "summary": metric.get("description")
                or f"{metric.get('name', 'metric')} ({unit})",
                "detail": {
                    "unit": unit,
                    "points": len(points),
                    "last_value": last_value,
                },
            }
        )

    notable = [
        log
        for log in (incident_request.get("logs") or [])
        if str(log.get("level")) in _NOTABLE_LOG_LEVELS
    ][:_MAX_LOG_EVIDENCE]
    for log in notable:
        evidence.append(
            {
                "kind": "log",
                "source": log.get("service") or "logs",
                "title": f"{log.get('level', 'LOG')} log",
                "summary": log.get("message"),
                "detail": {
                    "level": log.get("level"),
                    "service": log.get("service"),
                },
            }
        )

    return evidence


def build_investigation_payload(
    *,
    incident_request: dict[str, Any],
    diagnosis: dict[str, Any],
    remediation: dict[str, Any] | None = None,
    retrieved_chunks: list[dict[str, Any]] | None = None,
    run: dict[str, Any] | None = None,
    intake_source: str = "manual",
    is_replay: bool = False,
) -> dict[str, Any]:
    """Map live agent output to ``InvestigationRepository.create_full`` kwargs.

    ``diagnosis`` is ``IncidentDiagnosis.to_dict()`` and ``remediation`` is
    ``RemediationPlan.to_dict()`` (or equivalents). The result is a plain dict of
    keyword arguments — no ORM objects, no DB access.
    """
    remediation = remediation or {}
    run = run or {}
    alert = incident_request.get("alert") or {}

    diag_ok = diagnosis.get("status") == "ok"
    engine = diagnosis.get("engine") or "deterministic"

    incident = {
        "external_ref": incident_request.get("id"),
        "intake_source": intake_source,
        "is_replay": is_replay,
        "scenario": incident_request.get("scenario"),
        "service": str(incident_request.get("service", "unknown")),
        "environment": incident_request.get("environment") or "local",
        "severity": alert.get("severity") or "warning",
        "title": str(alert.get("summary") or diagnosis.get("summary") or "incident")[:500],
        "summary": diagnosis.get("summary"),
        "status": "diagnosed" if diag_ok else "investigating",
        "alert_source": alert.get("source"),
        "alert_summary": alert.get("summary"),
        "alert_labels": alert.get("labels") or {},
        "symptoms": diagnosis.get("symptoms") or [],
        "expected_root_cause": incident_request.get("expected_root_cause"),
    }

    agent_run = {
        "run_type": "full",
        "engine": engine,
        "status": run.get("status", "succeeded" if diag_ok else "failed"),
        "latency_ms": run.get("latency_ms"),
        "correlation_id": run.get("correlation_id"),
    }
    if run.get("error_type"):
        agent_run["error_type"] = run["error_type"]
    if run.get("error_message"):
        agent_run["error_message"] = run["error_message"]

    diag_row = {
        "status": diagnosis.get("status", "ok"),
        "engine": engine,
        "summary": diagnosis.get("summary"),
        "symptoms": diagnosis.get("symptoms") or [],
        "reference_citations": diagnosis.get("references") or [],
        "error": diagnosis.get("error"),
        "is_current": True,
    }

    hypotheses = []
    for i, hyp in enumerate(diagnosis.get("hypotheses") or []):
        hypotheses.append(
            {
                "rank": i + 1,
                "cause": hyp.get("cause", "unknown"),
                "confidence": hyp.get("confidence", 0.0),
                "confidence_label": hyp.get("confidence_label"),
                "evidence": hyp.get("evidence") or [],
                "recommended_checks": hyp.get("recommended_checks") or [],
                "missing_information": hyp.get("missing_information") or [],
                "is_selected": i == 0,
            }
        )

    recommendations = []
    for i, rec in enumerate(remediation.get("recommendations") or []):
        recommendations.append(
            {
                "rank": i + 1,
                "action_category": rec.get("action", "investigate"),
                "title": rec.get("title", "recommendation"),
                "rationale": rec.get("rationale"),
                "evidence": rec.get("evidence") or [],
                "risk_level": rec.get("risk", "low"),
                "rollback_note": rec.get("rollback_note"),
                "approval_required": bool(rec.get("approval_required", False)),
                "production_impacting": bool(rec.get("production_impacting", False)),
                "execution_status": rec.get("execution", "manual_only"),
            }
        )

    return {
        "incident": incident,
        "agent_run": agent_run,
        "evidence": _evidence_from_incident(incident_request),
        "retrieved_chunks": retrieved_chunks or [],
        "diagnosis": diag_row,
        "hypotheses": hypotheses,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Database-backed helpers (lazy imports so this module loads without the DB libs)
# ---------------------------------------------------------------------------


def persistence_enabled() -> bool:
    """True when a database is configured (DATABASE_URL is set)."""
    from backend.config import get_settings

    return bool(get_settings().database_url)


def persist_investigation(payload: dict[str, Any]) -> dict[str, str | None]:
    """Persist a full investigation; return string ids for the created rows.

    The default org is created on first use. If the incident's business key
    (``external_ref``) already exists for the org, it is suffixed so each
    submission/replay is stored as its own investigation.
    """
    from sqlalchemy import select

    from backend.db import models
    from backend.db.repositories.entities import OrganizationRepository
    from backend.db.repositories.investigations import InvestigationRepository
    from backend.db.session import session_scope

    with session_scope() as session:
        org = OrganizationRepository(session).ensure(DEFAULT_ORG_SLUG, DEFAULT_ORG_NAME)
        session.flush()

        ext = payload.get("incident", {}).get("external_ref")
        if ext:
            exists = session.scalars(
                select(models.Incident).where(
                    models.Incident.org_id == org.id,
                    models.Incident.external_ref == ext,
                )
            ).first()
            if exists is not None:
                payload["incident"]["external_ref"] = f"{ext}-{uuid.uuid4().hex[:8]}"

        ids = InvestigationRepository(session).create_full(org_id=org.id, **payload)
        return {k: (str(v) if v is not None else None) for k, v in ids.items()}


def fetch_investigation(incident_id: uuid.UUID) -> dict[str, Any] | None:
    """Return the full stored investigation for an incident id, or None."""
    from backend.db.repositories.investigations import InvestigationRepository
    from backend.db.session import session_scope

    with session_scope() as session:
        return InvestigationRepository(session).get_full(incident_id)


def fetch_agent_run(run_id: uuid.UUID) -> dict[str, Any] | None:
    """Return a single agent run's metadata, or None."""
    from backend.db.repositories.investigations import InvestigationRepository
    from backend.db.session import session_scope

    with session_scope() as session:
        return InvestigationRepository(session).get_agent_run(run_id)


def list_investigations(
    *,
    service: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    scenario: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent investigation summaries for the default org."""
    from backend.db.repositories.entities import OrganizationRepository
    from backend.db.repositories.investigations import InvestigationRepository
    from backend.db.session import session_scope

    with session_scope() as session:
        org = OrganizationRepository(session).get_by_slug(DEFAULT_ORG_SLUG)
        if org is None:
            return []
        return InvestigationRepository(session).list_recent(
            org.id,
            service=service,
            severity=severity,
            status=status,
            scenario=scenario,
            limit=limit,
        )
