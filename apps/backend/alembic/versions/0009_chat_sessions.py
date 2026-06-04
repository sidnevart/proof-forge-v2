"""chat sessions and messages

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_sessions_user", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_study", "chat_sessions", ["study_session_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_session", "chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_study", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user", table_name="chat_sessions")
    op.drop_table("chat_sessions")
