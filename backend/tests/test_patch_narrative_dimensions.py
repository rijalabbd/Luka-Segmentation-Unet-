from collections.abc import AsyncGenerator
import io
import json
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from PIL import Image
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.patient import Patient, Visit
from app.services import narrative as narrative_module
from app.services.narrative import (
    SYSTEM_PROMPT_TABEL_3_4,
    generate_fallback_narrative,
    validate_narrative_output,
)
from app.services.segmentation import SegmentationFn, get_segmentation_service
from app.services.storage import generate_stub_binary_mask_png


def _override_segmentation_px(n_px: int) -> None:
    def _custom_segment(_image_bytes: bytes) -> tuple[int, bytes]:
        return n_px, generate_stub_binary_mask_png(n_px)

    def _get_custom_service() -> SegmentationFn:
        return _custom_segment

    app.dependency_overrides[get_segmentation_service] = _get_custom_service


@pytest.fixture
async def patch_client(
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


async def test_p3_stored_image_dimensions_match_columns_exif_and_non_square(
    patch_client: tuple[AsyncClient, Path],
) -> None:
    """P3: img_width_px dan img_height_px harus persis sama dengan dimensi citra dari endpoint storage."""
    ac, _ = patch_client
    _override_segmentation_px(3277)

    # Kasus 1: JPEG 160x100 dengan EXIF Orientation=6 (rotasi 90 deg CW -> pasca-transpose 100x160)
    raw_exif_img = Image.new("RGB", (160, 100), color=(210, 130, 110))
    exif = raw_exif_img.getexif()
    exif[0x0112] = 6
    buf_exif = io.BytesIO()
    raw_exif_img.save(buf_exif, format="JPEG", exif=exif.tobytes())

    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("exif_non_std.jpg", buf_exif.getvalue(), "image/jpeg")},
    )
    assert r1.status_code == 201, r1.text
    v1 = r1.json()
    assert v1["img_width_px"] == 100
    assert v1["img_height_px"] == 160

    dl1 = await ac.get(f"/api/v1/storage/{v1['image_path']}")
    assert dl1.status_code == 200
    with Image.open(io.BytesIO(dl1.content)) as stored_1:
        assert stored_1.size == (v1["img_width_px"], v1["img_height_px"]) == (100, 160)
        assert stored_1.getexif().get(0x0112) is None
        print(
            f"\n[P3-EXIF] path={v1['image_path']} db=({v1['img_width_px']}x{v1['img_height_px']}) "
            f"storage=({stored_1.width}x{stored_1.height}) exif_orientation={stored_1.getexif().get(0x0112)}"
        )

    # Kasus 2: PNG tidak persegi 640x360
    rect_img = Image.new("RGB", (640, 360), color=(170, 95, 85))
    buf_rect = io.BytesIO()
    rect_img.save(buf_rect, format="PNG")

    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-05", "distance_confirmed": "true"},
        files={"file": ("non_square.png", buf_rect.getvalue(), "image/png")},
    )
    assert r2.status_code == 201, r2.text
    v2 = r2.json()
    assert v2["img_width_px"] == 640
    assert v2["img_height_px"] == 360

    dl2 = await ac.get(f"/api/v1/storage/{v2['image_path']}")
    assert dl2.status_code == 200
    with Image.open(io.BytesIO(dl2.content)) as stored_2:
        assert stored_2.size == (v2["img_width_px"], v2["img_height_px"]) == (640, 360)
        print(
            f"[P3-RECT] path={v2['image_path']} db=({v2['img_width_px']}x{v2['img_height_px']}) "
            f"storage=({stored_2.width}x{stored_2.height})"
        )


async def test_p4_system_prompt_unit_clauses_calming_phrases_and_meningkat_consultation(
    patch_client: tuple[AsyncClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P4: Klausa satuan dua mode di system prompt, tolak kalimat menenangkan, dan wajibkan ajakan konsultasi Tren Meningkat."""
    ac, _ = patch_client

    # 1. Verifikasi klausa kondisional % dan cm² hadir di SYSTEM_PROMPT_TABEL_3_4
    assert 'Jika masukan tidak memuat field "satuan"' in SYSTEM_PROMPT_TABEL_3_4
    assert "dilarang menggunakan satuan cm atau cm²" in SYSTEM_PROMPT_TABEL_3_4
    assert 'Jika masukan memuat "satuan": "cm²"' in SYSTEM_PROMPT_TABEL_3_4
    assert 'istilah "poin persentase" dilarang' in SYSTEM_PROMPT_TABEL_3_4

    # 2. Validator menolak keempat frasa menenangkan pada seluruh status tren
    calming_phrases = ("tenang", "jangan khawatir", "tidak perlu cemas", "baik-baik saja")
    trend_cases: tuple[tuple[str, float, float, float, float], ...] = (
        ("menurun", 5.00, 3.50, -1.50, 30.00),
        ("stabil", 5.00, 4.90, -0.10, 2.00),
        ("meningkat", 5.00, 6.50, 1.50, -30.00),
    )
    for badge, a0, at, delta_a, pac in trend_cases:
        c_raw, p_ok, _ = generate_fallback_narrative(a0, at, delta_a, pac, badge)  # type: ignore[arg-type]
        c_ok = (
            c_raw
            if "estimasi" in c_raw.lower() and "foto" in c_raw.lower()
            else f"{c_raw} Hasil ini merupakan estimasi berdasarkan foto, bukan diagnosis medis."
        )
        for phrase in calming_phrases:
            ok, reason = validate_narrative_output(
                c_ok,
                f"{p_ok} Tetap {phrase}.",
                a0=a0,
                at=at,
                delta_a=delta_a,
                pac=pac,
                badge=badge,  # type: ignore[arg-type]
            )
            assert ok is False
            assert reason == f"kata_terlarang:patient_narrative:{phrase}"

    # 3. Validator menolak Tren Meningkat tanpa ajakan konsultasi dan menerimanya bila ada ajakan
    c_inc_raw, p_inc, _ = generate_fallback_narrative(5.00, 6.50, 1.50, -30.00, "meningkat")
    c_inc = f"{c_inc_raw} Hasil ini merupakan estimasi berdasarkan foto, bukan diagnosis medis."
    p_no_consult = (
        "Berdasarkan hasil pengukuran sistem, area luka terdeteksi lebih besar (bertambah sekitar 30.00%). "
        "Hasil ini merupakan estimasi berdasarkan foto, bukan diagnosis medis."
    )
    ok_no_consult, reason_no_consult = validate_narrative_output(
        c_inc,
        p_no_consult,
        a0=5.00,
        at=6.50,
        delta_a=1.50,
        pac=-30.00,
        badge="meningkat",
    )
    assert ok_no_consult is False
    assert reason_no_consult == "ajakan_konsultasi_hilang:patient_narrative"

    ok_with_consult, reason_with_consult = validate_narrative_output(
        c_inc,
        p_inc,
        a0=5.00,
        at=6.50,
        delta_a=1.50,
        pac=-30.00,
        badge="meningkat",
    )
    assert ok_with_consult is True, reason_with_consult

    # 4. Uji integrasi endpoint confirm saat Gemini mengirim kalimat menenangkan atau tanpa ajakan konsultasi -> fallback
    monkeypatch.setattr(settings, "gemini_api_key", "fake-patch-key")
    _override_segmentation_px(3277)
    r1 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
        files={"file": ("b1.png", _png_bytes(64, 64), "image/png")},
    )
    await ac.post(f"/api/v1/visits/{r1.json()['id']}/confirm")

    async def _mock_meningkat_calming(**_kwargs: object) -> dict[str, object]:
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "clinician_notes": c_inc,
                                        "patient_narrative": f"{p_inc} Tetap tenang dan jangan khawatir.",
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(narrative_module, "request_gemini_api", _mock_meningkat_calming)
    _override_segmentation_px(4260)
    r2 = await ac.post(
        "/api/v1/patients/Patient_10/visits",
        data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
        files={"file": ("b2.png", _png_bytes(64, 64), "image/png")},
    )
    c2 = await ac.post(f"/api/v1/visits/{r2.json()['id']}/confirm")
    assert c2.status_code == 200
    body2 = c2.json()
    assert body2["narrative_source"] == "template_fallback"
    assert "tenang" not in body2["patient_narrative"].lower()
    assert "jangan khawatir" not in body2["patient_narrative"].lower()


def _png_bytes(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), color=(180, 90, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
