"""Generic repository base (KAN-16)."""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Minimal create/read access for one model.

    ``add`` flushes so the generated id is available immediately, but does not
    commit — the caller (or ``session_scope``) owns the transaction boundary.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, **fields: Any) -> ModelT:
        obj = self.model(**fields)
        self.session.add(obj)
        self.session.flush()
        return obj

    def get(self, id_: uuid.UUID) -> ModelT | None:
        return self.session.get(self.model, id_)

    def list_by(self, **filters: Any) -> list[ModelT]:
        stmt = select(self.model).filter_by(**filters)
        return list(self.session.scalars(stmt))
