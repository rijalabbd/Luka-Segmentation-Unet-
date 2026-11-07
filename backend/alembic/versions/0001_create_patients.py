"""create patients table

Revision ID: 0001_create_patients
Revises: None
Create Date: 2026-11-07 12:55:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_create_patients"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("rm_code", sa.String(length=20), nullable=False),
        sa.Column("name_initial", sa.String(length=100), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("ulcer_location", sa.String(length=120), nullable=True),
        sa.Column("informed_consent", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("rm_code"),
    )
    op.create_index(op.f("ix_patients_rm_code"), "patients", ["rm_code"], unique=False)
    op.create_index(op.f("ix_patients_is_demo"), "patients", ["is_demo"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_patients_is_demo"), table_name="patients")
    op.drop_index(op.f("ix_patients_rm_code"), table_name="patients")
    op.drop_table("patients")

