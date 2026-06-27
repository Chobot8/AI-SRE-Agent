"""Correlation (trace) IDs for incident diagnosis (KAN-12).

A correlation ID ties together every log line and metric emitted while handling a
single incident diagnosis (or HTTP request), so agent behaviour can be traced
end to end. The current ID lives in a ``contextvar`` so it is implicitly
available to logging without threading it through every function signature.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

_CORRELATION_ID: ContextVar[str | None] = ContextVar("correlation_id", default=None)

CORRELATION_HEADER = "X-Correlation-ID"


def new_correlation_id() -> str:
    """Return a fresh short correlation ID."""
    return uuid.uuid4().hex


def get_correlation_id() -> str | None:
    """Return the correlation ID bound to the current context, if any."""
    return _CORRELATION_ID.get()


def set_correlation_id(correlation_id: str) -> Token:
    """Bind a correlation ID to the current context; returns a reset token."""
    return _CORRELATION_ID.set(correlation_id)


def reset_correlation_id(token: Token) -> None:
    """Restore the previous correlation ID using a token from ``set``."""
    _CORRELATION_ID.reset(token)


@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation ID for the duration of the ``with`` block.

    Generates one when not provided. Yields the active ID and restores the
    previous value on exit.
    """
    cid = correlation_id or new_correlation_id()
    token = _CORRELATION_ID.set(cid)
    try:
        yield cid
    finally:
        _CORRELATION_ID.reset(token)
