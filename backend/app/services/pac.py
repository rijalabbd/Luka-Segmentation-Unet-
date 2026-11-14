from dataclasses import dataclass
from typing import Literal

from app.models.patient import Patient
from app.models.visit import Visit
from app.schemas.patient import PatientSummaryResponse, PatientTrendBadge, format_tanggal_id

CANVAS_TOTAL_PX = 65536
TOTAL_MASK_PIXELS = CANVAS_TOTAL_PX


@dataclass(frozen=True)
class LongitudinalEvaluation:
    pac_basis: Literal["relative", "calibrated"]
    a0: float
    at: float
    delta_area: float
    pac: float | None
    pac_rel: float | None
    pac_cm2: float | None
    badge: PatientTrendBadge
    trend_status: str
    warnings: list[str]


def calculate_relative_area(n_wound_px: int) -> float:
    return (n_wound_px / CANVAS_TOTAL_PX) * 100.0


def classify(
    pac: float | None,
    delta_rel_pp: float | None,
    basis: Literal["relative", "calibrated"] = "relative",
) -> tuple[PatientTrendBadge, str]:
    """Klasifikasi status tren berdasarkan basis pengukuran (Tabel 3.3 & Keputusan D2).

    - Mode calibrated: hanya memakai PAC cm² (ambang ±5,0%); kriteria ΔA ±1,0 pp tidak berlaku.
    - Mode relative: memakai PAC % (±5,0%) atau ΔA (±1,0 poin persentase).
    """
    if pac is None:
        return "tidak_dapat_dihitung", "PAC tidak dapat dihitung"

    norm_pac = round(pac, 6)
    if basis == "calibrated":
        if norm_pac > 5.0:
            return "menurun", "Tren Menurun (Area Luka Mengecil)"
        if norm_pac < -5.0:
            return "meningkat", "Tren Meningkat (Area Luka Membesar)"
        return "stabil", "Tren Stabil (Perubahan Minimal)"

    norm_delta = round(delta_rel_pp, 6) if delta_rel_pp is not None else 0.0
    if norm_pac > 5.0 or norm_delta < -1.0:
        return "menurun", "Tren Menurun (Area Luka Mengecil)"
    if norm_pac < -5.0 or norm_delta > 1.0:
        return "meningkat", "Tren Meningkat (Area Luka Membesar)"
    return "stabil", "Tren Stabil (Perubahan Minimal)"


def evaluate_pac_and_trend(
    a0: float, at: float
) -> tuple[float, float | None, PatientTrendBadge, str]:
    """
    Rumus Bab 3.7 & Urutan Evaluasi Tabel 3.3 (mode relatif):
    - delta_a = at - a0 (poin persentase)
    - Jika a0 <= 0: PAC tidak dihitung (hindari pembagian nol)
    - Urutan evaluasi:
      1. Tren Menurun (Area Luka Mengecil): PAC > +5.0 atau delta_a < -1.0
      2. Tren Meningkat (Area Luka Membesar): PAC < -5.0 atau delta_a > +1.0
      3. Tren Stabil (Perubahan Minimal): selain kedua di atas
    """
    delta_a = at - a0
    if a0 <= 0.0:
        return delta_a, None, "tidak_dapat_dihitung", "PAC tidak dapat dihitung"

    pac = ((a0 - at) / a0) * 100.0
    badge, label = classify(pac, delta_a, "relative")
    return delta_a, pac, badge, label


def evaluate_visit_longitudinal(
    baseline_visit: Visit,
    current_visit: Visit,
) -> LongitudinalEvaluation:
    """Evaluasi longitudinal dua basis (relatif % dan terkalibrasi cm²) sesuai PRD v3 G3 & G4."""
    a0_rel = float(baseline_visit.area_pct)
    at_rel = float(current_visit.area_pct)
    delta_rel = at_rel - a0_rel
    raw_pac_rel = ((a0_rel - at_rel) / a0_rel) * 100.0 if a0_rel > 0.0 else None
    rounded_pac_rel = round(raw_pac_rel, 2) if raw_pac_rel is not None else None

    base_calibrated = (
        baseline_visit.measure_mode == "calibrated"
        and baseline_visit.area_cm2 is not None
        and baseline_visit.area_cm2 > 0.0
    )
    curr_calibrated = (
        current_visit.measure_mode == "calibrated"
        and current_visit.area_cm2 is not None
    )

    warnings: list[str] = []

    if base_calibrated and curr_calibrated:
        a0_cm2 = float(baseline_visit.area_cm2)  # type: ignore[arg-type]
        at_cm2 = float(current_visit.area_cm2)  # type: ignore[arg-type]
        delta_cm2 = at_cm2 - a0_cm2
        raw_pac_cm2 = ((a0_cm2 - at_cm2) / a0_cm2) * 100.0
        rounded_pac_cm2 = round(raw_pac_cm2, 2)
        badge, trend_status = classify(raw_pac_cm2, None, "calibrated")
        return LongitudinalEvaluation(
            pac_basis="calibrated",
            a0=round(a0_cm2, 2),
            at=round(at_cm2, 2),
            delta_area=round(delta_cm2, 2),
            pac=rounded_pac_cm2,
            pac_rel=rounded_pac_rel,
            pac_cm2=rounded_pac_cm2,
            badge=badge,
            trend_status=trend_status,
            warnings=warnings,
        )

    if base_calibrated != curr_calibrated:
        warnings.append("MIXED_BASIS")

    badge, trend_status = classify(raw_pac_rel, delta_rel, "relative")
    return LongitudinalEvaluation(
        pac_basis="relative",
        a0=round(a0_rel, 2),
        at=round(at_rel, 2),
        delta_area=round(delta_rel, 2),
        pac=rounded_pac_rel,
        pac_rel=rounded_pac_rel,
        pac_cm2=None,
        badge=badge,
        trend_status=trend_status,
        warnings=warnings,
    )


def build_patient_summary(patient: Patient) -> PatientSummaryResponse:
    final_visits = sorted(
        [v for v in patient.visits if v.status == "final"],
        key=lambda v: (v.visit_index if v.visit_index is not None else 999999, v.visit_date, v.id),
    )
    n = len(final_visits)

    if n == 0:
        terakhir = "Belum ada kunjungan"
        status: PatientTrendBadge = "belum_ada"
        trend_status = "Belum ada kunjungan"
    elif n == 1:
        terakhir = format_tanggal_id(final_visits[0].visit_date)
        status = "baseline"
        trend_status = "Kunjungan awal (baseline)"
    else:
        baseline_visit = final_visits[0]
        latest_visit = final_visits[-1]
        terakhir = format_tanggal_id(latest_visit.visit_date)
        eval_res = evaluate_visit_longitudinal(baseline_visit, latest_visit)
        status = eval_res.badge
        trend_status = eval_res.trend_status

    return PatientSummaryResponse(
        id=patient.rm_code,
        nama=patient.name_initial,
        umur=patient.age,
        jk=patient.gender,
        lokasi=patient.ulcer_location,
        n=n,
        terakhir=terakhir,
        status=status,
        trend_status=trend_status,
        is_demo=patient.is_demo,
    )
