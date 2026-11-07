from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.visit import Visit


class Patient(Base):
    __tablename__ = "patients"

    rm_code: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    name_initial: Mapped[str | None] = mapped_column(String(100), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ulcer_location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    informed_consent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    visits: Mapped[list[Visit]] = relationship(
        "Visit",
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="Visit.visit_index.asc().nulls_last(), Visit.id.asc()",
    )


__all__ = ["Patient", "Visit"]
