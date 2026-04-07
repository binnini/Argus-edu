"""Phase 7 redesign: OCR fields, feedback rename, source column

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # submissions: OCR 관련 컬럼 추가
    op.add_column(
        "submissions",
        sa.Column("input_type", sa.String(10), server_default="text", nullable=False),
    )
    op.add_column(
        "submissions",
        sa.Column("ocr_raw_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "submissions",
        sa.Column("image_path", sa.String(500), nullable=True),
    )

    # grading_results: ai_explanation → ai_feedback rename
    op.alter_column("grading_results", "ai_explanation", new_column_name="ai_feedback")

    # teacher_queue: teacher_explanation → teacher_feedback rename
    op.alter_column("teacher_queue", "teacher_explanation", new_column_name="teacher_feedback")

    # problems: source 컬럼 추가
    op.add_column(
        "problems",
        sa.Column("source", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("problems", "source")

    op.alter_column("teacher_queue", "teacher_feedback", new_column_name="teacher_explanation")
    op.alter_column("grading_results", "ai_feedback", new_column_name="ai_explanation")

    op.drop_column("submissions", "image_path")
    op.drop_column("submissions", "ocr_raw_text")
    op.drop_column("submissions", "input_type")
