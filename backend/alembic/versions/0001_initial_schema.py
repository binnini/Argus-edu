"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # problems
    op.create_table(
        "problems",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("answer", sa.String(100), nullable=False),
        sa.Column("reference_solution", sa.Text(), nullable=False),
        sa.Column("rubric", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("domain", sa.String(50), server_default="수학2"),
        sa.Column("difficulty", sa.SmallInteger(), sa.CheckConstraint("difficulty BETWEEN 1 AND 5")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # submissions
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("student_answer", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_submissions_status", "submissions", ["status"])

    # grading_results
    op.create_table(
        "grading_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("ai_score", sa.SmallInteger(), nullable=False),
        sa.Column("ai_explanation", sa.Text(), nullable=False),
        sa.Column("sbert_similarity", sa.Float(), nullable=False),
        sa.Column("hhem_score", sa.Float(), nullable=False),
        sa.Column("inconsistency_rate", sa.Float(), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False),
        sa.Column("trust_level", sa.String(10), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )

    # teacher_queue
    op.create_table(
        "teacher_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("queue_type", sa.String(20), nullable=False),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(10), nullable=True),
        sa.Column("teacher_score", sa.SmallInteger(), nullable=True),
        sa.Column("teacher_explanation", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_index(
        "idx_teacher_queue_action_null",
        "teacher_queue",
        ["queued_at"],
        postgresql_where=sa.text("action IS NULL"),
    )
    op.create_index(
        "idx_teacher_queue_sla",
        "teacher_queue",
        ["sla_deadline"],
        postgresql_where=sa.text("action IS NULL"),
    )

    # feedback_log
    op.create_table(
        "feedback_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("ai_score", sa.SmallInteger(), nullable=False),
        sa.Column("teacher_score", sa.SmallInteger(), nullable=False),
        sa.Column(
            "score_delta",
            sa.SmallInteger(),
            sa.Computed("teacher_score - ai_score", persisted=True),
        ),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False),
        sa.Column("trust_level", sa.String(10), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_feedback_log_logged_at", "feedback_log", ["logged_at"])


def downgrade() -> None:
    op.drop_index("idx_feedback_log_logged_at", table_name="feedback_log")
    op.drop_table("feedback_log")
    op.drop_index("idx_teacher_queue_sla", table_name="teacher_queue")
    op.drop_index("idx_teacher_queue_action_null", table_name="teacher_queue")
    op.drop_table("teacher_queue")
    op.drop_table("grading_results")
    op.drop_index("idx_submissions_status", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("problems")
