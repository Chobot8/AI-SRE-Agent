"""Engine and session setup for the persistence layer (KAN-16).

Sync SQLAlchemy (psycopg3). The engine is created lazily so the app and tests
import cleanly even when no database is configured. Connection problems surface
as a clear ``DatabaseConnectionError`` — and error messages never include the
DSN, which contains the password.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a DB operation is attempted but DATABASE_URL is unset."""


class DatabaseConnectionError(RuntimeError):
    """Raised when the database cannot be reached (clear, secret-free message)."""


_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def _build_engine() -> Engine:
    settings = get_settings()
    if not settings.database_url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not set. Copy .env.example to .env (or set the "
            "environment variable) to enable the persistence layer."
        )
    return create_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        future=True,
        # Resolve unqualified names to the agent schema first.
        connect_args={"options": f"-csearch_path={settings.db_schema},public"},
    )


def get_engine() -> Engine:
    """Return the process-wide engine, building it on first use."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    """Return the process-wide session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), expire_on_commit=False, future=True
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on error, always close."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a session (caller controls the commit)."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_connection() -> None:
    """Ping the database, raising a clear error if it is unreachable.

    Re-raises ``DatabaseNotConfiguredError`` as-is; wraps any driver/connection
    failure in ``DatabaseConnectionError`` without exposing the DSN.
    """
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except DatabaseNotConfiguredError:
        raise
    except SQLAlchemyError as exc:  # pragma: no cover - needs a live database
        raise DatabaseConnectionError(
            f"Could not connect to the database ({type(exc).__name__}). "
            "Check that PostgreSQL is running and DATABASE_URL host/port are correct."
        ) from exc


def reset_engine() -> None:
    """Dispose and clear the cached engine/session factory (used by tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
