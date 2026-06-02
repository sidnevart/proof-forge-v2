"""add concept_mastery table

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "concept_mastery",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("concept", sa.String(), nullable=False),
        sa.Column("theory_reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("practice_reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("practice_quality", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_difficulty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("struggle_passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mastery_level", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "topic_id", "concept", name="uq_mastery_user_topic_concept"),
    )
    op.create_index("ix_concept_mastery_user_id", "concept_mastery", ["user_id"])
    op.create_index("ix_concept_mastery_topic_id", "concept_mastery", ["topic_id"])


def downgrade() -> None:
    op.drop_index("ix_concept_mastery_topic_id", "concept_mastery")
    op.drop_index("ix_concept_mastery_user_id", "concept_mastery")
    op.drop_table("concept_mastery")
