"""add chat attachments

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_attachments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False, server_default="application/octet-stream"),
        sa.Column("kind", sa.String(), nullable=False, server_default="text"),
        sa.Column("content_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("data_b64", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_attachments_message",
        "chat_attachments",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_attachments_message", table_name="chat_attachments")
    op.drop_table("chat_attachments")
