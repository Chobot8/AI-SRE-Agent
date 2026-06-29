"""Health check endpoint.

Provides a lightweight liveness probe used by local dev, Docker health checks
(KAN-10), and uptime monitoring.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import __version__
from backend.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Schema for the health endpoint response."""

    status: str
    service: str
    version: str
    environment: str


class DbReadyResponse(BaseModel):
    """Schema for the database readiness probe."""

    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service liveness information."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
    )


@router.get("/health/db", response_model=DbReadyResponse)
def health_db() -> DbReadyResponse:
    """Readiness probe for the persistence layer (KAN-16).

    Returns 200 when the database is reachable; 503 with a clear, secret-free
    message when it is not (or 500 if DATABASE_URL is unset).
    """
    # Imported lazily so the app still runs when the DB layer is unconfigured.
    from backend.db.session import (
        DatabaseConnectionError,
        DatabaseNotConfiguredError,
        check_connection,
    )

    try:
        check_connection()
    except DatabaseNotConfiguredError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return DbReadyResponse(status="ok", database="reachable")
