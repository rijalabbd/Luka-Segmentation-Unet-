"""create visits table

Revision ID: 0002_create_visits
Revises: 0001_create_patients
Create Date: 2026-11-07 12:56:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_create_visits"
down_revision: Union[str, None] = "0001_create_patients"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.String(length=20), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("visit_index", sa.Integer(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("mask_path", sa.String(length=255), nullable=True),
        sa.Column("n_wound_px", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("area_pct", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("delta_area", sa.Float(), nullable=True),
        sa.Column("pac", sa.Float(), nullable=True),
        sa.Column("trend_status", sa.String(length=64), nullable=True),
        sa.Column("clinician_notes", sa.Text(), nullable=True),
        sa.Column("patient_narrative", sa.Text(), nullable=True),
        sa.Column("narrative_source", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.rm_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_visits_patient_id"), "visits", ["patient_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_visits_patient_id"), table_name="visits")
    op.drop_table("visits")

