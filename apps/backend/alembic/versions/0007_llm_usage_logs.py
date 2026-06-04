"""llm_usage_logs table

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("call_type", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=True),
        sa.Column("capsule_id", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), server_default="0"),
        sa.Column("total_tokens", sa.Integer(), server_default="0"),
        sa.Column("cost_usd", sa.Float(), server_default="0"),
        sa.Column("latency_ms", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(), server_default="success"),
        sa.Column("error_msg", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_llm_usage_logs_user_id", "llm_usage_logs", ["user_id"])
    op.create_index("ix_llm_usage_logs_created_at", "llm_usage_logs", ["created_at"])
    op.create_index("ix_llm_usage_logs_call_type", "llm_usage_logs", ["call_type"])


def downgrade() -> None:
    op.drop_table("llm_usage_logs")
