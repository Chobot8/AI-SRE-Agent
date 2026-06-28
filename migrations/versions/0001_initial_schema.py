"""initial schema from infra/db/schema.sql (KAN-16)

Creates the full ``sre`` persistence schema from an empty database by executing
the canonical, reviewed DDL in infra/db/schema.sql (single source of truth,
shared with the docker-compose db init mount).

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-28
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# migrations/versions/0001_*.py -> parents[2] is the repo root.
_SCHEMA_SQL = Path(__file__).resolve().parents[2] / "infra" / "db" / "schema.sql"


def upgrade() -> None:
    sql = _SCHEMA_SQL.read_text(encoding="utf-8")
    # Alembic runs this inside its own transaction; drop the file's own outer
    # BEGIN;/COMMIT; (the plpgsql function body uses BEGIN/END without ';').
    sql = sql.replace("BEGIN;", "").replace("COMMIT;", "")
    op.execute(sql)


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS sre CASCADE")
