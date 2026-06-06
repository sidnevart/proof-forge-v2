"""add topic folders

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_folders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_topic_folders_user", "topic_folders", ["user_id"])
    op.add_column(
        "topics",
        sa.Column("folder_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_topics_folder_id",
        "topics", "topic_folders",
        ["folder_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_topics_folder_id", "topics", type_="foreignkey")
    op.drop_column("topics", "folder_id")
    op.drop_index("ix_topic_folders_user", table_name="topic_folders")
    op.drop_table("topic_folders")
