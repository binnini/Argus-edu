"""add feedback_completed_at to grading_results

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "grading_results",
        sa.Column("feedback_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE grading_results
        SET feedback_completed_at = graded_at
        WHERE feedback_status = 'done' AND feedback_completed_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("grading_results", "feedback_completed_at")
