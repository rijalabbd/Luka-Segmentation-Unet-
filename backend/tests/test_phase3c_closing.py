from collections.abc import AsyncGenerator
import io
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
