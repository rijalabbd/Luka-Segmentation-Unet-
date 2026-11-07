from app.models.patient import Patient
from app.schemas.patient import PatientSummaryResponse, PatientTrendBadge, format_tanggal_id

CANVAS_TOTAL_PX = 65536


def calculate_relative_area(n_wound_px: int) -> float:
    return (n_wound_px / CANVAS_TOTAL_PX) * 100.0


def evaluate_pac_and_trend(
    a0: float, at: float
) -> tuple[float, float | None, PatientTrendBadge, str]:
    """
    Rumus Bab 3.7 & Urutan Evaluasi Tabel 3.3:
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

    if pac > 5.0 or delta_a < -1.0:
        return delta_a, pac, "menurun", "Tren Menurun (Area Luka Mengecil)"
    if pac < -5.0 or delta_a > 1.0:
        return delta_a, pac, "meningkat", "Tren Meningkat (Area Luka Membesar)"
    return delta_a, pac, "stabil", "Tren Stabil (Perubahan Minimal)"


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
        _, _, status, trend_status = evaluate_pac_and_trend(
            baseline_visit.area_pct, latest_visit.area_pct
        )

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

