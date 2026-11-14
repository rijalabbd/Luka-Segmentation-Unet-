"""add calibration and dual-mode columns to visits

Revision ID: 0006_add_calibration_columns
Revises: 0005_add_confirm_zero_area
Create Date: 2026-11-14 09:50:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_calibration_columns"
down_revision: Union[str, None] = "0005_add_confirm_zero_area"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column(
            "measure_mode",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'relative'"),
        ),
    )
    op.execute(sa.text("UPDATE visits SET measure_mode = 'relative' WHERE measure_mode IS NULL"))
    op.alter_column("visits", "measure_mode", server_default=None)

    op.add_column("visits", sa.Column("img_width_px", sa.Integer(), nullable=True))
    op.add_column("visits", sa.Column("img_height_px", sa.Integer(), nullable=True))
    op.add_column("visits", sa.Column("calib_x1", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("calib_y1", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("calib_x2", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("calib_y2", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("calib_length_cm", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("scale_cm_per_px", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("area_cm2", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("pac_rel", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("pac_cm2", sa.Float(), nullable=True))
    op.add_column("visits", sa.Column("pac_basis", sa.String(length=16), nullable=True))
    op.add_column("visits", sa.Column("warnings", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("visits", "warnings")
    op.drop_column("visits", "pac_basis")
    op.drop_column("visits", "pac_cm2")
    op.drop_column("visits", "pac_rel")
    op.drop_column("visits", "area_cm2")
    op.drop_column("visits", "scale_cm_per_px")
    op.drop_column("visits", "calib_length_cm")
    op.drop_column("visits", "calib_y2")
    op.drop_column("visits", "calib_x2")
    op.drop_column("visits", "calib_y1")
    op.drop_column("visits", "calib_x1")
    op.drop_column("visits", "img_height_px")
    op.drop_column("visits", "img_width_px")
    op.drop_column("visits", "measure_mode")
