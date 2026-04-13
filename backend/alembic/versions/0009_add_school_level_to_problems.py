"""add school_level to problems

Revision ID: c5e995d403f6
Revises: 0008
Create Date: 2026-04-13 17:59:10.666355
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5e995d403f6"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("problems", sa.Column("school_level", sa.String(length=50), nullable=True))
    op.execute(
        """
        UPDATE problems
        SET school_level = SUBSTRING(source FROM '(초등학교|중학교|고등학교)')
        WHERE school_level IS NULL
          AND source IS NOT NULL
          AND source ~ '(초등학교|중학교|고등학교)'
        """
    )


def downgrade() -> None:
    op.drop_column("problems", "school_level")
