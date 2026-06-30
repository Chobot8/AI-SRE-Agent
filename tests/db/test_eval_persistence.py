"""DB-backed test for evaluation persistence (KAN-20).

Persists a real evaluation run and reads back the run + per-scenario rows. Skips
cleanly when no PostgreSQL is reachable, and cleans up the run it creates.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        return False
    try:
        from backend.db import session as db_session

        db_session.reset_engine()
        db_session.check_connection()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_ready(), reason="No reachable PostgreSQL")


@requires_db
def test_persist_report_writes_run_and_results() -> None:
    import uuid

    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope
    from backend.evaluation.persistence import persist_report
    from backend.evaluation.runner import run_evaluation
    from backend.scenarios import loader

    slugs = loader.list_packs()[:2]
    report = run_evaluation(slugs)

    run_id = persist_report(report)
    assert run_id is not None
    rid = uuid.UUID(run_id)

    try:
        with session_scope() as session:
            run = session.get(models.EvaluationRun, rid)
            assert run is not None
            assert run.total_scenarios == len(slugs)
            assert run.passed + run.failed == len(slugs)
            assert run.status == "completed"

            results = session.scalars(
                select(models.EvaluationResult).where(
                    models.EvaluationResult.evaluation_run_id == rid
                )
            ).all()
            assert len(results) == len(slugs)
            assert {r.scenario for r in results} == set(slugs)
    finally:
        # Clean up the run (cascades to results).
        with session_scope() as session:
            run = session.get(models.EvaluationRun, rid)
            if run is not None:
                session.delete(run)
