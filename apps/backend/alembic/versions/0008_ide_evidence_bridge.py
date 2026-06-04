"""ide evidence bridge tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("conspect_md", sa.Text(), server_default=""),
        sa.Column("learning_goals", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_study_sessions_user_topic", "study_sessions", ["user_id", "topic_id"])

    op.create_table(
        "practice_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("instructions_md", sa.Text(), nullable=False),
        sa.Column("target_concepts", sa.JSON(), server_default="[]"),
        sa.Column("difficulty", sa.Integer(), server_default="1"),
        sa.Column("expected_evidence", sa.JSON(), server_default="[]"),
        sa.Column("check_commands", sa.JSON(), server_default="[]"),
        sa.Column("status", sa.String(), server_default="assigned"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_practice_tasks_user_status", "practice_tasks", ["user_id", "status"])
    op.create_index("ix_practice_tasks_session", "practice_tasks", ["study_session_id"])

    op.create_table(
        "ide_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ide", sa.String(), server_default="jetbrains"),
        sa.Column("ide_product", sa.String(), server_default="unknown"),
        sa.Column("plugin_version", sa.String(), server_default="unknown"),
        sa.Column("paired_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ide_sessions_user_id", "ide_sessions", ["user_id"])

    op.create_table(
        "ide_submissions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("practice_task_id", sa.String(), sa.ForeignKey("practice_tasks.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ide_session_id", sa.String(), sa.ForeignKey("ide_sessions.id"), nullable=True),
        sa.Column("files", sa.JSON(), server_default="[]"),
        sa.Column("diff", sa.Text(), server_default=""),
        sa.Column("test_output", sa.Text(), server_default=""),
        sa.Column("check_command", sa.Text(), server_default=""),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("reflection", sa.Text(), server_default=""),
        sa.Column("language", sa.String(), server_default="unknown"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ide_submissions_task", "ide_submissions", ["practice_task_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("ide_submissions.id"), nullable=False),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.Column("status", sa.String(), server_default="needs_revision"),
        sa.Column("feedback_md", sa.Text(), server_default=""),
        sa.Column("concept_scores", sa.JSON(), server_default="{}"),
        sa.Column("weak_spots", sa.JSON(), server_default="[]"),
        sa.Column("next_action", sa.String(), server_default="revise"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evaluations_submission", "evaluations", ["submission_id"])

    op.create_table(
        "follow_ups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("evaluation_id", sa.String(), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), server_default=""),
        sa.Column("user_answer", sa.Text(), server_default=""),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback_md", sa.Text(), server_default=""),
    )


def downgrade() -> None:
    op.drop_table("follow_ups")
    op.drop_table("evaluations")
    op.drop_table("ide_submissions")
    op.drop_table("ide_sessions")
    op.drop_table("practice_tasks")
    op.drop_table("study_sessions")
