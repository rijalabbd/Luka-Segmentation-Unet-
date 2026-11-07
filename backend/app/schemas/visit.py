from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: str
    visit_date: date
    status: Literal["draft", "final"]
    visit_index: int | None = None
    image_path: str | None = None
    mask_path: str | None = None
    overlay_path: str | None = None
    distance_confirmed: bool = True
    n_wound_px: int
    area_pct: float
    delta_area: float | None = None
    pac: float | None = None
    trend_status: str | None = None
    clinician_notes: str | None = None
    patient_narrative: str | None = None
    narrative_source: Literal["llm", "template_fallback"] | None = None
    created_at: datetime
    confirmed_at: datetime | None = None

