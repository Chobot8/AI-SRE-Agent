"""Create-and-read-back a complete incident investigation (KAN-16)."""

from __future__ import annotations

from backend.db.repositories.entities import OrganizationRepository
from backend.db.repositories.investigations import InvestigationRepository
from backend.db.seed import _sample_investigation


def test_create_and_read_back_full_investigation(session) -> None:
    org = OrganizationRepository(session).ensure("test-org", "Test Org")
    session.flush()

    repo = InvestigationRepository(session)
    ids = repo.create_full(org_id=org.id, **_sample_investigation())
    session.flush()

    full = repo.get_full(ids["incident_id"])
    assert full is not None

    # Incident intake context round-trips.
    assert full["incident"]["service"] == "checkout-api"
    assert full["incident"]["scenario"] == "high_latency"
    assert full["incident"]["severity"] == "critical"
    assert full["incident"]["alert_labels"]["service"] == "checkout-api"

    # The full chain is persisted and linked to the incident.
    assert len(full["agent_runs"]) == 1
    assert full["agent_runs"][0]["status"] == "succeeded"
    assert len(full["evidence"]) == 1
    assert len(full["retrieved_chunks"]) == 1

    assert full["diagnosis"]["status"] == "ok"
    assert full["diagnosis"]["is_current"] is True

    assert len(full["hypotheses"]) == 1
    assert full["hypotheses"][0]["rank"] == 1
    assert full["hypotheses"][0]["confidence_label"] == "high"

    assert len(full["recommendations"]) == 1
    assert full["recommendations"][0]["approval_required"] is True
    assert full["recommendations"][0]["execution_status"] == "manual_only"


def test_get_full_unknown_incident_returns_none(session) -> None:
    import uuid

    repo = InvestigationRepository(session)
    assert repo.get_full(uuid.uuid4()) is None
