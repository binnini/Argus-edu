"""extend column limits for full-grade data

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-07

전과정(초·중·고) 데이터 삽입 시 발생한 VARCHAR 길이 초과 오류 수정.
- problems.answer: VARCHAR(100) → TEXT
- problems.domain: VARCHAR(50) → VARCHAR(200)
- problems.title: VARCHAR(200) → VARCHAR(500)
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "problems",
        "answer",
        type_=sa.Text(),
        existing_type=sa.String(100),
        nullable=True,
    )
    op.alter_column(
        "problems",
        "domain",
        type_=sa.String(200),
        existing_type=sa.String(50),
        nullable=True,
    )
    op.alter_column(
        "problems",
        "title",
        type_=sa.String(500),
        existing_type=sa.String(200),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "problems",
        "answer",
        type_=sa.String(100),
        existing_type=sa.Text(),
        nullable=True,
    )
    op.alter_column(
        "problems",
        "domain",
        type_=sa.String(50),
        existing_type=sa.String(200),
        nullable=True,
    )
    op.alter_column(
        "problems",
        "title",
        type_=sa.String(200),
        existing_type=sa.String(500),
        nullable=False,
    )
