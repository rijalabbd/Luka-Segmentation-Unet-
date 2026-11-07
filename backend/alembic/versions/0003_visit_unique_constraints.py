"""add unique constraints for visit_index and single active draft per patient

Revision ID: 0003_visit_unique_constraints
Revises: 0002_create_visits
Create Date: 2026-11-07 13:15:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_visit_unique_constraints"
down_revision: Union[str, None] = "0002_create_visits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pastikan kolom legacy baseline_wound_px dan latest_wound_px (jika pernah ada pada DB lama) dihapus
    op.execute(
        "ALTER TABLE patients DROP COLUMN IF EXISTS baseline_wound_px, DROP COLUMN IF EXISTS latest_wound_px;"
    )

    op.create_unique_constraint(
        "uq_visits_patient_visit_index",
        "visits",
        ["patient_id", "visit_index"],
    )
    op.create_index(
        "uq_visits_one_draft_per_patient",
        "visits",
        ["patient_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )


def downgrade() -> None:
    op.drop_index("uq_visits_one_draft_per_patient", table_name="visits")
    op.drop_constraint("uq_visits_patient_visit_index", "visits", type_="unique")

