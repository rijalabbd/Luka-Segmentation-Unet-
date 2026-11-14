from collections.abc import AsyncGenerator
import io
import os
from pathlib import Path

from httpx import ASGITransport, AsyncClient
import numpy as np
from PIL import Image
from pydantic import ValidationError
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, settings
from app.core.database import get_db
from app.main import app
from app.services import segmentation as seg_module
from app.services.segmentation import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    get_model_identity,
    load_segmentation_model,
    preprocess_image_bytes,
    resolve_checkpoint_path,
    run_model_segmentation,
)


def _make_solid_png_bytes(r: int = 128, g: int = 64, b: int = 192, size: int = 32) -> bytes:
    img = Image.new("RGB", (size, size), color=(r, g, b))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
async def phase3c_client() -> AsyncGenerator[AsyncClient, None]:
    test_engine = create_async_engine(settings.resolved_test_database_url, future=True)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await test_engine.dispose()


def test_c1_01_normalization_modes_produce_distinct_expected_tensors() -> None:
    """Dua mode normalisasi menghasilkan tensor yang berbeda dan sesuai rumus masing-masing."""
    png_bytes = _make_solid_png_bytes(128, 64, 192, size=64)

    t_zero_one = preprocess_image_bytes(png_bytes, normalization="zero_one", input_size=256)
    t_imagenet = preprocess_image_bytes(png_bytes, normalization="imagenet", input_size=256)

    assert t_zero_one.shape == (1, 3, 256, 256)
    assert t_imagenet.shape == (1, 3, 256, 256)
    assert t_zero_one.dtype == t_imagenet.dtype

    raw_rgb = np.array([128.0, 64.0, 192.0], dtype=np.float32) / 255.0
    expected_zero_one = raw_rgb
    expected_imagenet = (raw_rgb - IMAGENET_MEAN.reshape(3)) / IMAGENET_STD.reshape(3)

    np.testing.assert_allclose(t_zero_one[0, :, 0, 0].numpy(), expected_zero_one, atol=1e-5)
    np.testing.assert_allclose(t_imagenet[0, :, 0, 0].numpy(), expected_imagenet, atol=1e-5)
    assert not np.allclose(t_zero_one.numpy(), t_imagenet.numpy())


def test_c1_02_invalid_model_settings_rejected_with_clear_message() -> None:
    """Konfigurasi model yang tidak valid ditolak dengan pesan jelas."""
    with pytest.raises(ValidationError, match="MODEL_NORMALIZATION"):
        Settings(model_normalization="zscore_unknown")

    with pytest.raises(ValidationError, match="MODEL_INPUT_SIZE"):
        Settings(model_input_size=100)

    with pytest.raises(ValidationError, match="MODEL_BINARY_THRESHOLD"):
        Settings(model_binary_threshold=1.5)

    with pytest.raises(ValidationError, match="MODEL_CHECKPOINT_PATH"):
        Settings(model_checkpoint_path="   ")


def test_c1_03_missing_checkpoint_raises_clear_error_not_silent_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checkpoint yang tidak ada menghasilkan FileNotFoundError yang jelas dan identitas loaded=False."""
    png_bytes = _make_solid_png_bytes()
    monkeypatch.setattr(seg_module, "_MODEL", None)
    monkeypatch.setattr(settings, "model_checkpoint_path", "ml/checkpoints/tidak_pernah_ada_c1.pth")

    assert load_segmentation_model() is None
    identity = get_model_identity()
    assert identity["checkpoint_name"] == "tidak_pernah_ada_c1.pth"
    assert identity["checkpoint_sha256_short"] is None
    assert identity["loaded"] is False

    with pytest.raises(FileNotFoundError, match="tidak_pernah_ada_c1\\.pth"):
        load_segmentation_model(require_exists=True)

    with pytest.raises(FileNotFoundError, match="tidak_pernah_ada_c1\\.pth"):
        run_model_segmentation(png_bytes)


async def test_c1_04_health_endpoint_exposes_model_identity_without_sensitive_path(
    phase3c_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Endpoint health menyertakan identitas model tanpa membocorkan path absolut sensitif."""
    res = await phase3c_client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "model" in body

    model_info = body["model"]
    assert model_info["checkpoint_name"] == Path(settings.model_checkpoint_path).name
    assert "/" not in model_info["checkpoint_name"]
    assert "\\" not in model_info["checkpoint_name"]
    assert model_info["normalization"] == settings.model_normalization
    assert model_info["input_size"] == settings.model_input_size
    assert model_info["binary_threshold"] == settings.model_binary_threshold

    if resolve_checkpoint_path().is_file():
        assert isinstance(model_info["checkpoint_sha256_short"], str)
        assert len(model_info["checkpoint_sha256_short"]) == 12
    else:
        assert model_info["checkpoint_sha256_short"] is None


def test_c2_01_gemini_settings_validation_and_request_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parameter layanan Gemini dibaca dari konfigurasi dan nilai tidak valid ditolak."""
    with pytest.raises(ValidationError, match="GEMINI_TEMPERATURE"):
        Settings(gemini_temperature=2.5)
    with pytest.raises(ValidationError, match="GEMINI_MAX_OUTPUT_TOKENS"):
        Settings(gemini_max_output_tokens=16)
    with pytest.raises(ValidationError, match="GEMINI_TIMEOUT_SECONDS"):
        Settings(gemini_timeout_seconds=0)
    with pytest.raises(ValidationError, match="GEMINI_MODEL"):
        Settings(gemini_model="   ")

    import asyncio
    import httpx
    from app.services import narrative as narrative_module

    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    class _FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self, url: str, *, json: dict[str, object], headers: dict[str, str]
        ) -> _FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(settings, "gemini_api_key", "fake-c2-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-test-model")
    monkeypatch.setattr(settings, "gemini_temperature", 0.15)
    monkeypatch.setattr(settings, "gemini_max_output_tokens", 640)
    monkeypatch.setattr(settings, "gemini_timeout_seconds", 7.5)

    asyncio.run(
        narrative_module.request_gemini_api(
            user_payload={"A0": 5.0, "A_t": 3.5, "delta_A": -1.5, "PAC": 30.0, "trend_status": "Tren Menurun"},
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
        )
    )

    assert "gemini-test-model:generateContent" in str(captured["url"])
    assert captured["timeout"] == 7.5
    gen_cfg = captured["json"]["generationConfig"]  # type: ignore[index]
    assert gen_cfg["temperature"] == 0.15
    assert gen_cfg["maxOutputTokens"] == 640
    assert "fake-c2-key" == captured["headers"]["x-goog-api-key"]  # type: ignore[index]


async def test_c3_seeded_visits_with_pac_have_explicit_pac_basis_and_pac_rel() -> None:
    """C3: Setelah seed_demo_patients, tidak ada kunjungan final berPAC dengan pac_basis null."""
    from sqlalchemy import delete, select
    from app.models.patient import Patient, Visit
    from app.services.seed import seed_demo_patients

    test_engine = create_async_engine(settings.resolved_test_database_url, future=True)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    try:
        async with TestSessionLocal() as session:
            await session.execute(delete(Visit))
            await session.execute(delete(Patient))
            await session.commit()
            await seed_demo_patients(session)

            visits = (await session.execute(select(Visit).where(Visit.status == "final"))).scalars().all()
            assert len(visits) >= 6
            for v in visits:
                assert v.measure_mode == "relative"
                if v.pac is not None:
                    assert v.pac_basis == "relative"
                    assert v.pac_rel == pytest.approx(v.pac)
            null_basis_with_pac = [v for v in visits if v.pac is not None and v.pac_basis is None]
            assert null_basis_with_pac == []

            await session.execute(delete(Visit))
            await session.execute(delete(Patient))
            await session.commit()
    finally:
        await test_engine.dispose()


def test_c4_01_fallback_comma_format_all_trends_and_units() -> None:
    """C4: Semua templat fallback memakai koma desimal (tanpa angka bertitik) untuk 3 tren x 2 satuan."""
    import re
    from app.services.narrative import generate_fallback_narrative, validate_narrative_output

    cases = [
        ("menurun", 12.60, 8.82, -3.78, 30.00),
        ("stabil", 12.60, 12.35, -0.25, 1.98),
        ("meningkat", 12.60, 26.37, 13.77, -109.29),
    ]
    for unit in ("%", "cm²"):
        for badge, a0, at, delta_a, pac in cases:
            c_notes, p_narr, src = generate_fallback_narrative(
                a0=a0, at=at, delta_a=delta_a, pac=pac, badge=badge, unit=unit  # type: ignore[arg-type]
            )
            assert src == "template_fallback"
            combined = f"{c_notes}\n{p_narr}"
            assert re.search(r"\d+\.\d+", combined) is None, f"Masih ada desimal bertitik pada {badge} {unit}: {combined}"
            assert f"{a0:.2f}".replace(".", ",") in c_notes
            assert f"{at:.2f}".replace(".", ",") in c_notes
            ok, reason = validate_narrative_output(
                c_notes,
                p_narr,
                a0=a0,
                at=at,
                delta_a=delta_a,
                pac=pac,
                badge=badge,  # type: ignore[arg-type]
                unit=unit,  # type: ignore[arg-type]
            )
            assert ok is True, f"{badge} {unit}: {reason}"


def test_c4_02_validator_accepts_comma_and_dot_and_rejects_mismatch() -> None:
    """C4: Validator menerima 26,37% dan 26.37%, namun menolak 26,38% (selisih di atas toleransi pembulatan)."""
    from app.services.narrative import validate_narrative_output

    a0, at, delta_a, pac = 12.60, 26.37, 13.77, -109.29
    p_narr = (
        "Dari hasil pengukuran terbaru, area luka mengalami peningkatan sebesar 109,29% dibandingkan pemeriksaan awal. "
        "Segera konsultasikan kondisi ini dengan perawat atau dokter untuk pemeriksaan dan penanganan lebih lanjut. "
        "Hasil ini merupakan estimasi berdasarkan foto, bukan diagnosis medis."
    )
    c_comma = (
        "Ringkasan Pengukuran Longitudinal:\n"
        "- Baseline (A0): 12,60% · Saat Ini (At): 26,37%\n"
        "- Selisih (ΔA): +13,77 poin persentase · PAC: -109,29% · Status: Meningkat.\n"
        "Pemeriksaan klinis langsung tetap diperlukan karena hasil merupakan estimasi berdasarkan foto."
    )
    c_dot = (
        "Ringkasan Pengukuran Longitudinal:\n"
        "- Baseline (A0): 12.60% · Saat Ini (At): 26.37%\n"
        "- Selisih (ΔA): +13.77 poin persentase · PAC: -109.29% · Status: Meningkat.\n"
        "Pemeriksaan klinis langsung tetap diperlukan karena hasil merupakan estimasi berdasarkan foto."
    )
    c_wrong_comma = c_comma.replace("26,37%", "26,38%")
    c_wrong_dot = c_dot.replace("26.37%", "26.38%")

    ok_comma, reason_comma = validate_narrative_output(
        c_comma, p_narr, a0=a0, at=at, delta_a=delta_a, pac=pac, badge="meningkat", unit="%"
    )
    ok_dot, reason_dot = validate_narrative_output(
        c_dot, p_narr, a0=a0, at=at, delta_a=delta_a, pac=pac, badge="meningkat", unit="%"
    )
    ok_bad_comma, reason_bad_comma = validate_narrative_output(
        c_wrong_comma, p_narr, a0=a0, at=at, delta_a=delta_a, pac=pac, badge="meningkat", unit="%"
    )
    ok_bad_dot, reason_bad_dot = validate_narrative_output(
        c_wrong_dot, p_narr, a0=a0, at=at, delta_a=delta_a, pac=pac, badge="meningkat", unit="%"
    )

    assert ok_comma is True, reason_comma
    assert ok_dot is True, reason_dot
    assert ok_bad_comma is False and "angka_asing" in reason_bad_comma
    assert ok_bad_dot is False and "angka_asing" in reason_bad_dot


async def test_c5_01_forced_failure_fallback_saves_visit_as_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """C5: Saat Gemini gagal/timeout, confirm tetap mengembalikan 200 status=final dengan template_fallback."""
    import logging
    import httpx
    from sqlalchemy import delete
    from app.models.patient import Patient, Visit
    from app.services import narrative as narrative_module
    from app.services.segmentation import SegmentationFn, get_segmentation_service
    from app.services.storage import generate_stub_binary_mask_png

    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "gemini_api_key", "fake-c5-timeout-key")

    def _set_seg(n_px: int) -> None:
        def _seg(_image_bytes: bytes) -> tuple[int, bytes]:
            return n_px, generate_stub_binary_mask_png(n_px)

        def _get_seg() -> SegmentationFn:
            return _seg

        app.dependency_overrides[get_segmentation_service] = _get_seg

    async def _always_timeout(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise httpx.TimeoutException("Simulasi timeout Gemini C5")

    monkeypatch.setattr(narrative_module, "request_gemini_api", _always_timeout)

    test_engine = create_async_engine(settings.resolved_test_database_url, future=True)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with TestSessionLocal() as session:
            await session.execute(delete(Visit))
            await session.execute(delete(Patient))
            await session.commit()

        png_bytes = _make_solid_png_bytes(180, 90, 80, size=64)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r_pat = await ac.post(
                "/api/v1/patients",
                json={
                    "id": "Patient_C5",
                    "nama": "Uji Kegagalan C5",
                    "umur": 48,
                    "jk": "Perempuan",
                    "lokasi": "Telapak kaki kiri",
                    "consent": True,
                    "is_demo": False,
                },
            )
            assert r_pat.status_code == 201

            _set_seg(3277)
            d1 = await ac.post(
                "/api/v1/patients/Patient_C5/visits",
                data={"visit_date": "2026-10-01", "distance_confirmed": "true"},
                files={"file": ("c5_t1.png", png_bytes, "image/png")},
            )
            assert d1.status_code == 201
            c1 = await ac.post(f"/api/v1/visits/{d1.json()['id']}/confirm")
            assert c1.status_code == 200
            assert c1.json()["status"] == "final"

            _set_seg(2294)
            d2 = await ac.post(
                "/api/v1/patients/Patient_C5/visits",
                data={"visit_date": "2026-10-15", "distance_confirmed": "true"},
                files={"file": ("c5_t2.png", png_bytes, "image/png")},
            )
            assert d2.status_code == 201
            v2_id = d2.json()["id"]

            caplog.clear()
            with caplog.at_level(logging.WARNING, logger="app.services.narrative"):
                c2 = await ac.post(f"/api/v1/visits/{v2_id}/confirm")

            assert c2.status_code == 200
            body2 = c2.json()
            assert body2["status"] == "final"
            assert body2["narrative_source"] == "template_fallback"
            assert "5,00%" in body2["clinician_notes"]
            assert "3,50%" in body2["clinician_notes"]
            assert "30,00%" in body2["patient_narrative"]

            persisted = await ac.get(f"/api/v1/visits/{v2_id}")
            assert persisted.status_code == 200
            p_body = persisted.json()
            assert p_body["status"] == "final"
            assert p_body["narrative_source"] == "template_fallback"
            assert p_body["clinician_notes"] == body2["clinician_notes"]

            warnings = [rec.getMessage() for rec in caplog.records if "fallback" in rec.getMessage().lower()]
            assert warnings, "Log peringatan fallback wajib tercatat saat Gemini timeout"
            print(f"[C5-FORCED-FALLBACK] status={body2['status']} source={body2['narrative_source']} log={warnings[-1]}")
    finally:
        app.dependency_overrides.clear()
        async with TestSessionLocal() as session:
            await session.execute(delete(Visit))
            await session.execute(delete(Patient))
            await session.commit()
        await test_engine.dispose()


@pytest.mark.skipif(
    os.getenv("RUN_REAL_GEMINI") != "1" or not settings.gemini_api_key.strip(),
    reason="Hanya dijalankan saat RUN_REAL_GEMINI=1 dan GEMINI_API_KEY tersedia",
)
async def test_c5_02_real_gemini_six_combinations_matrix(caplog: pytest.LogCaptureFixture) -> None:
    """C5 (manual): Matriks 6 kombinasi Gemini asli ({menurun, stabil, meningkat} x {%, cm²})."""
    import logging
    from app.services import narrative as narrative_module

    combos = [
        ("menurun", "Tren Menurun (Area Luka Mengecil)", 12.60, 8.82, -3.78, 30.00),
        ("stabil", "Tren Stabil (Perubahan Minimal)", 12.60, 12.35, -0.25, 1.98),
        ("meningkat", "Tren Meningkat (Area Luka Membesar)", 12.60, 26.37, 13.77, -109.29),
    ]

    for unit in ("%", "cm²"):
        for badge, trend_status, a0, at, delta_a, pac in combos:
            caplog.clear()
            with caplog.at_level(logging.WARNING, logger="app.services.narrative"):
                c_notes, p_narr, source = await narrative_module.generate_longitudinal_narrative(
                    a0=a0,
                    at=at,
                    delta_a=delta_a,
                    pac=pac,
                    badge=badge,  # type: ignore[arg-type]
                    trend_status=trend_status,
                    unit=unit,  # type: ignore[arg-type]
                )
            warn_msgs = [rec.getMessage() for rec in caplog.records]
            reason = " | ".join(warn_msgs) if warn_msgs else "-"
            print(f"[C5-COMBO] badge={badge} unit={unit} source={source} reason={reason}")
            print(f"[C5-CLINICIAN] {c_notes}")
            print(f"[C5-PATIENT] {p_narr}")
            assert source in {"llm", "template_fallback"}
            ok, val_reason = narrative_module.validate_narrative_output(
                c_notes,
                p_narr,
                a0=a0,
                at=at,
                delta_a=delta_a,
                pac=pac,
                badge=badge,  # type: ignore[arg-type]
                unit=unit,  # type: ignore[arg-type]
            )
            assert ok is True, f"{badge} {unit}: {val_reason}"


async def test_3d_01_trend_direction_specific_subreasons_and_warning_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """3d-1: Sub-alasan _matches_trend_direction dilaporkan spesifik dan dicatat di log WARNING."""
    import json
    import logging
    from app.services import narrative as narrative_module

    # Baseline valid text templates for each trend
    c_inc, p_inc, _ = narrative_module.generate_fallback_narrative(
        a0=12.60, at=26.37, delta_a=13.77, pac=-109.29, badge="meningkat", unit="%"
    )
    c_dec, p_dec, _ = narrative_module.generate_fallback_narrative(
        a0=12.60, at=8.82, delta_a=-3.78, pac=30.00, badge="menurun", unit="%"
    )
    c_stb, p_stb, _ = narrative_module.generate_fallback_narrative(
        a0=12.60, at=12.35, delta_a=-0.25, pac=1.98, badge="stabil", unit="%"
    )

    checks = [
        # 1. pac_negatif_di_narasi_pasien
        (
            c_inc,
            p_inc.replace("109,29%", "-109,29%"),
            12.60, 26.37, 13.77, -109.29, "meningkat",
            "arah_tren_atau_format_pac_tidak_sesuai:pac_negatif_di_narasi_pasien",
        ),
        # 2. pac_klinisi_tanpa_tanda_plus
        (
            c_dec.replace("PAC: +30,00%", "PAC: 30,00%"),
            p_dec,
            12.60, 8.82, -3.78, 30.00, "menurun",
            "arah_tren_atau_format_pac_tidak_sesuai:pac_klinisi_tanpa_tanda_plus",
        ),
        # 3. pac_klinisi_tanpa_tanda_minus
        (
            c_inc.replace("PAC: -109,29%", "PAC: 109,29%"),
            p_inc,
            12.60, 26.37, 13.77, -109.29, "meningkat",
            "arah_tren_atau_format_pac_tidak_sesuai:pac_klinisi_tanpa_tanda_minus",
        ),
        # 4. kata_kunci_meningkat_hilang
        (
            c_inc.replace("meningkat", "berubah").replace("perluasan", "perubahan"),
            p_inc.replace("lebih besar", "berbeda").replace("bertambah", "berubah"),
            12.60, 26.37, 13.77, -109.29, "meningkat",
            "arah_tren_atau_format_pac_tidak_sesuai:kata_kunci_meningkat_hilang",
        ),
        # 5. kata_berlawanan_pada_meningkat:penurunan
        (
            c_inc.replace("perluasan luas", "bukan penurunan luas"),
            p_inc,
            12.60, 26.37, 13.77, -109.29, "meningkat",
            "arah_tren_atau_format_pac_tidak_sesuai:kata_berlawanan_pada_meningkat:penurunan",
        ),
        # 6. kata_kunci_menurun_hilang
        (
            c_dec.replace("menurun", "berubah").replace("penurunan", "perubahan"),
            p_dec.replace("lebih kecil", "berbeda").replace("berkurang", "berubah"),
            12.60, 8.82, -3.78, 30.00, "menurun",
            "arah_tren_atau_format_pac_tidak_sesuai:kata_kunci_menurun_hilang",
        ),
        # 7. kata_berlawanan_pada_menurun:membesar
        (
            c_dec,
            p_dec.replace("lebih kecil", "tidak membesar, melainkan lebih kecil"),
            12.60, 8.82, -3.78, 30.00, "menurun",
            "arah_tren_atau_format_pac_tidak_sesuai:kata_berlawanan_pada_menurun:membesar",
        ),
        # 8. kata_kunci_stabil_hilang
        (
            c_stb.replace("Tidak terdeteksi perubahan", "Diamati selisih").replace("relatif stabil", "datar"),
            p_stb.replace("relatif tidak berubah", "diamati"),
            12.60, 12.35, -0.25, 1.98, "stabil",
            "arah_tren_atau_format_pac_tidak_sesuai:kata_kunci_stabil_hilang",
        ),
        # 9. kata_berlawanan_pada_stabil:area luka terukur meningkat
        (
            c_stb.replace("Tidak terdeteksi perubahan berarti", "Area luka terukur meningkat sedikit namun relatif stabil"),
            p_stb,
            12.60, 12.35, -0.25, 1.98, "stabil",
            "arah_tren_atau_format_pac_tidak_sesuai:kata_berlawanan_pada_stabil:area luka terukur meningkat",
        ),
    ]

    for c_notes, p_narr, a0, at, da, pac, badge, expected_reason in checks:
        ok, reason = narrative_module.validate_narrative_output(
            c_notes,
            p_narr,
            a0=a0,
            at=at,
            delta_a=da,
            pac=pac,
            badge=badge,  # type: ignore[arg-type]
            unit="%",
        )
        assert ok is False
        assert reason == expected_reason

    # Verifikasi log level WARNING memuat sub-alasan spesifik saat generate_longitudinal_narrative menolak
    monkeypatch.setattr(settings, "gemini_api_key", "fake-3d1-key")

    async def _mock_opposite_word(**_kwargs: object) -> dict[str, object]:
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "clinician_notes": c_inc.replace("perluasan luas", "bukan penurunan luas"),
                                        "patient_narrative": p_inc,
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(narrative_module, "request_gemini_api", _mock_opposite_word)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="app.services.narrative"):
        _, _, src = await narrative_module.generate_longitudinal_narrative(
            a0=12.60,
            at=26.37,
            delta_a=13.77,
            pac=-109.29,
            badge="meningkat",
            trend_status="Tren Meningkat (Area Luka Membesar)",
            unit="%",
        )
    assert src == "template_fallback"
    assert any(
        rec.levelno == logging.WARNING
        and "reason=validator_rejected:arah_tren_atau_format_pac_tidak_sesuai:kata_berlawanan_pada_meningkat:penurunan"
        in rec.message
        for rec in caplog.records
    )
