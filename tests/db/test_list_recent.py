"""Repository tests for listing recent investigations (KAN-17).

Focus on the ``status`` filter semantics: it must match the *latest* agent run
per incident, consistent with the run_status shown in the response — not "any
run ever had this status". Skips cleanly when no PostgreSQL is reachable.
"""

from __future__ import annotations

import datetime as dt

from backend.db.repositories.entities import OrganizationRepository
from backend.db.repositories.investigations import InvestigationRepository

_BASE = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def _incident(repo: InvestigationRepository, org_id, ref: str):
    return repo.incidents.add(
        org_id=org_id,
        external_ref=ref,
        service="checkout-api",
        scenario="high_latency",
        severity="warning",
        environment="local",
        title=f"incident {ref}",
    )


def test_status_filter_matches_latest_run(session) -> None:
    org = OrganizationRepository(session).ensure("t-list-recent", "List Recent Org")
    session.flush()
    repo = InvestigationRepository(session)

    # Incident whose first run failed but whose latest run succeeded.
    inc = _incident(repo, org.id, "LR-RECOVERED")
    repo.runs.add(
        org_id=org.id, incident_id=inc.id, status="failed", created_at=_BASE
    )
    repo.runs.add(
        org_id=org.id,
        incident_id=inc.id,
        status="succeeded",
        created_at=_BASE + dt.timedelta(minutes=5),
    )
    session.flush()

    succeeded_ids = {r["incident_id"] for r in repo.list_recent(org.id, status="succeeded")}
    failed_ids = {r["incident_id"] for r in repo.list_recent(org.id, status="failed")}

    # The latest run is 'succeeded', so the incident matches succeeded only.
    assert str(inc.id) in succeeded_ids
    assert str(inc.id) not in failed_ids

    # And the summary reflects the latest run's status.
    row = next(
        r for r in repo.list_recent(org.id, status="succeeded")
        if r["incident_id"] == str(inc.id)
    )
    assert row["run_status"] == "succeeded"


def test_status_filter_matches_latest_failed(session) -> None:
    org = OrganizationRepository(session).ensure("t-list-recent2", "List Recent Org 2")
    session.flush()
    repo = InvestigationRepository(session)

    # Incident whose latest run failed (a retry that did not recover).
    inc = _incident(repo, org.id, "LR-STILL-FAILING")
    repo.runs.add(
        org_id=org.id, incident_id=inc.id, status="succeeded", created_at=_BASE
    )
    repo.runs.add(
        org_id=org.id,
        incident_id=inc.id,
        status="failed",
        created_at=_BASE + dt.timedelta(minutes=5),
    )
    session.flush()

    failed_ids = {r["incident_id"] for r in repo.list_recent(org.id, status="failed")}
    succeeded_ids = {r["incident_id"] for r in repo.list_recent(org.id, status="succeeded")}
    assert str(inc.id) in failed_ids
    assert str(inc.id) not in succeeded_ids
