"""Structured logging for the agent (KAN-12).

Emits one JSON object per log line to stdout (so logs are greppable locally and
visible via ``docker compose logs``). Every line carries the active correlation
ID, and a redaction step keeps secrets (API keys, tokens, passwords) out of the
output even if they are accidentally passed as structured fields.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from backend.observability.correlation import get_correlation_id

LOGGER_ROOT = "agent"

# Substrings that mark a field name as sensitive; its value is never logged.
_SECRET_HINTS = ("key", "token", "secret", "password", "authorization", "credential")
_REDACTED = "***"

# Standard LogRecord attributes we never copy into the structured payload.
_RESERVED = set(
    vars(logging.makeLogRecord({})).keys()
) | {"message", "asctime", "extra_fields"}


def _is_secret(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _SECRET_HINTS)


def redact(fields: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``fields`` with secret-looking values masked."""
    clean: dict[str, Any] = {}
    for name, value in fields.items():
        if _is_secret(name):
            clean[name] = _REDACTED
        elif isinstance(value, dict):
            clean[name] = redact(value)
        else:
            clean[name] = value
    return clean


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON with the correlation ID."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        correlation_id = get_correlation_id()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(redact(extra))

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure the ``agent`` logger. Idempotent (safe under uvicorn reload)."""
    logger = logging.getLogger(LOGGER_ROOT)
    logger.setLevel(level.upper())
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "text":
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a child of the ``agent`` logger (e.g. ``agent.service``)."""
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log a structured event: a stable ``event`` name plus redacted fields."""
    logger.log(level, event, extra={"extra_fields": fields})
