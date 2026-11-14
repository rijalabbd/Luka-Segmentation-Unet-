from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConfirmVisitRequest(BaseModel):
    confirm_zero_area: bool = False


class CalibrationRequest(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    length_cm: float


class VisitPreview(BaseModel):
    is_baseline: bool
    pac_basis: Literal["relative", "calibrated"] | None = None
    delta_area: float | None = None
    pac: float | None = None
    pac_rel: float | None = None
    pac_cm2: float | None = None
    trend_status: str | None = None
    warnings: list[str] = []


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
    confirm_zero_area: bool = False
    n_wound_px: int
    area_pct: float
    delta_area: float | None = None
    pac: float | None = None
    trend_status: str | None = None
    measure_mode: Literal["relative", "calibrated"] = "relative"
    img_width_px: int | None = None
    img_height_px: int | None = None
    calib_x1: float | None = None
    calib_y1: float | None = None
    calib_x2: float | None = None
    calib_y2: float | None = None
    calib_length_cm: float | None = None
    scale_cm_per_px: float | None = None
    area_cm2: float | None = None
    pac_rel: float | None = None
    pac_cm2: float | None = None
    pac_basis: Literal["relative", "calibrated"] | None = None
    warnings: list[str] | None = None
    preview: VisitPreview | None = None
    clinician_notes: str | None = None
    patient_narrative: str | None = None
    narrative_source: Literal["llm", "template_fallback"] | None = None
    created_at: datetime
    confirmed_at: datetime | None = None

