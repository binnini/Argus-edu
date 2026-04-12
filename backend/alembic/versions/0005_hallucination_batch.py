"""0005 — grading_results: HHEM 컬럼 제거, 배치 할루시네이션 컬럼 추가 (ADR-026)

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 HHEM/inconsistency 컬럼 제거
    op.drop_column("grading_results", "hhem_score")
    op.drop_column("grading_results", "inconsistency_rate")

    # 배치 LLM 할루시네이션 검증 컬럼 추가
    op.add_column(
        "grading_results",
        sa.Column("hallucination_status", sa.String(10), nullable=False, server_default="pending"),
    )
    op.add_column(
        "grading_results",
        sa.Column("hallucination_score", sa.Float, nullable=True),
    )
    op.add_column(
        "grading_results",
        sa.Column("hallucination_issues", sa.Text, nullable=True),
    )
    op.add_column(
        "grading_results",
        sa.Column("hallucination_checked_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 기존 행은 pending 상태로 설정
    op.execute("UPDATE grading_results SET hallucination_status = 'pending'")


def downgrade() -> None:
    op.drop_column("grading_results", "hallucination_checked_at")
    op.drop_column("grading_results", "hallucination_issues")
    op.drop_column("grading_results", "hallucination_score")
    op.drop_column("grading_results", "hallucination_status")

    op.add_column(
        "grading_results",
        sa.Column("hhem_score", sa.Float, nullable=True),
    )
    op.add_column(
        "grading_results",
        sa.Column("inconsistency_rate", sa.Float, nullable=False, server_default="0.0"),
    )
