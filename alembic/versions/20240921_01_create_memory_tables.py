"""Create initial memory tables

Revision ID: 20240921_01
Revises: None
Create Date: 2024-09-21 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20240921_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("vec", sa.LargeBinary(), nullable=False),
        sa.Column("ts", sa.Float(), nullable=False),
    )
    op.create_index("idx_items_kind_ts", "items", ["kind", "ts"])
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("ts", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_index("idx_items_kind_ts", table_name="items")
    op.drop_table("items")
