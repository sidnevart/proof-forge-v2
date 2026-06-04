"""topic_materials table

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_materials",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("content_text", sa.Text(), server_default=""),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_topic_materials_topic_id", "topic_materials", ["topic_id"])
    op.create_index("ix_topic_materials_user_id", "topic_materials", ["user_id"])


def downgrade() -> None:
    op.drop_table("topic_materials")
