"""Health check endpoint.

Provides a lightweight liveness probe used by local dev, Docker health checks
(KAN-10), and uptime monitoring.
"""

from fastapi import APIRouter
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
