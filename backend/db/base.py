"""Declarative base for the ORM models (KAN-16).

All tables live in the configured Postgres schema (``sre`` by default), matching
infra/db/schema.sql.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

# Schema name is fixed at import time from settings (default "sre").
SCHEMA = get_settings().db_schema


class Base(DeclarativeBase):
    """Base class for all persistence models."""

    metadata = MetaData(schema=SCHEMA)
