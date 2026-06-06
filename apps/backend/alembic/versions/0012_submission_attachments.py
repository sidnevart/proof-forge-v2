"""add submission attachments

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission_attachments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("submission_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False, server_default="application/octet-stream"),
        sa.Column("kind", sa.String(), nullable=False, server_default="text"),
        sa.Column("content_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("data_b64", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["ide_submissions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_submission_attachments_submission",
        "submission_attachments",
        ["submission_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_submission_attachments_submission", table_name="submission_attachments")
    op.drop_table("submission_attachments")
