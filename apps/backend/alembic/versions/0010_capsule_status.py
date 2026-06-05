"""add status to capsules

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capsules",
        sa.Column("status", sa.String(), nullable=False, server_default="ready"),
    )


def downgrade() -> None:
    op.drop_column("capsules", "status")
