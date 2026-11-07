from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.patient import Patient


def derive_overlay_rel_path(mask_path: str | None) -> str | None:
    if not mask_path:
        return None
    if mask_path.startswith("masks/") and mask_path.endswith("_mask.png"):
        stem = mask_path[len("masks/") : -len("_mask.png")]
        return f"overlays/{stem}_overlay.png"
    return None


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (
        UniqueConstraint("patient_id", "visit_index", name="uq_visits_patient_visit_index"),
        Index(
            "uq_visits_one_draft_per_patient",
            "patient_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.rm_code", ondelete="CASCADE"), index=True, nullable=False
    )
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)  # draft | final
    visit_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mask_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    distance_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    confirm_zero_area: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    n_wound_px: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    area_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    delta_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    pac: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    clinician_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    patient_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="visits")

    @property
    def overlay_path(self) -> str | None:
        return derive_overlay_rel_path(self.mask_path)
