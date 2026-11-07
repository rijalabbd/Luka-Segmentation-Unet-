from collections.abc import AsyncGenerator
import asyncio
from datetime import date, datetime, timedelta, timezone
import io
from pathlib import Path

from PIL import Image
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.patient import Patient, Visit
from app.services.narrative import (
    FORBIDDEN_WORDS,
    build_gemini_user_prompt,
    generate_fallback_narrative,
    generate_longitudinal_narrative,
    get_narrative_service,
    validate_narrative_text,
)
from app.services.segmentation import (
    EXPECTED_RESNET34_UNET_PARAMS,
    SegmentationFn,
    get_last_inference_ms,
    get_loaded_model,
    get_segmentation_service,
    load_segmentation_model,
    resolve_checkpoint_path,
)
from app.services.storage import generate_stub_binary_mask_png, resolve_storage_path


def _make_dummy_png_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), color=(180, 90, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _override_segmentation_px(n_px: int) -> None:
    def _custom_segment(_image_bytes: bytes) -> tuple[int, bytes]:
        return n_px, generate_stub_binary_mask_png(n_px)

    def _get_custom_service() -> SegmentationFn:
        return _custom_segment

    app.dependency_overrides[get_segmentation_service] = _get_custom_service


@pytest.fixture
async def visit_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[tuple[AsyncClient, Path], None]:
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))

    test_engine = create_async_engine(settings.resolved_test_database_url, future=True)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

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


async def test_13_upload_draft_creates_files_and_replaces_previous_draft(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, storage_root = visit_client
    png_bytes = _make_dummy_png_bytes()

    # Draft pertama (dependency override: 3277 piksel -> 5.00%)
    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("ulcer_t1.png", png_bytes, "image/png")},
    )
    assert r1.status_code == 201
    d1 = r1.json()
    assert d1["status"] == "draft"
    assert d1["distance_confirmed"] is True
    assert d1["visit_index"] is None
    assert d1["n_wound_px"] == 3277
    assert d1["area_pct"] == 5.0
    img1_path = storage_root / d1["image_path"]
    mask1_path = storage_root / d1["mask_path"]
    overlay1_path = storage_root / d1["overlay_path"]
    assert img1_path.is_file()
    assert mask1_path.is_file()
    assert overlay1_path.is_file()

    # Pastikan masker biner 256x256 PNG (piksel hanya 0 dan 255, jumlah 255 == 3277)
    with Image.open(mask1_path) as mask_img:
        assert mask_img.size == (256, 256)
        assert mask_img.mode == "L"
        px_values = list(mask_img.tobytes())
        assert set(px_values).issubset({0, 255})
        assert px_values.count(255) == 3277

    # Draft kedua untuk pasien yang sama harus menggantikan draft pertama & menghapus berkasnya
    _override_segmentation_px(3604)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-02", "distance_confirmed": "true"},
        files={"file": ("ulcer_t1_retake.png", png_bytes, "image/png")},
    )
    assert r2.status_code == 201
    d2 = r2.json()
    assert d2["id"] != d1["id"]
    assert d2["n_wound_px"] == 3604
    assert not img1_path.exists()
    assert not mask1_path.exists()
    assert not overlay1_path.exists()
    assert (storage_root / d2["image_path"]).is_file()
    assert (storage_root / d2["mask_path"]).is_file()
    assert (storage_root / d2["overlay_path"]).is_file()

    # Draft lama sudah terhapus dari DB
    old_get = await ac.get(f"/api/v1/visits/{d1['id']}")
    assert old_get.status_code == 404


async def test_14_confirm_baseline_and_followup_plus_idempotency(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, _ = visit_client
    png_bytes = _make_dummy_png_bytes()

    # 1. Buat & konfirmasi kunjungan 1 (Baseline A0 = 5.00% -> 3277 px via dependency override)
    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("t1.png", png_bytes, "image/png")},
    )
    v1_id = r1.json()["id"]

    c1 = await ac.post(f"/api/v1/visits/{v1_id}/confirm")
    assert c1.status_code == 200
    b1 = c1.json()
    assert b1["status"] == "final"
    assert b1["visit_index"] == 1
    assert b1["area_pct"] == 5.0
    assert b1["delta_area"] is None
    assert b1["pac"] is None
    assert b1["trend_status"] is None
    assert b1["clinician_notes"] is None
    assert b1["patient_narrative"] is None
    assert b1["narrative_source"] is None
    assert b1["confirmed_at"] is not None

    # Panggilan confirm kedua pada baseline bersifat idempoten
    c1_again = await ac.post(f"/api/v1/visits/{v1_id}/confirm")
    assert c1_again.status_code == 200
    assert c1_again.json()["visit_index"] == 1
    assert c1_again.json()["confirmed_at"] == b1["confirmed_at"]

    # 2. Buat & konfirmasi kunjungan 2 (At = 3.50% -> 2294 px -> delta_A = -1.50, PAC = +30.00%, Menurun)
    _override_segmentation_px(2294)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("t2.png", png_bytes, "image/png")},
    )
    v2_id = r2.json()["id"]

    c2 = await ac.post(f"/api/v1/visits/{v2_id}/confirm")
    assert c2.status_code == 200
    b2 = c2.json()
    assert b2["status"] == "final"
    assert b2["visit_index"] == 2
    assert b2["area_pct"] == 3.5
    assert b2["delta_area"] == -1.5
    assert b2["pac"] == 30.0
    assert b2["trend_status"] == "Tren Menurun (Area Luka Mengecil)"
    assert b2["narrative_source"] == "template_fallback"
    assert "5.00%" in b2["clinician_notes"]
    assert "3.50%" in b2["clinician_notes"]
    assert "30.00%" in b2["patient_narrative"]

    # 3. Buat & konfirmasi kunjungan 3 (At = 6.00% -> 3932 px terhadap A0 = 5.00% -> PAC = -20.00%)
    _override_segmentation_px(3932)
    r3 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-29", "distance_confirmed": "true"},
        files={"file": ("t3.png", png_bytes, "image/png")},
    )
    v3_id = r3.json()["id"]
    c3 = await ac.post(f"/api/v1/visits/{v3_id}/confirm")
    assert c3.status_code == 200
    b3 = c3.json()
    assert b3["visit_index"] == 3
    assert b3["delta_area"] == 1.0
    assert b3["pac"] == -20.0
    assert b3["trend_status"] == "Tren Meningkat (Area Luka Membesar)"

    # 4. Riwayat kunjungan final mengembalikan 3 kunjungan berurutan
    hist = await ac.get("/api/v1/patients/Patient_10/visits")
    assert hist.status_code == 200
    items = hist.json()
    assert [v["visit_index"] for v in items] == [1, 2, 3]


async def test_15_lifo_deletion_and_file_cleanup(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, storage_root = visit_client
    png_bytes = _make_dummy_png_bytes()

    # Buat 2 kunjungan final
    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("t1.png", png_bytes, "image/png")},
    )
    v1 = (await ac.post(f"/api/v1/visits/{r1.json()['id']}/confirm")).json()

    _override_segmentation_px(2294)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("t2.png", png_bytes, "image/png")},
    )
    v2 = (await ac.post(f"/api/v1/visits/{r2.json()['id']}/confirm")).json()

    # Coba hapus kunjungan ke-1 saat kunjungan ke-2 masih ada -> harus 409 Conflict (LIFO)
    del_v1_early = await ac.delete(f"/api/v1/visits/{v1['id']}")
    assert del_v1_early.status_code == 409
    assert (storage_root / v1["image_path"]).is_file()

    # Hapus kunjungan terakhir (ke-2) -> berhasil 200 OK & berkas terhapus
    del_v2 = await ac.delete(f"/api/v1/visits/{v2['id']}")
    assert del_v2.status_code == 200
    assert not (storage_root / v2["image_path"]).exists()
    assert not (storage_root / v2["mask_path"]).exists()

    # Hapus seluruh pasien -> menghapus pasien beserta kunjungan ke-1 dan berkasnya
    del_patient = await ac.delete("/api/v1/patients/Patient_10")
    assert del_patient.status_code == 200
    assert del_patient.json()["deleted_patient_id"] == "PATIENT_10"
    assert not (storage_root / v1["image_path"]).exists()
    assert not (storage_root / v1["mask_path"]).exists()

    check_p = await ac.get("/api/v1/patients/Patient_10")
    assert check_p.status_code == 404


async def test_16_database_unique_constraints_0003(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    _ac, _ = visit_client
    test_engine = create_async_engine(settings.resolved_test_database_url, future=True)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    try:
        # 1. Uji indeks unik parsial: hanya satu draft aktif per pasien
        async with TestSessionLocal() as session:
            session.add(
                Visit(
                    patient_id="PATIENT_10",
                    visit_date=date(2026, 10, 1),
                    status="draft",
                    n_wound_px=1000,
                    area_pct=1.53,
                )
            )
            await session.commit()

            session.add(
                Visit(
                    patient_id="PATIENT_10",
                    visit_date=date(2026, 10, 2),
                    status="draft",
                    n_wound_px=1200,
                    area_pct=1.83,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

        # 2. Uji UNIQUE (patient_id, visit_index)
        async with TestSessionLocal() as session:
            session.add(
                Visit(
                    patient_id="PATIENT_10",
                    visit_date=date(2026, 10, 1),
                    status="final",
                    visit_index=1,
                    n_wound_px=1000,
                    area_pct=1.53,
                )
            )
            await session.commit()

            session.add(
                Visit(
                    patient_id="PATIENT_10",
                    visit_date=date(2026, 10, 8),
                    status="final",
                    visit_index=1,
                    n_wound_px=900,
                    area_pct=1.37,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
    finally:
        await test_engine.dispose()


async def test_17_upload_validation_rejects_non_image_oversized_and_backward_date(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, _ = visit_client
    _override_segmentation_px(3277)

    # 1. Berkas bukan gambar -> 422 Unprocessable Entity
    r_non_img = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("catatan.txt", b"ini bukan berkas gambar", "text/plain")},
    )
    assert r_non_img.status_code == 422

    # 2. Berkas > 10 MB -> 422 Unprocessable Entity
    oversized_bytes = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (10 * 1024 * 1024 + 64))
    r_oversize = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("besar.png", oversized_bytes, "image/png")},
    )
    assert r_oversize.status_code == 422

    # 3. Tanggal kunjungan mundur dari kunjungan final terakhir -> 422 Unprocessable Entity
    png_bytes = _make_dummy_png_bytes()
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("t1.png", png_bytes, "image/png")},
    )
    assert r1.status_code == 201
    c1 = await ac.post(f"/api/v1/visits/{r1.json()['id']}/confirm")
    assert c1.status_code == 200

    r_backward = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-10", "distance_confirmed": "true"},
        files={"file": ("t2_mundur.png", png_bytes, "image/png")},
    )
    assert r_backward.status_code == 422
    assert "tidak boleh lebih awal" in r_backward.json()["detail"]


async def test_18_exif_transpose_and_overlay_serving(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, storage_root = visit_client
    _override_segmentation_px(3277)

    # Buat citra JPEG 120x80 dengan EXIF Orientation = 6 (rotasi 90 derajat)
    raw_img = Image.new("RGB", (120, 80), color=(200, 120, 100))
    exif = raw_img.getexif()
    exif[0x0112] = 6  # Rotate 90 CW -> dimensi setelah exif_transpose harus (80, 120)
    buf = io.BytesIO()
    raw_img.save(buf, format="JPEG", exif=exif.tobytes())
    jpeg_with_exif = buf.getvalue()

    r = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("ponsel_exif.jpg", jpeg_with_exif, "image/jpeg")},
    )
    assert r.status_code == 201
    data = r.json()

    # Pastikan citra asli yang disimpan sudah berorientasi tegak (80x120)
    with Image.open(storage_root / data["image_path"]) as saved_orig:
        assert saved_orig.size == (80, 120)
        assert saved_orig.mode == "RGB"

    # Pastikan overlay 256x256 RGB tersimpan dan dapat diakses via endpoint storage
    with Image.open(storage_root / data["overlay_path"]) as saved_ov:
        assert saved_ov.size == (256, 256)
        assert saved_ov.mode == "RGB"

    ov_resp = await ac.get(f"/api/v1/storage/{data['overlay_path']}")
    assert ov_resp.status_code == 200
    assert ov_resp.headers["content-type"] == "image/png"


@pytest.mark.skipif(
    not resolve_checkpoint_path().is_file(),
    reason="Checkpoint model asli tidak ditemukan; lewati pengujian inferensi model asli.",
)
async def test_19_real_model_inference_and_manual_mask_verification(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, storage_root = visit_client
    # Hapus override agar menggunakan get_segmentation_service (model asli ResNet34UNet)
    app.dependency_overrides.pop(get_segmentation_service, None)

    model = get_loaded_model() or load_segmentation_model()
    assert model is not None
    assert not model.training
    assert model.count_parameters()["total_parameters"] == EXPECTED_RESNET34_UNET_PARAMS

    # Gunakan citra uji P10T_1.jpg jika tersedia, atau dummy PNG jika tidak
    candidates = [
        Path("/app/ml/test_set/Images/Patient_10/P10T_1.jpg"),
        Path("ml/test_set/Images/Patient_10/P10T_1.jpg"),
        Path("../ml/test_set/Images/Patient_10/P10T_1.jpg"),
    ]
    sample_path = next((p for p in candidates if p.is_file()), None)
    if sample_path is not None:
        img_bytes = sample_path.read_bytes()
        fname = "P10T_1.jpg"
        mime = "image/jpeg"
    else:
        img_bytes = _make_dummy_png_bytes()
        fname = "dummy.png"
        mime = "image/png"

    r = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": (fname, img_bytes, mime)},
    )
    assert r.status_code == 201
    data = r.json()

    # Waktu inferensi tercatat (ms)
    inf_ms = get_last_inference_ms()
    assert inf_ms is not None and inf_ms > 0.0

    # Verifikasi manual dari berkas masker 256x256 yang disimpan di disk
    mask_file = storage_root / data["mask_path"]
    overlay_file = storage_root / data["overlay_path"]
    assert mask_file.is_file()
    assert overlay_file.is_file()

    with Image.open(mask_file) as m_img:
        assert m_img.size == (256, 256)
        assert m_img.mode == "L"
        raw_bytes = list(m_img.tobytes())
        assert set(raw_bytes).issubset({0, 255})
        manual_n_wound_px = raw_bytes.count(255)

    manual_area_pct = round((manual_n_wound_px / 65536) * 100.0, 2)
    assert data["n_wound_px"] == manual_n_wound_px
    assert data["area_pct"] == manual_area_pct

    if sample_path is not None:
        # P10T_1 pada reference_metrics.csv: 8257 piksel (Windows) / 8258 piksel (Linux SIMD) -> 12.60%
        assert abs(manual_n_wound_px - 8257) <= 2
        assert manual_area_pct == 12.6


async def test_20_distance_confirmed_required(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, _ = visit_client
    _override_segmentation_px(3277)
    png_bytes = _make_dummy_png_bytes()

    # Tanpa distance_confirmed -> 422
    r_missing = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01"},
        files={"file": ("t1.png", png_bytes, "image/png")},
    )
    assert r_missing.status_code == 422

    # distance_confirmed=false -> 422
    r_false = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "false"},
        files={"file": ("t1.png", png_bytes, "image/png")},
    )
    assert r_false.status_code == 422

    # distance_confirmed=true -> 201
    r_true = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("t1.png", png_bytes, "image/png")},
    )
    assert r_true.status_code == 201
    assert r_true.json()["distance_confirmed"] is True


async def test_21_wib_early_morning_timezone_tolerance(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, _ = visit_client
    _override_segmentation_px(3277)
    png_bytes = _make_dummy_png_bytes()

    utc_today = datetime.now(timezone.utc).date()
    wib_early_morning_date = (utc_today + timedelta(days=1)).isoformat()
    too_far_future_date = (utc_today + timedelta(days=2)).isoformat()

    # Tanggal +1 hari dari UTC (simulasi 00:00-07:00 WIB) diterima (201)
    r_wib = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": wib_early_morning_date, "distance_confirmed": "true"},
        files={"file": ("wib.png", png_bytes, "image/png")},
    )
    assert r_wib.status_code == 201
    assert r_wib.json()["visit_date"] == wib_early_morning_date

    # Tanggal +2 hari dari UTC ditolak (422)
    r_future = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": too_far_future_date, "distance_confirmed": "true"},
        files={"file": ("future.png", png_bytes, "image/png")},
    )
    assert r_future.status_code == 422


async def test_22_pending_draft_query_and_discard(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, storage_root = visit_client
    _override_segmentation_px(3277)
    png_bytes = _make_dummy_png_bytes()

    r_draft = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-05", "distance_confirmed": "true"},
        files={"file": ("draft.png", png_bytes, "image/png")},
    )
    assert r_draft.status_code == 201
    draft_data = r_draft.json()

    # Query default (final) masih kosong
    r_final = await ac.get("/api/v1/patients/Patient_10/visits")
    assert r_final.status_code == 200
    assert r_final.json() == []

    # Query status=draft mengembalikan draf yang menggantung
    r_pending = await ac.get("/api/v1/patients/Patient_10/visits?status=draft")
    assert r_pending.status_code == 200
    drafts = r_pending.json()
    assert len(drafts) == 1
    assert drafts[0]["id"] == draft_data["id"]
    assert drafts[0]["status"] == "draft"

    # Buang draf -> berkas dan baris DB terhapus
    r_del = await ac.delete(f"/api/v1/visits/{draft_data['id']}")
    assert r_del.status_code == 200
    assert not (storage_root / draft_data["image_path"]).exists()

    r_after = await ac.get("/api/v1/patients/Patient_10/visits?status=draft")
    assert r_after.json() == []


async def test_23_exif_and_gps_stripped_from_stored_file(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, storage_root = visit_client
    _override_segmentation_px(3277)

    raw_img = Image.new("RGB", (100, 80), color=(190, 110, 95))
    exif = raw_img.getexif()
    exif[0x0112] = 1  # Orientation normal
    exif[0x010F] = "CameraSecretMake"  # Make tag
    exif[0x0110] = "PhoneGPSModel"  # Model tag
    exif[0x8825] = {1: "S", 2: (7, 15, 30), 3: "E", 4: (112, 45, 0)}  # GPSInfo IFD
    buf = io.BytesIO()
    raw_img.save(buf, format="JPEG", exif=exif.tobytes())
    jpeg_with_gps = buf.getvalue()
    assert b"CameraSecretMake" in jpeg_with_gps

    r = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("gps_photo.jpg", jpeg_with_gps, "image/jpeg")},
    )
    assert r.status_code == 201
    saved_file = storage_root / r.json()["image_path"]
    saved_bytes = saved_file.read_bytes()

    assert b"CameraSecretMake" not in saved_bytes
    assert b"PhoneGPSModel" not in saved_bytes
    with Image.open(saved_file) as saved_img:
        assert len(saved_img.getexif()) == 0
        assert "exif" not in saved_img.info


async def test_24_storage_whitelist_and_path_traversal_rejected(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    ac, storage_root = visit_client

    # Buat berkas rahasia di luar subdir yang diizinkan
    outside_secret = storage_root.parent / "secret_outside.txt"
    outside_secret.write_text("rahasia", encoding="utf-8")
    root_secret = storage_root / "secret_root.txt"
    root_secret.write_text("rahasia_root", encoding="utf-8")

    # 1. Subdir tidak dalam daftar putih -> 404
    r_bad_sub = await ac.get("/api/v1/storage/secrets/secret_root.txt")
    assert r_bad_sub.status_code == 404

    # 2. Percobaan .. pada filename (encoded maupun literal) -> 404
    for bad_path in (
        "/api/v1/storage/uploads/..%2Fsecret_root.txt",
        "/api/v1/storage/uploads/..%5Csecret_root.txt",
        "/api/v1/storage/uploads/..",
    ):
        resp = await ac.get(bad_path)
        assert resp.status_code == 404

    # 3. Fungsi resolve_storage_path menolak path di luar root storage
    with pytest.raises(ValueError):
        resolve_storage_path("../secret_outside.txt")
    with pytest.raises(ValueError):
        resolve_storage_path("uploads/../../secret_outside.txt")
    with pytest.raises(ValueError):
        resolve_storage_path("")


# ==============================================================================
# FASE 3 (H4: SK-3 Evaluasi Grounding LLM, Konfirmasi, PAC, & Fallback Tabel 3.5)
# ==============================================================================


async def test_25_sk3_k4_confirm_menurun_gemini_mocked(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    """SK-3 K4: A0=5.00%, At=3.50% -> delta_A=-1.50%, PAC=+30.00% -> Tren Menurun."""
    ac, _ = visit_client
    png_bytes = _make_dummy_png_bytes()

    # 1. Baseline A0 = 5.00% (3277 px)
    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("v1.png", png_bytes, "image/png")},
    )
    v1_id = r1.json()["id"]
    await ac.post(f"/api/v1/visits/{v1_id}/confirm")

    # 2. Visit 2 At = 3.50% (2294 px)
    _override_segmentation_px(2294)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("v2.png", png_bytes, "image/png")},
    )
    v2_id = r2.json()["id"]

    mock_called = 0

    async def _mock_narrative(a0, at, delta_a, pac, trend_status, badge):
        nonlocal mock_called
        mock_called += 1
        assert a0 == 5.0
        assert at == 3.5
        assert delta_a == -1.5
        assert pac == 30.0
        assert badge == "menurun"
        assert trend_status == "Tren Menurun (Area Luka Mengecil)"
        return (
            "Evaluasi Longitudinal: Area luka terukur menurun dari 5.00% menjadi 3.50% (PAC: +30.00%, ΔA: -1.50%). Hasil estimasi berdasarkan foto memerlukan pemeriksaan langsung tenaga medis.",
            "Area luka terdeteksi mengecil berkurang sekitar 30.00%. Hasil ini merupakan estimasi berdasarkan foto dan memerlukan pemeriksaan langsung dokter.",
            "llm",
        )

    app.dependency_overrides[get_narrative_service] = lambda: _mock_narrative

    c2 = await ac.post(f"/api/v1/visits/{v2_id}/confirm")
    assert c2.status_code == 200
    b2 = c2.json()
    assert mock_called == 1
    assert b2["status"] == "final"
    assert b2["visit_index"] == 2
    assert b2["area_pct"] == 3.5
    assert b2["delta_area"] == -1.5
    assert b2["pac"] == 30.0
    assert b2["trend_status"] == "Tren Menurun (Area Luka Mengecil)"
    assert b2["narrative_source"] == "llm"
    assert "30.00%" in b2["patient_narrative"]
    assert "5.00%" in b2["clinician_notes"]


async def test_26_sk3_k5_confirm_stabil_gemini_mocked(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    """SK-3 K5: A0=5.00%, At=4.90% -> delta_A=-0.10%, PAC=+2.00% -> Tren Stabil."""
    ac, _ = visit_client
    png_bytes = _make_dummy_png_bytes()

    # Baseline A0 = 5.00%
    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("v1.png", png_bytes, "image/png")},
    )
    v1_id = r1.json()["id"]
    await ac.post(f"/api/v1/visits/{v1_id}/confirm")

    # Visit 2 At = 4.90% (3211 px -> delta_A = -0.10, PAC = +2.00%)
    _override_segmentation_px(3211)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("v2.png", png_bytes, "image/png")},
    )
    v2_id = r2.json()["id"]

    async def _mock_narrative(a0, at, delta_a, pac, trend_status, badge):
        assert badge == "stabil"
        assert pac == 2.0
        assert delta_a == -0.1
        return (
            "Evaluasi Longitudinal: Tidak terdeteksi perubahan berarti (5.00% -> 4.90%, PAC: +2.00%, ΔA: -0.10%). Hasil pengukuran estimasi berdasarkan foto memerlukan pemeriksaan langsung tenaga medis.",
            "Area luka relatif stabil dengan luas sekitar 4.90%. Hasil merupakan estimasi berdasarkan foto dan memerlukan pemeriksaan langsung dokter.",
            "llm",
        )

    app.dependency_overrides[get_narrative_service] = lambda: _mock_narrative

    c2 = await ac.post(f"/api/v1/visits/{v2_id}/confirm")
    assert c2.status_code == 200
    b2 = c2.json()
    assert b2["pac"] == 2.0
    assert b2["delta_area"] == -0.1
    assert b2["trend_status"] == "Tren Stabil (Perubahan Minimal)"
    assert b2["narrative_source"] == "llm"


async def test_27_sk3_k6_confirm_meningkat_gemini_mocked(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    """SK-3 K6: A0=5.00%, At=6.50% -> delta_A=+1.50%, PAC=-30.00% -> Tren Meningkat."""
    ac, _ = visit_client
    png_bytes = _make_dummy_png_bytes()

    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("v1.png", png_bytes, "image/png")},
    )
    await ac.post(f"/api/v1/visits/{r1.json()['id']}/confirm")

    # Visit 2 At = 6.50% (4260 px -> delta_A = +1.50, PAC = -30.00%)
    _override_segmentation_px(4260)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("v2.png", png_bytes, "image/png")},
    )
    v2_id = r2.json()["id"]

    async def _mock_narrative(a0, at, delta_a, pac, trend_status, badge):
        assert badge == "meningkat"
        assert pac == -30.0
        assert delta_a == 1.5
        return (
            "Evaluasi Longitudinal: Area luka terukur meningkat dari 5.00% menjadi 6.50% (PAC: -30.00%, ΔA: +1.50%). Hasil estimasi berdasarkan foto memerlukan pemeriksaan langsung tenaga medis.",
            "Area luka terdeteksi membesar bertambah sekitar 30.00%. Hasil ini estimasi berdasarkan foto dan memerlukan pemeriksaan langsung dokter.",
            "llm",
        )

    app.dependency_overrides[get_narrative_service] = lambda: _mock_narrative

    c2 = await ac.post(f"/api/v1/visits/{v2_id}/confirm")
    assert c2.status_code == 200
    b2 = c2.json()
    assert b2["pac"] == -30.0
    assert b2["delta_area"] == 1.5
    assert b2["trend_status"] == "Tren Meningkat (Area Luka Membesar)"
    assert b2["narrative_source"] == "llm"


async def test_28_sk3_k7_confirm_exact_boundary_stabil(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    """SK-3 K7: A0=10.00%, At=9.50% -> PAC tepat +5.00%, delta_A=-0.50% -> Tren Stabil (Batas Eksak)."""
    ac, _ = visit_client
    png_bytes = _make_dummy_png_bytes()

    # Baseline A0 = 10.00% (6554 px)
    _override_segmentation_px(6554)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("v1.png", png_bytes, "image/png")},
    )
    await ac.post(f"/api/v1/visits/{r1.json()['id']}/confirm")

    # Visit 2 At = 9.50% (6226 px -> PAC = (10.00 - 9.50)/10.00 = +5.00%)
    _override_segmentation_px(6226)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("v2.png", png_bytes, "image/png")},
    )
    c2 = await ac.post(f"/api/v1/visits/{r2.json()['id']}/confirm")
    assert c2.status_code == 200
    b2 = c2.json()
    assert b2["pac"] == 5.0
    assert b2["delta_area"] == -0.5
    assert b2["trend_status"] == "Tren Stabil (Perubahan Minimal)"


async def test_29_sk3_k8_foreign_numbers_rejected_and_fallback() -> None:
    """SK-3 K8: Narasi LLM yang mengandung angka asing di luar input ditolak dan fallback."""
    a0 = 5.0
    at = 3.5
    delta_a = -1.5
    pac = 30.0
    badge = "menurun"

    # Narasi dengan angka asing 45.0% dan 12.5%
    c_notes_bad = "Evaluasi: luas luka 45.0% dan PAC +30.00%. Estimasi visual memerlukan pemeriksaan langsung tenaga medis."
    p_text_bad = "Luka mengecil sekitar 12.5%. Estimasi visual memerlukan pemeriksaan langsung dokter."
    is_valid, reason = validate_narrative_text(c_notes_bad, p_text_bad, a0, at, delta_a, pac, badge)
    assert not is_valid
    assert "Angka asing" in reason

    # Verifikasi templat fallback Tabel 3.5 persis yang dihasilkan
    c_fb, p_fb, src = generate_fallback_narrative(a0, at, delta_a, pac, badge)
    assert src == "template_fallback"
    assert "5.00%" in c_fb
    assert "3.50%" in c_fb
    assert "+30.00%" in c_fb
    assert "30.00%" in p_fb


async def test_30_sk3_k9_timeout_error_malformed_json_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SK-3 K9: Timeout (>10s), network error, dan JSON rusak beralih ke templat fallback."""
    a0 = 5.0
    at = 3.5
    delta_a = -1.5
    pac = 30.0
    trend_status = "Tren Menurun (Area Luka Mengecil)"
    badge = "menurun"

    # 1. Timeout (>10s)
    async def mock_post_timeout(*args, **kwargs):
        raise httpx.TimeoutException("Read timeout > 10s")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_timeout)
    c1, p1, s1 = await generate_longitudinal_narrative(
        a0, at, delta_a, pac, trend_status, badge, api_key="test_key"
    )
    assert s1 == "template_fallback"
    assert "30.00%" in p1

    # 2. HTTP 500 error
    async def mock_post_500(*args, **kwargs):
        return httpx.Response(500, text="Internal Server Error")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_500)
    c2, p2, s2 = await generate_longitudinal_narrative(
        a0, at, delta_a, pac, trend_status, badge, api_key="test_key"
    )
    assert s2 == "template_fallback"

    # 3. JSON rusak / bukan format JSON
    async def mock_post_malformed(*args, **kwargs):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Bukan format JSON yang valid"}]}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post_malformed)
    c3, p3, s3 = await generate_longitudinal_narrative(
        a0, at, delta_a, pac, trend_status, badge, api_key="test_key"
    )
    assert s3 == "template_fallback"


async def test_31_sk3_k10_gemini_payload_no_pii_and_forbidden_words() -> None:
    """SK-3 K10: Payload hanya 5 parameter tanpa PII, dan larangan kata terlarang."""
    prompt = build_gemini_user_prompt(
        a0=10.26,
        at=8.10,
        delta_a=-2.16,
        pac=21.05,
        trend_status="Tren Menurun (Area Luka Mengecil)",
    )

    # Pastikan tepat 5 field tanpa data pribadi pasien
    assert "A0: 10.26%" in prompt
    assert "At: 8.10%" in prompt
    assert "delta_A: -2.16%" in prompt
    assert "PAC: +21.05%" in prompt
    assert "trend_status: Tren Menurun (Area Luka Mengecil)" in prompt

    forbidden_pii = ["Patient", "RM", "nama", "umur", "jk", "lokasi", "foto", "image"]
    for pii in forbidden_pii:
        assert pii not in prompt.lower()

    # Validasi kata terlarang
    for word in FORBIDDEN_WORDS:
        bad_notes = f"Kondisi luka {word} secara klinis. Estimasi visual memerlukan pemeriksaan langsung tenaga medis."
        good_patient = "Luka terdeteksi mengecil sekitar 21.05%. Estimasi visual memerlukan pemeriksaan langsung dokter."
        is_val, reason = validate_narrative_text(
            bad_notes, good_patient, 10.26, 8.10, -2.16, 21.05, "menurun"
        )
        assert not is_val
        assert "Kata terlarang" in reason


async def test_32_baseline_visit_does_not_call_llm(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    """Kunjungan baseline (t=1) tidak pernah memanggil LLM."""
    ac, _ = visit_client
    png_bytes = _make_dummy_png_bytes()

    llm_called = False

    async def _mock_narrative(*args, **kwargs):
        nonlocal llm_called
        llm_called = True
        return ("a", "b", "llm")

    app.dependency_overrides[get_narrative_service] = lambda: _mock_narrative

    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("v1.png", png_bytes, "image/png")},
    )
    c1 = await ac.post(f"/api/v1/visits/{r1.json()['id']}/confirm")
    assert c1.status_code == 200
    b1 = c1.json()
    assert not llm_called
    assert b1["visit_index"] == 1
    assert b1["pac"] is None
    assert b1["clinician_notes"] is None
    assert b1["patient_narrative"] is None
    assert b1["narrative_source"] is None


async def test_33_a0_zero_baseline_does_not_call_llm_and_shows_notice(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    """Jika A0=0, PAC tidak dapat dihitung, LLM tidak dipanggil, dan fallback aman."""
    ac, _ = visit_client
    png_bytes = _make_dummy_png_bytes()

    llm_called = False

    async def _mock_narrative(*args, **kwargs):
        nonlocal llm_called
        llm_called = True
        return ("a", "b", "llm")

    app.dependency_overrides[get_narrative_service] = lambda: _mock_narrative

    # Baseline dengan 0 piksel
    _override_segmentation_px(0)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("v1.png", png_bytes, "image/png")},
    )
    await ac.post(f"/api/v1/visits/{r1.json()['id']}/confirm")

    # Kunjungan 2 dengan 1311 piksel (2.00%)
    _override_segmentation_px(1311)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("v2.png", png_bytes, "image/png")},
    )
    c2 = await ac.post(f"/api/v1/visits/{r2.json()['id']}/confirm")
    assert c2.status_code == 200
    b2 = c2.json()
    assert not llm_called
    assert b2["pac"] is None
    assert b2["narrative_source"] == "template_fallback"
    assert "A₀ = 0" in b2["clinician_notes"]


async def test_34_concurrent_confirm_does_not_call_gemini_twice(
    visit_client: tuple[AsyncClient, Path],
) -> None:
    """Konfirmasi bersamaan (konkuren) pada draf yang sama tidak memanggil LLM dua kali."""
    ac, _ = visit_client
    png_bytes = _make_dummy_png_bytes()

    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("v1.png", png_bytes, "image/png")},
    )
    await ac.post(f"/api/v1/visits/{r1.json()['id']}/confirm")

    _override_segmentation_px(2294)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("v2.png", png_bytes, "image/png")},
    )
    v2_id = r2.json()["id"]

    call_count = 0

    async def _mock_narrative(a0, at, delta_a, pac, trend_status, badge):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # Simulasi jeda network
        return (
            "Evaluasi Longitudinal: Area luka menurun dari 5.00% ke 3.50% (PAC: +30.00%, ΔA: -1.50%). Estimasi visual memerlukan pemeriksaan langsung tenaga medis.",
            "Area luka mengecil berkurang sekitar 30.00%. Estimasi visual memerlukan pemeriksaan langsung dokter.",
            "llm",
        )

    app.dependency_overrides[get_narrative_service] = lambda: _mock_narrative

    # Panggil confirm serentak
    resp1, resp2 = await asyncio.gather(
        ac.post(f"/api/v1/visits/{v2_id}/confirm"),
        ac.post(f"/api/v1/visits/{v2_id}/confirm"),
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["confirmed_at"] == resp2.json()["confirmed_at"]
    assert call_count == 1, f"LLM harus dipanggil tepat 1 kali, tapi terpanggil {call_count} kali"


async def test_35_reversed_trend_direction_rejected_and_fallback() -> None:
    """Arah tren terbalik pada narasi LLM ditolak dan beralih ke fallback."""
    # Kasus menurun, tapi teks menyebut membesar/bertambah
    notes = "Evaluasi: luka dari 5.00% ke 3.50% (PAC: +30.00%, ΔA: -1.50%). Estimasi visual memerlukan pemeriksaan langsung tenaga medis."
    bad_patient = "Area luka terdeteksi membesar bertambah sekitar 30.00%. Estimasi visual memerlukan pemeriksaan langsung dokter."
    is_val, reason = validate_narrative_text(notes, bad_patient, 5.0, 3.5, -1.5, 30.0, "menurun")
    assert not is_val
    assert "Arah tren terbalik" in reason


async def test_36_real_gemini_api_call_manual() -> None:
    """Uji manual panggilan nyata ke Gemini API jika GEMINI_API_KEY disetel di env."""
    if not settings.gemini_api_key:
        pytest.skip("belum diverifikasi (GEMINI_API_KEY kosong)")

    c_notes, p_narrative, src = await generate_longitudinal_narrative(
        a0=10.26,
        at=8.10,
        delta_a=-2.16,
        pac=21.05,
        trend_status="Tren Menurun (Area Luka Mengecil)",
        badge="menurun",
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=10.0,
    )
    assert src in ("llm", "template_fallback")
    assert len(c_notes) > 20
    assert len(p_narrative) > 20


