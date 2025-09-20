"""Create baseline memory schema

Revision ID: 0001_create_memory_schema
Revises: 
Create Date: 2024-10-07 00:00:00

"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0001_create_memory_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY,
            kind TEXT,
            text TEXT,
            vec BLOB,
            ts REAL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_kind_ts ON items(kind, ts)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY,
            kind TEXT,
            prompt TEXT,
            answer TEXT,
            rating REAL,
            ts REAL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feedback")
    op.execute("DROP INDEX IF EXISTS idx_items_kind_ts")
    op.execute("DROP TABLE IF EXISTS items")
