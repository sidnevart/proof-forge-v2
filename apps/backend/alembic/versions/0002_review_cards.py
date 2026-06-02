"""add review_cards table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_cards",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("question_id", sa.String(), sa.ForeignKey("review_questions.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_cards_user_id", "review_cards", ["user_id"])
    op.create_index("ix_review_cards_next_review_at", "review_cards", ["next_review_at"])


def downgrade() -> None:
    op.drop_index("ix_review_cards_next_review_at", "review_cards")
    op.drop_index("ix_review_cards_user_id", "review_cards")
    op.drop_table("review_cards")
