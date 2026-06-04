"""web app tables: auth_tokens, web_events, capsule_feedback, user_streaks, card_sessions

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("token", sa.String(), nullable=False, unique=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_tokens_email", "auth_tokens", ["email"])
    op.create_index("ix_auth_tokens_token", "auth_tokens", ["token"])

    op.create_table(
        "web_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("referrer", sa.String(), nullable=True),
        sa.Column("device", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_web_events_session_id", "web_events", ["session_id"])
    op.create_index("ix_web_events_user_id", "web_events", ["user_id"])
    op.create_index("ix_web_events_event_type", "web_events", ["event_type"])
    op.create_index("ix_web_events_occurred_at", "web_events", ["occurred_at"])

    op.create_table(
        "capsule_feedback",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("capsule_id", sa.String(), sa.ForeignKey("capsules.id"), nullable=False),
        sa.Column("weak_spots", sa.JSON(), nullable=False),
        sa.Column("suggestions_md", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
    )
    op.create_index("ix_capsule_feedback_capsule_id", "capsule_feedback", ["capsule_id"])

    op.create_table(
        "user_streaks",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_review_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "card_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("cards_reviewed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_rating", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "session_date", name="uq_card_session_user_date"),
    )
    op.create_index("ix_card_sessions_user_id", "card_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_card_sessions_user_id", "card_sessions")
    op.drop_table("card_sessions")
    op.drop_table("user_streaks")
    op.drop_index("ix_capsule_feedback_capsule_id", "capsule_feedback")
    op.drop_table("capsule_feedback")
    op.drop_index("ix_web_events_occurred_at", "web_events")
    op.drop_index("ix_web_events_event_type", "web_events")
    op.drop_index("ix_web_events_user_id", "web_events")
    op.drop_index("ix_web_events_session_id", "web_events")
    op.drop_table("web_events")
    op.drop_index("ix_auth_tokens_token", "auth_tokens")
    op.drop_index("ix_auth_tokens_email", "auth_tokens")
    op.drop_table("auth_tokens")
