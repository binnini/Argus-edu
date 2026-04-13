"""0007 — durable jobs and feedback status

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "grading_results",
        sa.Column("feedback_status", sa.String(10), nullable=False, server_default="pending"),
    )
    op.add_column("grading_results", sa.Column("solution_status", sa.String(40), nullable=True))
    op.add_column("grading_results", sa.Column("answer_verdict", sa.String(20), nullable=True))

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(80), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_submission_id", "jobs", ["submission_id"])
    op.create_index("ix_jobs_status_priority", "jobs", ["status", "priority", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status_priority", table_name="jobs")
    op.drop_index("ix_jobs_submission_id", table_name="jobs")
    op.drop_table("jobs")

    op.drop_column("grading_results", "answer_verdict")
    op.drop_column("grading_results", "solution_status")
    op.drop_column("grading_results", "feedback_status")
