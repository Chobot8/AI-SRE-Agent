"""Connection-failure handling returns a clear, secret-free error (KAN-16).

Does not need a live database — only the drivers — so it runs in CI.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")

from backend.config import Settings  # noqa: E402
from backend.db import session as db_session  # noqa: E402


def test_connection_failure_raises_clear_error(monkeypatch) -> None:
    # Point at a closed port so the connection fails fast.
    bad = Settings(database_url="postgresql+psycopg://u:secretpw@127.0.0.1:1/nope")
    monkeypatch.setattr(db_session, "get_settings", lambda: bad)
    db_session.reset_engine()
    try:
        with pytest.raises(db_session.DatabaseConnectionError) as err:
            db_session.check_connection()
        # The DSN/password must never appear in the error message.
        assert "secretpw" not in str(err.value)
    finally:
        db_session.reset_engine()


def test_database_not_configured_error(monkeypatch) -> None:
    monkeypatch.setattr(db_session, "get_settings", lambda: Settings(database_url=None))
    db_session.reset_engine()
    try:
        with pytest.raises(db_session.DatabaseNotConfiguredError):
            db_session.check_connection()
    finally:
        db_session.reset_engine()
