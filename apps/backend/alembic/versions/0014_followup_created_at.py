"""add created_at to follow_ups for deterministic ordering

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills existing rows; the ORM supplies the value going forward.
    op.add_column(
        "follow_ups",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("follow_ups", "created_at")
