"""add nullable title to capsules (for rename)

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("capsules", sa.Column("title", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("capsules", "title")
