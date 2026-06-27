"""FastAPI application entry point for the AI SRE Agent.

Run locally:
    uvicorn backend.main:app --reload

Interactive docs are then available at http://localhost:8000/docs

Observability (KAN-12): logging is configured on startup, every request runs
under a correlation ID and is recorded as a metric, and Prometheus-format
metrics are exposed at ``GET /metrics``.
"""

import time

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from backend import __version__
from backend.api.routes import diagnosis, health
from backend.config import get_settings
from backend.observability import (
    CONTENT_TYPE,
    CORRELATION_HEADER,
    METRICS,
    configure_logging,
    get_logger,
    log_event,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

settings = get_settings()
configure_logging(settings.log_level, settings.log_format)
_log = get_logger("api")

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "An AI Site Reliability Engineering agent that detects, explains, and "
        "recommends actions for common service incidents."
    ),
)


def _endpoint_label(request: Request) -> str:
    """Prefer the matched route template (low cardinality) over the raw path."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Bind a correlation ID, time the request, and record request metrics."""
    correlation_id = request.headers.get(CORRELATION_HEADER) or new_correlation_id()
    token = set_correlation_id(correlation_id)
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed = time.perf_counter() - start
        endpoint = _endpoint_label(request)
        METRICS.requests_total.inc(
            endpoint=endpoint, method=request.method, status=str(status_code)
        )
        METRICS.request_latency_seconds.observe(elapsed, endpoint=endpoint)
        if status_code >= 500:
            METRICS.request_failures_total.inc(endpoint=endpoint)
        log_event(
            _log,
            "request.handled",
            method=request.method,
            endpoint=endpoint,
            status=status_code,
            duration_ms=round(elapsed * 1000, 2),
        )
        if "response" in locals():
            response.headers[CORRELATION_HEADER] = correlation_id
        reset_correlation_id(token)


@app.get("/metrics", include_in_schema=False)
def metrics() -> PlainTextResponse:
    """Expose agent metrics in Prometheus text exposition format."""
    return PlainTextResponse(METRICS.render(), media_type=CONTENT_TYPE)


app.include_router(health.router)
app.include_router(diagnosis.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Basic service metadata."""
    return {
        "service": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
        "docs": "/docs",
    }
