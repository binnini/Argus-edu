"""add student_name, student_id to submissions; soft_deleted to problems

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-10

변경 내용:
- submissions.student_name VARCHAR(50) NOT NULL DEFAULT ''
- submissions.student_id VARCHAR(20) NULLABLE
- problems.soft_deleted BOOLEAN DEFAULT FALSE NOT NULL
- idx_submissions_student_name ON submissions(student_name)
- idx_submissions_problem_id ON submissions(problem_id)
- idx_problems_not_deleted ON problems(id) WHERE soft_deleted = FALSE
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # submissions 테이블 컬럼 추가
    op.add_column(
        "submissions",
        sa.Column("student_name", sa.String(50), nullable=False, server_default=""),
    )
    op.add_column(
        "submissions",
        sa.Column("student_id", sa.String(20), nullable=True),
    )

    # problems 테이블 컬럼 추가
    op.add_column(
        "problems",
        sa.Column(
            "soft_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # 인덱스 생성
    op.create_index(
        "idx_submissions_student_name",
        "submissions",
        ["student_name"],
    )
    op.create_index(
        "idx_submissions_problem_id",
        "submissions",
        ["problem_id"],
    )
    op.create_index(
        "idx_problems_not_deleted",
        "problems",
        ["id"],
        postgresql_where=sa.text("soft_deleted = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_problems_not_deleted", table_name="problems")
    op.drop_index("idx_submissions_problem_id", table_name="submissions")
    op.drop_index("idx_submissions_student_name", table_name="submissions")
    op.drop_column("problems", "soft_deleted")
    op.drop_column("submissions", "student_id")
    op.drop_column("submissions", "student_name")
