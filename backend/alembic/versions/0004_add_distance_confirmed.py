"""add distance_confirmed column to visits

Revision ID: 0004_add_distance_confirmed
Revises: 0003_visit_unique_constraints
Create Date: 2026-11-07 20:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_add_distance_confirmed"
down_revision: Union[str, None] = "0003_visit_unique_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column(
            "distance_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(sa.text("UPDATE visits SET distance_confirmed = true WHERE distance_confirmed IS NULL"))
    op.alter_column("visits", "distance_confirmed", server_default=None)


def downgrade() -> None:
    op.drop_column("visits", "distance_confirmed")

