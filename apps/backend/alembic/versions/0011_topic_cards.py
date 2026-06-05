"""add topic cards

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_cards",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("card_type", sa.String(), nullable=False, server_default="FLASHCARD"),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_topic_cards_user_due", "topic_cards", ["user_id", "next_review_at"])
    op.create_index("ix_topic_cards_topic_user", "topic_cards", ["topic_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_topic_cards_topic_user", table_name="topic_cards")
    op.drop_index("ix_topic_cards_user_due", table_name="topic_cards")
    op.drop_table("topic_cards")
