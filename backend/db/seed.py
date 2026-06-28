"""Seed local development data (KAN-16).

Creates a default organization and one complete sample incident investigation
(the ``high_latency`` / ``checkout-api`` scenario) so the API/UI and queries have
something to show against a fresh database. Idempotent: re-running is a no-op.

Run:  python -m backend.db.seed
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from backend.db import models
from backend.db.repositories.entities import OrganizationRepository
from backend.db.repositories.investigations import InvestigationRepository
from backend.db.session import check_connection, session_scope

DEFAULT_ORG_SLUG = "local"
SEED_EXTERNAL_REF = "SEED-INC-1001"


def _sample_investigation() -> dict[str, Any]:
    return {
        "incident": {
            "external_ref": SEED_EXTERNAL_REF,
            "intake_source": "replay",
            "is_replay": True,
            "scenario": "high_latency",
            "service": "checkout-api",
            "environment": "local",
            "severity": "critical",
            "title": "checkout-api p99 latency above SLO",
            "summary": (
                "CRITICAL alert on checkout-api: p99 1200ms over the 500ms SLO. "
                "Leading hypothesis: slow downstream dependency / unindexed query."
            ),
            "status": "diagnosed",
            "alert_source": "prometheus",
            "alert_summary": "checkout-api p99 latency above SLO (1200ms > 500ms) for 10m",
            "alert_labels": {"service": "checkout-api", "severity": "critical"},
            "symptoms": [
                "p99 latency 1200ms breaches the 500ms SLO",
                "orders-db query time rising while throughput is flat",
            ],
        },
        "agent_run": {
            "run_type": "full",
            "engine": "deterministic",
            "status": "succeeded",
            "latency_ms": 42,
            "correlation_id": "seed-correlation-0001",
        },
        "evidence": [
            {
                "kind": "metric",
                "source": "prometheus",
                "title": "p99 latency",
                "summary": "1200ms, above the 500ms SLO for 10m",
                "detail": {"unit": "ms", "value": 1200, "slo": 500},
                "score": 0.9,
            }
        ],
        "retrieved_chunks": [
            {
                "source": "high_latency.md",
                "heading": "Remediation",
                "citation": "[high_latency.md > Remediation]",
                "chunk_text": "Check for slow/unindexed queries on the hot path.",
                "score": 0.87,
                "vector_store": "inproc:runbooks",
            }
        ],
        "diagnosis": {
            "status": "ok",
            "engine": "deterministic",
            "summary": "Slow downstream dependency / unindexed query is the leading cause.",
            "symptoms": ["p99 over SLO", "DB query time rising", "throughput flat"],
            "reference_citations": ["[high_latency.md > Remediation]"],
            "is_current": True,
        },
        "hypotheses": [
            {
                "rank": 1,
                "cause": "Slow downstream dependency / unindexed query",
                "confidence": 0.9,
                "confidence_label": "high",
                "root_cause_category": "slow_dependency",
                "evidence": ["orders-db query time rising", "throughput flat"],
                "recommended_checks": [
                    "Inspect slow-query logs for the affected datastore",
                    "EXPLAIN the suspect query and confirm a missing index",
                ],
                "missing_information": ["Query execution plan"],
                "is_selected": True,
            }
        ],
        "recommendations": [
            {
                "rank": 1,
                "action_category": "tune_config",
                "title": "Add the missing index / optimize the query",
                "rationale": "A missing index on the hot query drives the p99 breach.",
                "evidence": ["missing index on orders.user_id"],
                "risk_level": "medium",
                "rollback_note": "Indexes can be dropped; build concurrently to avoid locking.",
                "approval_required": True,
                "production_impacting": False,
                "execution_status": "manual_only",
            }
        ],
    }


def seed() -> dict[str, Any]:
    """Create the default org + sample investigation if not already present."""
    check_connection()
    with session_scope() as session:
        org = OrganizationRepository(session).ensure(DEFAULT_ORG_SLUG, "Local Dev")
        session.flush()

        already = session.scalars(
            select(models.Incident).where(
                models.Incident.org_id == org.id,
                models.Incident.external_ref == SEED_EXTERNAL_REF,
            )
        ).first()
        if already is not None:
            return {"org_id": str(org.id), "incident_id": str(already.id), "created": False}

        ids = InvestigationRepository(session).create_full(
            org_id=org.id, **_sample_investigation()
        )
        return {
            "org_id": str(org.id),
            "incident_id": str(ids["incident_id"]),
            "created": True,
        }


if __name__ == "__main__":
    result = seed()
    action = "created" if result["created"] else "already present"
    print(f"Seed {action}: org={result['org_id']} incident={result['incident_id']}")
