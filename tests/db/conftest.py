"""Shared fixtures for persistence tests (KAN-16).

These tests need a live PostgreSQL with the schema applied (run the migration or
the compose db init first, and set DATABASE_URL — for host-local runs use the
localhost host). When no database is reachable the whole package is skipped, so
the suite stays green in CI environments without Postgres.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")

from sqlalchemy.orm import Session  # noqa: E402

from backend.db import session as db_session  # noqa: E402


@pytest.fixture
def session() -> Iterator[Session]:
    """A session wrapped in a transaction that is rolled back after each test.

    Skips the test when no database is reachable (keeps CI green without
    Postgres). Nothing the test writes is persisted, so tests are isolated and
    leave no residue in the database.
    """
    try:
        db_session.reset_engine()
        db_session.check_connection()
    except Exception as exc:  # noqa: BLE001 - any failure means "no DB, skip"
        pytest.skip(f"No reachable PostgreSQL: {type(exc).__name__}")

    engine = db_session.get_engine()
    connection = engine.connect()
    transaction = connection.begin()
    sess = Session(bind=connection, expire_on_commit=False)
    try:
        yield sess
    finally:
        sess.close()
        transaction.rollback()
        connection.close()
