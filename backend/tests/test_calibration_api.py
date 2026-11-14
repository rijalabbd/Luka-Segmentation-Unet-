from collections.abc import AsyncGenerator
import importlib.util
import io
import json
from pathlib import Path
from typing import Any

from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import ASGITransport, AsyncClient
from PIL import Image
import pytest
from sqlalchemy import Connection, delete, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.patient import Patient, Visit
from app.services import narrative as narrative_module
from app.services.narrative import (
    generate_fallback_narrative,
    validate_narrative_output,
)
from app.services.pac import classify, evaluate_distance_warnings
from app.services.segmentation import SegmentationFn, get_segmentation_service
from app.services.storage import generate_stub_binary_mask_png


def _make_png_bytes(width: int = 256, height: int = 256) -> bytes:
    img = Image.new("RGB", (width, height), color=(180, 90, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _override_segmentation_px(n_px: int) -> None:
    def _custom_segment(_image_bytes: bytes) -> tuple[int, bytes]:
        return n_px, generate_stub_binary_mask_png(n_px)

    def _get_custom_service() -> SegmentationFn:
        return _custom_segment

    app.dependency_overrides[get_segmentation_service] = _get_custom_service


def _sync_db_url(async_url: str) -> str:
    return async_url.replace("+asyncpg", "+psycopg2").replace("postgresql+psycopg2", "postgresql")


@pytest.fixture
async def calib_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[tuple[AsyncClient, Path], None]:
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "gemini_api_key", "")

    test_engine = create_async_engine(settings.resolved_test_database_url, future=True)
    TestSessionLocal = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )

    async with TestSessionLocal() as session:
        await session.execute(delete(Visit))
        await session.execute(delete(Patient))
        await session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/v1/patients",
            json={
                "id": "Patient_10",
                "nama": "LUTSeg 10",
                "umur": 50,
                "jk": "Laki-laki",
                "lokasi": "Telapak kaki kanan",
                "consent": True,
                "is_demo": False,
            },
        )
        yield ac, tmp_path

    async with TestSessionLocal() as session:
        await session.execute(delete(Visit))
        await session.execute(delete(Patient))
        await session.commit()

    app.dependency_overrides.clear()
    await test_engine.dispose()


async def _upload_draft(
    ac: AsyncClient,
    *,
    n_px: int,
    visit_date: str,
    width: int = 256,
    height: int = 256,
) -> dict[str, Any]:
    _override_segmentation_px(n_px)
    resp = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": visit_date, "distance_confirmed": "true"},
        files={"file": ("ulcer.png", _make_png_bytes(width, height), "image/png")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_k6_01_alembic_migration_0006_upgrade_downgrade_and_legacy_default() -> None:
    """K1 & K6-1: Migrasi 0006 upgrade/downgrade bersih; baris lama otomatis terbaca measure_mode='relative'."""
    backend_root = Path(__file__).resolve().parents[1]
    mig_path = backend_root / "alembic" / "versions" / "0006_add_calibration_columns.py"
    spec = importlib.util.spec_from_file_location("mig_0006", mig_path)
    assert spec is not None and spec.loader is not None
    mig_0006 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig_0006)

    def _exec_0006(sync_conn: Connection, fn_name: str) -> None:
        ctx = MigrationContext.configure(sync_conn)
        with Operations.context(ctx):
            getattr(mig_0006, fn_name)()

    engine = create_async_engine(settings.resolved_test_database_url, future=True)
    try:
        async with engine.begin() as conn:
            cols_initial = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("visits")}
            )
            if "measure_mode" not in cols_initial:
                await conn.run_sync(_exec_0006, "upgrade")

            # Jalankan downgrade 0006 -> pastikan seluruh kolom kalibrasi terhapus
            await conn.run_sync(_exec_0006, "downgrade")
            cols_after_down = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("visits")}
            )
            assert "measure_mode" not in cols_after_down
            assert "area_cm2" not in cols_after_down

            # Sisipkan baris kunjungan sebelum upgrade ke 0006 untuk menguji backfill 'relative'
            await conn.execute(text("DELETE FROM visits"))
            await conn.execute(text("DELETE FROM patients"))
            await conn.execute(
                text(
                    "INSERT INTO patients (rm_code, name_initial, age, gender, ulcer_location, informed_consent, is_demo, created_at) "
                    "VALUES ('RM-MIG-01', 'Tn. M', 45, 'Laki-laki', 'Plantar', true, false, NOW())"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO visits (patient_id, visit_date, status, visit_index, distance_confirmed, "
                    "confirm_zero_area, n_wound_px, area_pct, created_at) "
                    "VALUES ('RM-MIG-01', '2026-10-01', 'final', 1, true, false, 3277, 5.0, NOW())"
                )
            )

            # Jalankan upgrade 0006 -> pastikan kolom kalibrasi ada dan baris lama terbaca 'relative'
            await conn.run_sync(_exec_0006, "upgrade")
            cols_after_up = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("visits")}
            )
            for expected_col in (
                "measure_mode",
                "img_width_px",
                "img_height_px",
                "calib_x1",
                "calib_y1",
                "calib_x2",
                "calib_y2",
                "calib_length_cm",
                "scale_cm_per_px",
                "area_cm2",
                "pac_rel",
                "pac_cm2",
                "pac_basis",
                "warnings",
            ):
                assert expected_col in cols_after_up

            row = (
                await conn.execute(
                    text(
                        "SELECT measure_mode, scale_cm_per_px, area_cm2 FROM visits WHERE patient_id = 'RM-MIG-01'"
                    )
                )
            ).one()
            assert row[0] == "relative"
            assert row[1] is None
            assert row[2] is None
            await conn.execute(text("DELETE FROM visits"))
            await conn.execute(text("DELETE FROM patients"))
    finally:
        await engine.dispose()


async def test_k6_02_valid_calibration_hand_calculation_256_and_1600x1200(
    calib_client: tuple[AsyncClient, Path],
) -> None:
    """K2 & K6-2: Kalibrasi sah diperiksa terhadap hitung tangan pada kanvas 256x256 dan 1600x1200."""
    ac, _ = calib_client

    # Kasus A (256x256): N_luka=3277, delta_px=40, L=2.0 cm -> s=0.05 cm/px, A_cm2=8.19 cm²
    d_256 = await _upload_draft(ac, n_px=3277, visit_date="2026-10-01", width=256, height=256)
    assert d_256["measure_mode"] == "relative"
    assert d_256["img_width_px"] == 256
    assert d_256["img_height_px"] == 256

    r_cal_256 = await ac.put(
        f"/api/v1/visits/{d_256['id']}/calibration",
        json={"x1": 20.0, "y1": 30.0, "x2": 60.0, "y2": 30.0, "length_cm": 2.0},
    )
    assert r_cal_256.status_code == 200, r_cal_256.text
    b_256 = r_cal_256.json()
    assert b_256["measure_mode"] == "calibrated"
    assert b_256["scale_cm_per_px"] == pytest.approx(0.05)
    assert b_256["area_cm2"] == pytest.approx(8.19)
    assert b_256["area_pct"] == pytest.approx(5.0)

    # Kasus B (1600x1200): N_luka=3277, delta_px=80, L=2.0 cm -> s=0.025 cm/px, A_cm2=60.00 cm²
    d_rect = await _upload_draft(
        ac, n_px=3277, visit_date="2026-10-02", width=1600, height=1200
    )
    assert d_rect["img_width_px"] == 1600
    assert d_rect["img_height_px"] == 1200

    r_cal_rect = await ac.put(
        f"/api/v1/visits/{d_rect['id']}/calibration",
        json={"x1": 100.0, "y1": 200.0, "x2": 180.0, "y2": 200.0, "length_cm": 2.0},
    )
    assert r_cal_rect.status_code == 200, r_cal_rect.text
    b_rect = r_cal_rect.json()
    assert b_rect["measure_mode"] == "calibrated"
    assert b_rect["scale_cm_per_px"] == pytest.approx(0.025)
    assert b_rect["area_cm2"] == pytest.approx(60.0)


async def test_k6_03_calibration_rejected_422_on_invalid_inputs(
    calib_client: tuple[AsyncClient, Path],
) -> None:
    """K2 & K6-3: Kalibrasi ditolak (422) bila titik berimpit, < 2% diagonal, L <= 0 / > 50, atau di luar citra."""
    ac, _ = calib_client
    draft = await _upload_draft(ac, n_px=3277, visit_date="2026-10-01", width=1000, height=1000)
    vid = draft["id"]

    # 1. Titik berimpit (delta_px = 0)
    r_same = await ac.put(
        f"/api/v1/visits/{vid}/calibration",
        json={"x1": 100.0, "y1": 100.0, "x2": 100.0, "y2": 100.0, "length_cm": 2.0},
    )
    assert r_same.status_code == 422

    # 2. Titik terlalu dekat (< 2% diagonal; diagonal 1000x1000 = 1414.21 px, 2% = 28.28 px; uji delta_px = 10 px)
    r_close = await ac.put(
        f"/api/v1/visits/{vid}/calibration",
        json={"x1": 100.0, "y1": 100.0, "x2": 110.0, "y2": 100.0, "length_cm": 2.0},
    )
    assert r_close.status_code == 422

    # 3. Panjang nyata <= 0 atau > 50 cm
    for bad_len in (0.0, -1.5, 50.1, 100.0):
        r_len = await ac.put(
            f"/api/v1/visits/{vid}/calibration",
            json={"x1": 100.0, "y1": 100.0, "x2": 200.0, "y2": 100.0, "length_cm": bad_len},
        )
        assert r_len.status_code == 422

    # 4. Koordinat di luar dimensi citra [0, 1000] x [0, 1000]
    for bad_coords in (
        {"x1": -1.0, "y1": 100.0, "x2": 200.0, "y2": 100.0, "length_cm": 2.0},
        {"x1": 100.0, "y1": 100.0, "x2": 1001.0, "y2": 100.0, "length_cm": 2.0},
        {"x1": 100.0, "y1": -5.0, "x2": 200.0, "y2": 100.0, "length_cm": 2.0},
        {"x1": 100.0, "y1": 100.0, "x2": 200.0, "y2": 1005.0, "length_cm": 2.0},
    ):
        r_out = await ac.put(f"/api/v1/visits/{vid}/calibration", json=bad_coords)
        assert r_out.status_code == 422


async def test_k6_04_and_05_delete_calibration_on_draft_and_409_on_final(
    calib_client: tuple[AsyncClient, Path],
) -> None:
    """K2 & K6-4/5: DELETE mengembalikan draf ke relative; PUT dan DELETE pada kunjungan final ditolak (409)."""
    ac, _ = calib_client
    draft = await _upload_draft(ac, n_px=3277, visit_date="2026-10-01", width=256, height=256)
    vid = draft["id"]

    # Kalibrasi draf
    r_put = await ac.put(
        f"/api/v1/visits/{vid}/calibration",
        json={"x1": 10.0, "y1": 10.0, "x2": 50.0, "y2": 10.0, "length_cm": 2.0},
    )
    assert r_put.status_code == 200
    assert r_put.json()["measure_mode"] == "calibrated"

    # Hapus kalibrasi pada draf -> kembali ke relative dan kolom kalibrasi dikosongkan
    r_del = await ac.delete(f"/api/v1/visits/{vid}/calibration")
    assert r_del.status_code == 200
    reset_body = r_del.json()
    assert reset_body["measure_mode"] == "relative"
    assert reset_body["calib_x1"] is None
    assert reset_body["calib_y1"] is None
    assert reset_body["calib_x2"] is None
    assert reset_body["calib_y2"] is None
    assert reset_body["calib_length_cm"] is None
    assert reset_body["scale_cm_per_px"] is None
    assert reset_body["area_cm2"] is None

    # Konfirmasi menjadi final
    r_conf = await ac.post(f"/api/v1/visits/{vid}/confirm")
    assert r_conf.status_code == 200
    assert r_conf.json()["status"] == "final"

    # PUT maupun DELETE kalibrasi pada kunjungan final harus ditolak 409
    r_put_final = await ac.put(
        f"/api/v1/visits/{vid}/calibration",
        json={"x1": 10.0, "y1": 10.0, "x2": 50.0, "y2": 10.0, "length_cm": 2.0},
    )
    assert r_put_final.status_code == 409

    r_del_final = await ac.delete(f"/api/v1/visits/{vid}/calibration")
    assert r_del_final.status_code == 409


async def test_k6_06_calibrated_pac_cm2_distance_simulation_and_d2_classification(
    calib_client: tuple[AsyncClient, Path],
) -> None:
    """K3 & K6-6: Simulasi pembesaran jarak 20->25 cm (PAC_rel=+36%, s_t=1.25*s_0 -> PAC_cm2=0% Tren Stabil) & D2."""
    ac, _ = calib_client

    # Kunjungan 1 (Baseline): 256x256, N_0 = 6400 px (A_0,rel = 9.77%)
    # Kalibrasi: delta_px = 50 px, L = 2.0 cm -> s_0 = 0.04 cm/px -> A_0,cm2 = 6400 * 0.0016 = 10.24 cm²
    d1 = await _upload_draft(ac, n_px=6400, visit_date="2026-10-01", width=256, height=256)
    await ac.put(
        f"/api/v1/visits/{d1['id']}/calibration",
        json={"x1": 10.0, "y1": 10.0, "x2": 60.0, "y2": 10.0, "length_cm": 2.0},
    )
    c1 = await ac.post(f"/api/v1/visits/{d1['id']}/confirm")
    assert c1.status_code == 200
    b1 = c1.json()
    assert b1["area_cm2"] == pytest.approx(10.24)

    # Kunjungan 2 (Simulasi jarak kamera menjauh 1.25x):
    # N_t = 0.64 * 6400 = 4096 px (A_t,rel = 6.25%, PAC_rel = +36.0%)
    # Penggaris di citra ikut mengecil: delta_px = 40 px untuk L = 2.0 cm -> s_t = 0.05 = 1.25 * s_0
    # A_t,cm2 = 4096 * 0.05^2 = 10.24 cm² -> PAC_cm2 = 0.0%, status = Tren Stabil (Perubahan Minimal)
    d2 = await _upload_draft(ac, n_px=4096, visit_date="2026-10-15", width=256, height=256)
    r_cal2 = await ac.put(
        f"/api/v1/visits/{d2['id']}/calibration",
        json={"x1": 10.0, "y1": 10.0, "x2": 50.0, "y2": 10.0, "length_cm": 2.0},
    )
    assert r_cal2.status_code == 200
    preview2 = r_cal2.json()["preview"]
    assert preview2["pac_basis"] == "calibrated"
    assert preview2["pac_rel"] == pytest.approx(36.0, abs=0.05)
    assert preview2["pac_cm2"] == pytest.approx(0.0)
    assert preview2["trend_status"] == "Tren Stabil (Perubahan Minimal)"
    assert preview2["warnings"] == []

    c2 = await ac.post(f"/api/v1/visits/{d2['id']}/confirm")
    assert c2.status_code == 200
    b2 = c2.json()
    assert b2["pac_basis"] == "calibrated"
    assert b2["pac_rel"] == pytest.approx(36.0, abs=0.05)
    assert b2["pac_cm2"] == pytest.approx(0.0)
    assert b2["pac"] == pytest.approx(0.0)
    assert b2["delta_area"] == pytest.approx(0.0)
    assert b2["trend_status"] == "Tren Stabil (Perubahan Minimal)"
    assert b2["warnings"] == []
    assert "cm²" in b2["clinician_notes"]

    # Uji unit fungsi classify untuk Keputusan D2:
    # Pada mode calibrated, |PAC_cm2| <= 5.0% tetap Stabil meskipun |delta_rel_pp| > 1.0 pp
    assert classify(4.0, -2.5, "calibrated") == (
        "stabil",
        "Tren Stabil (Perubahan Minimal)",
    )
    assert classify(-4.9, 3.0, "calibrated") == (
        "stabil",
        "Tren Stabil (Perubahan Minimal)",
    )
    assert classify(5.1, -0.2, "calibrated") == (
        "menurun",
        "Tren Menurun (Area Luka Mengecil)",
    )
    assert classify(-5.1, 0.2, "calibrated") == (
        "meningkat",
        "Tren Meningkat (Area Luka Membesar)",
    )


async def test_k6_07_mixed_mode_fallback_to_relative_and_mixed_basis_warning(
    calib_client: tuple[AsyncClient, Path],
) -> None:
    """K3 & K6-7: Mode campuran (satu calibrated, satu relative) -> pac_basis='relative', pac_cm2=None, MIXED_BASIS."""
    ac, _ = calib_client

    # Skenario A: Baseline relative, Kunjungan 2 calibrated
    d1 = await _upload_draft(ac, n_px=3277, visit_date="2026-10-01")
    await ac.post(f"/api/v1/visits/{d1['id']}/confirm")

    d2 = await _upload_draft(ac, n_px=2949, visit_date="2026-10-10")
    await ac.put(
        f"/api/v1/visits/{d2['id']}/calibration",
        json={"x1": 10.0, "y1": 10.0, "x2": 50.0, "y2": 10.0, "length_cm": 2.0},
    )
    c2 = await ac.post(f"/api/v1/visits/{d2['id']}/confirm")
    assert c2.status_code == 200
    b2 = c2.json()
    assert b2["measure_mode"] == "calibrated"
    assert b2["pac_basis"] == "relative"
    assert b2["pac_cm2"] is None
    assert b2["pac"] == b2["pac_rel"]
    assert "MIXED_BASIS" in b2["warnings"]

    # Skenario B: Pasien baru dengan Baseline calibrated, Kunjungan 2 relative
    await ac.post(
        "/api/v1/patients",
        json={
            "id": "Patient_11",
            "nama": "LUTSeg 11",
            "umur": 48,
            "jk": "Perempuan",
            "lokasi": "Plantar kiri",
            "consent": True,
            "is_demo": False,
        },
    )
    _override_segmentation_px(3277)
    r_b1 = await ac.post(
        "/api/v1/patients/Patient_11/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("b1.png", _make_png_bytes(), "image/png")},
    )
    vid_b1 = r_b1.json()["id"]
    await ac.put(
        f"/api/v1/visits/{vid_b1}/calibration",
        json={"x1": 10.0, "y1": 10.0, "x2": 50.0, "y2": 10.0, "length_cm": 2.0},
    )
    await ac.post(f"/api/v1/visits/{vid_b1}/confirm")

    _override_segmentation_px(2949)
    r_b2 = await ac.post(
        "/api/v1/patients/Patient_11/visits",
        data={"visit_date": "2026-10-12", "distance_confirmed": "true"},
        files={"file": ("b2.png", _make_png_bytes(), "image/png")},
    )
    c_b2 = await ac.post(f"/api/v1/visits/{r_b2.json()['id']}/confirm")
    assert c_b2.status_code == 200
    body_b2 = c_b2.json()
    assert body_b2["measure_mode"] == "relative"
    assert body_b2["pac_basis"] == "relative"
    assert body_b2["pac_cm2"] is None
    assert "MIXED_BASIS" in body_b2["warnings"]


async def test_k6_08_distance_warnings_boundaries_and_low_baseline(
    calib_client: tuple[AsyncClient, Path],
) -> None:
    """K4 & K6-8: Peringatan jarak pada batas 4.9%, 5.0%, -7.0%, 10.0%, 10.1%, 36%, LOW_BASELINE, dan mode calibrated."""
    ac, _ = calib_client

    # Uji langsung pada nilai batas persis sesuai spesifikasi D1 & G5
    assert evaluate_distance_warnings(4.9, "relative", a0_rel=5.0) == []
    assert evaluate_distance_warnings(-4.9, "relative", a0_rel=5.0) == []
    assert evaluate_distance_warnings(5.0, "relative", a0_rel=5.0) == ["DISTANCE_SENSITIVE"]
    assert evaluate_distance_warnings(-7.0, "relative", a0_rel=5.0) == ["DISTANCE_SENSITIVE"]
    assert evaluate_distance_warnings(10.0, "relative", a0_rel=5.0) == ["DISTANCE_SENSITIVE"]
    assert evaluate_distance_warnings(-10.0, "relative", a0_rel=5.0) == ["DISTANCE_SENSITIVE"]
    assert evaluate_distance_warnings(10.1, "relative", a0_rel=5.0) == ["DISTANCE_LARGE"]
    assert evaluate_distance_warnings(36.0, "relative", a0_rel=5.0) == ["DISTANCE_LARGE"]
    assert evaluate_distance_warnings(-36.0, "relative", a0_rel=5.0) == ["DISTANCE_LARGE"]
    assert evaluate_distance_warnings(36.0, "calibrated", a0_rel=5.0) == []
    assert evaluate_distance_warnings(3.0, "relative", a0_rel=0.8) == ["LOW_BASELINE"]

    # Uji integrasi via endpoint confirm pada mode relative dengan |PAC| > 10% (DISTANCE_LARGE)
    # dan 5% <= |PAC| <= 10% (DISTANCE_SENSITIVE)
    d1 = await _upload_draft(ac, n_px=6554, visit_date="2026-10-01")  # A_0 = 10.00%
    await ac.post(f"/api/v1/visits/{d1['id']}/confirm")

    # Kunjungan 2: A_t = 9.30% (n_px = 6095 -> 9.30%) -> PAC = +7.00% -> DISTANCE_SENSITIVE
    d2 = await _upload_draft(ac, n_px=6095, visit_date="2026-10-10")
    c2 = await ac.post(f"/api/v1/visits/{d2['id']}/confirm")
    assert c2.status_code == 200
    assert c2.json()["pac_rel"] == pytest.approx(7.0, abs=0.05)
    assert "DISTANCE_SENSITIVE" in c2.json()["warnings"]

    # Kunjungan 3: A_t = 6.40% (n_px = 4194 -> 6.40%) -> PAC = +36.00% -> DISTANCE_LARGE
    d3 = await _upload_draft(ac, n_px=4194, visit_date="2026-10-20")
    c3 = await ac.post(f"/api/v1/visits/{d3['id']}/confirm")
    assert c3.status_code == 200
    assert c3.json()["pac_rel"] == pytest.approx(36.0, abs=0.05)
    assert "DISTANCE_LARGE" in c3.json()["warnings"]


async def test_k6_09_cm2_validator_fallback_and_gemini_payload(
    calib_client: tuple[AsyncClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """K5 & K6-9: Validator cm², templat fallback cm² 3 status, dan payload Gemini cm² tanpa PII/koordinat."""
    ac, _ = calib_client

    # 1. Templat fallback cm² untuk ketiga status tren menghasilkan narasi cm² tanpa poin persentase
    for badge, a0, at, delta_a, pac in (
        ("menurun", 8.00, 6.00, -2.00, 25.00),
        ("stabil", 8.00, 7.80, -0.20, 2.50),
        ("meningkat", 8.00, 10.00, 2.00, -25.00),
    ):
        c_notes, p_narr, src = generate_fallback_narrative(
            a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit="cm²"
        )
        assert src == "template_fallback"
        a0_id = f"{a0:.2f}".replace(".", ",")
        at_id = f"{at:.2f}".replace(".", ",")
        da_id = f"{delta_a:+.2f}".replace(".", ",")
        assert f"{a0_id} cm²" in c_notes
        assert f"{at_id} cm²" in c_notes
        assert f"{da_id} cm²" in c_notes
        assert "poin persentase" not in c_notes.lower()
        assert "bukan diagnosis medis" in p_narr.lower()

    # 2. Validator cm² menerima narasi cm² yang sah (dilengkapi disclaimer pada kedua narasi)
    #    dan menolak angka asing maupun satuan yang salah (poin persentase, mm², % pada luas cm²)
    valid_c, valid_p, _ = generate_fallback_narrative(
        a0=8.00, at=6.00, delta_a=-2.00, pac=25.00, badge="menurun", unit="cm²"
    )
    ok_valid, reason_valid = validate_narrative_output(
        valid_c,
        valid_p,
        a0=8.00,
        at=6.00,
        delta_a=-2.00,
        pac=25.00,
        badge="menurun",
        unit="cm²",
    )
    assert ok_valid is True, reason_valid

    # Angka asing (99.99)
    ok_num, r_num = validate_narrative_output(
        valid_c + " (catatan tambahan 99.99 cm²).",
        valid_p,
        a0=8.00,
        at=6.00,
        delta_a=-2.00,
        pac=25.00,
        badge="menurun",
        unit="cm²",
    )
    assert ok_num is False and "angka_asing" in r_num

    # Satuan salah: poin persentase pada mode cm²
    ok_pp, r_pp = validate_narrative_output(
        valid_c.replace("ΔA: -2,00 cm²", "ΔA: -2,00 poin persentase"),
        valid_p,
        a0=8.00,
        at=6.00,
        delta_a=-2.00,
        pac=25.00,
        badge="menurun",
        unit="cm²",
    )
    assert ok_pp is False and "poin_persentase" in r_pp

    # Satuan salah: mm²
    ok_mm, r_mm = validate_narrative_output(
        valid_c.replace("cm²", "mm²"),
        valid_p,
        a0=8.00,
        at=6.00,
        delta_a=-2.00,
        pac=25.00,
        badge="menurun",
        unit="cm²",
    )
    assert ok_mm is False and "mm" in r_mm

    # Satuan salah: memakai % untuk luas pada mode cm² (tanpa cm² atau menempelkan % ke A0/At)
    rel_c, rel_p, _ = generate_fallback_narrative(
        a0=8.00, at=6.00, delta_a=-2.00, pac=25.00, badge="menurun", unit="%"
    )
    ok_pct1, r_pct1 = validate_narrative_output(
        rel_c,
        rel_p,
        a0=8.00,
        at=6.00,
        delta_a=-2.00,
        pac=25.00,
        badge="menurun",
        unit="cm²",
    )
    assert ok_pct1 is False

    ok_pct2, r_pct2 = validate_narrative_output(
        valid_c.replace("8,00 cm²", "8,00%"),
        valid_p,
        a0=8.00,
        at=6.00,
        delta_a=-2.00,
        pac=25.00,
        badge="menurun",
        unit="cm²",
    )
    assert ok_pct2 is False and "persen_pada_luas_cm2" in r_pct2

    # 3. Muatan ke Gemini pada mode cm² memuat "satuan": "cm²" dan bebas PII / koordinat / skala
    monkeypatch.setattr(settings, "gemini_api_key", "fake-calib-gemini-key")
    captured_payloads: list[dict[str, float | str]] = []

    async def _mock_gemini_cm2(
        user_payload: dict[str, float | str], **_kwargs: object
    ) -> dict[str, object]:
        captured_payloads.append(user_payload)
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "clinician_notes": valid_c,
                                        "patient_narrative": valid_p,
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(narrative_module, "request_gemini_api", _mock_gemini_cm2)

    # Kunjungan 1 calibrated: N=3200, s=0.05 -> A0 = 3200 * 0.0025 = 8.00 cm²
    d1 = await _upload_draft(ac, n_px=3200, visit_date="2026-10-01", width=256, height=256)
    await ac.put(
        f"/api/v1/visits/{d1['id']}/calibration",
        json={"x1": 12.0, "y1": 34.0, "x2": 52.0, "y2": 34.0, "length_cm": 2.0},
    )
    await ac.post(f"/api/v1/visits/{d1['id']}/confirm")

    # Kunjungan 2 calibrated: N=2400, s=0.05 -> At = 2400 * 0.0025 = 6.00 cm² (delta=-2.00, PAC=+25.00%)
    d2 = await _upload_draft(ac, n_px=2400, visit_date="2026-10-15", width=256, height=256)
    await ac.put(
        f"/api/v1/visits/{d2['id']}/calibration",
        json={"x1": 12.0, "y1": 34.0, "x2": 52.0, "y2": 34.0, "length_cm": 2.0},
    )
    c2 = await ac.post(f"/api/v1/visits/{d2['id']}/confirm")
    assert c2.status_code == 200
    body2 = c2.json()
    assert body2["narrative_source"] == "llm"

    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert set(payload.keys()) == {"A0", "A_t", "delta_A", "PAC", "trend_status", "satuan"}
    assert payload["A0"] == pytest.approx(8.0)
    assert payload["A_t"] == pytest.approx(6.0)
    assert payload["delta_A"] == pytest.approx(-2.0)
    assert payload["PAC"] == pytest.approx(25.0)
    assert payload["satuan"] == "cm²"

    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden_leak in (
        "Patient_10",
        "LUTSeg 10",
        "Telapak kaki kanan",
        "calib_x1",
        "scale_cm_per_px",
        "0.05",
        "12.0",
        "34.0",
        "52.0",
    ):
        assert forbidden_leak not in serialized
