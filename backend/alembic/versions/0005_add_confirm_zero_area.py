"""add confirm_zero_area column to visits

Revision ID: 0005_add_confirm_zero_area
Revises: 0004_add_distance_confirmed
Create Date: 2026-11-07 22:36:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_add_confirm_zero_area"
down_revision: Union[str, None] = "0004_add_distance_confirmed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column(
            "confirm_zero_area",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(
        sa.text("UPDATE visits SET confirm_zero_area = false WHERE confirm_zero_area IS NULL")
    )
    op.alter_column("visits", "confirm_zero_area", server_default=None)


def downgrade() -> None:
    op.drop_column("visits", "confirm_zero_area")
