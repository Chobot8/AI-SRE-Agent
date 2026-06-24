"""FastAPI application entry point for the AI SRE Agent.

Run locally:
    uvicorn backend.main:app --reload

Interactive docs are then available at http://localhost:8000/docs
"""

from fastapi import FastAPI

from backend import __version__
from backend.api.routes import health
from backend.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "An AI Site Reliability Engineering agent that detects, explains, and "
        "recommends actions for common service incidents."
    ),
)

app.include_router(health.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Basic service metadata."""
    return {
        "service": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
        "docs": "/docs",
    }
