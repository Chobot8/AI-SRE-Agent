"""Agent observability: structured logs, metrics, and correlation IDs (KAN-12)."""

from __future__ import annotations

from backend.observability.correlation import (
    CORRELATION_HEADER,
    correlation_context,
    get_correlation_id,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from backend.observability.logging import (
    configure_logging,
    get_logger,
    log_event,
    redact,
)
from backend.observability.metrics import CONTENT_TYPE, METRICS

__all__ = [
    "CORRELATION_HEADER",
    "correlation_context",
    "get_correlation_id",
    "new_correlation_id",
    "reset_correlation_id",
    "set_correlation_id",
    "configure_logging",
    "get_logger",
    "log_event",
    "redact",
    "METRICS",
    "CONTENT_TYPE",
]
