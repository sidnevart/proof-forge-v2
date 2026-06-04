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
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("conspect_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("learning_goals", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_study_sessions_user_topic", "study_sessions", ["user_id", "topic_id"])

    op.create_table(
        "practice_tasks",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic_id", sa.String(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("study_session_id", sa.String(), sa.ForeignKey("study_sessions.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("instructions_md", sa.Text(), nullable=False),
        sa.Column("target_concepts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expected_evidence", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("check_commands", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(), nullable=False, server_default="assigned"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_practice_tasks_user_status", "practice_tasks", ["user_id", "status"])
    op.create_index("ix_practice_tasks_session", "practice_tasks", ["study_session_id"])

    op.create_table(
        "ide_sessions",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ide", sa.String(), nullable=False, server_default="jetbrains"),
        sa.Column("ide_product", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("plugin_version", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("paired_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ide_sessions_user_id", "ide_sessions", ["user_id"])

    op.create_table(
        "ide_submissions",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("practice_task_id", sa.String(), sa.ForeignKey("practice_tasks.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ide_session_id", sa.String(), sa.ForeignKey("ide_sessions.id"), nullable=True),
        sa.Column("files", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("diff", sa.Text(), nullable=False, server_default=""),
        sa.Column("test_output", sa.Text(), nullable=False, server_default=""),
        sa.Column("check_command", sa.Text(), nullable=False, server_default=""),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("reflection", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ide_submissions_task", "ide_submissions", ["practice_task_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("ide_submissions.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="needs_revision"),
        sa.Column("feedback_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("concept_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("weak_spots", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("next_action", sa.String(), nullable=False, server_default="revise"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluations_submission", "evaluations", ["submission_id"])

    op.create_table(
        "follow_ups",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("evaluation_id", sa.String(), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback_md", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_follow_ups_evaluation_id", "follow_ups", ["evaluation_id"])


def downgrade() -> None:
    op.drop_index("ix_follow_ups_evaluation_id", table_name="follow_ups")
    op.drop_index("ix_evaluations_submission", table_name="evaluations")
    op.drop_index("ix_ide_submissions_task", table_name="ide_submissions")
    op.drop_index("ix_ide_sessions_user_id", table_name="ide_sessions")
    op.drop_index("ix_practice_tasks_session", table_name="practice_tasks")
    op.drop_index("ix_practice_tasks_user_status", table_name="practice_tasks")
    op.drop_index("ix_study_sessions_user_topic", table_name="study_sessions")
    op.drop_table("follow_ups")
    op.drop_table("evaluations")
    op.drop_table("ide_submissions")
    op.drop_table("ide_sessions")
    op.drop_table("practice_tasks")
    op.drop_table("study_sessions")
