"""0010 add students table

Revision ID: 0010
Revises: c5e995d403f6
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "c5e995d403f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.String(length=20), nullable=False),
        sa.Column("student_name", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_students_student_id", "students", ["student_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_students_student_id", table_name="students")
    op.drop_table("students")
