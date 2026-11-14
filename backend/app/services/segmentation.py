from collections.abc import Callable
import hashlib
import io
import logging
from pathlib import Path
import time
from typing import Annotated

from fastapi import Depends
import numpy as np
from PIL import Image, ImageOps
import torch

from app.core.config import settings
from app.services.storage import DEFAULT_STUB_WOUND_PX, generate_stub_binary_mask_png
from app.services.unet_model import ResNet34UNet

logger = logging.getLogger(__name__)

EXPECTED_RESNET34_UNET_PARAMS = 24_860_105
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)

SegmentationFn = Callable[[bytes], tuple[int, bytes]]

_MODEL: ResNet34UNet | None = None
_MODEL_DEVICE = torch.device("cpu")
_LAST_INFERENCE_MS: float | None = None
_HASH_CACHE: tuple[str, int, int, str] | None = None


def resolve_checkpoint_path(custom_path: str | Path | None = None) -> Path:
    if custom_path is not None:
        explicit = Path(custom_path)
        return explicit.resolve() if explicit.is_file() else explicit

    cfg_path = Path(settings.model_checkpoint_path)
    candidates = [
        cfg_path,
        Path("/app/checkpoints") / cfg_path.name,
        Path("/app/ml/checkpoints") / cfg_path.name,
        Path("ml/checkpoints") / cfg_path.name,
        Path("../ml/checkpoints") / cfg_path.name,
    ]
    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    return cfg_path


def get_checkpoint_sha256_short(checkpoint_path: str | Path | None = None) -> str | None:
    global _HASH_CACHE
    ckpt_path = resolve_checkpoint_path(checkpoint_path)
    if not ckpt_path.is_file():
        return None
    stat = ckpt_path.stat()
    key_path = str(ckpt_path)
    if (
        _HASH_CACHE is not None
        and _HASH_CACHE[0] == key_path
        and _HASH_CACHE[1] == stat.st_mtime_ns
        and _HASH_CACHE[2] == stat.st_size
    ):
        return _HASH_CACHE[3]

    digest = hashlib.sha256()
    with ckpt_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    short_hash = digest.hexdigest()[:12]
    _HASH_CACHE = (key_path, stat.st_mtime_ns, stat.st_size, short_hash)
    return short_hash


def get_model_identity() -> dict[str, object]:
    cfg_name = Path(settings.model_checkpoint_path).name
    ckpt_path = resolve_checkpoint_path()
    ckpt_exists = ckpt_path.is_file()
    return {
        "checkpoint_name": cfg_name,
        "checkpoint_sha256_short": get_checkpoint_sha256_short() if ckpt_exists else None,
        "loaded": bool(_MODEL is not None and ckpt_exists),
        "normalization": settings.model_normalization,
        "input_size": settings.model_input_size,
        "binary_threshold": settings.model_binary_threshold,
    }


def load_segmentation_model(
    checkpoint_path: str | Path | None = None,
    *,
    require_exists: bool = False,
) -> ResNet34UNet | None:
    """
    Loads ResNet34UNet once at startup with strict=True and model.eval(),
    and verifies total_parameters == 24,860,105 (Bab 3.6).
    """
    global _MODEL
    ckpt_path = resolve_checkpoint_path(checkpoint_path)
    if not ckpt_path.is_file():
        _MODEL = None
        if require_exists:
            raise FileNotFoundError(
                f"Berkas checkpoint model tidak ditemukan: '{ckpt_path.name}'. "
                "Periksa konfigurasi MODEL_CHECKPOINT_PATH."
            )
        logger.warning(
            "Checkpoint model tidak ditemukan (%s). Inferensi model asli tidak aktif.",
            ckpt_path.name,
        )
        return None

    t0 = time.perf_counter()
    model = ResNet34UNet(in_channels=3, out_channels=1, pretrained=False)
    param_info = model.count_parameters()
    total_params = param_info["total_parameters"]
    if total_params != EXPECTED_RESNET34_UNET_PARAMS:
        raise RuntimeError(
            f"Jumlah parameter model ({total_params}) tidak sesuai dengan Bab 3.6 ({EXPECTED_RESNET34_UNET_PARAMS})."
        )

    ckpt = torch.load(ckpt_path, map_location=_MODEL_DEVICE, weights_only=False)
    state_dict = (
        ckpt["model_state_dict"]
        if isinstance(ckpt, dict) and "model_state_dict" in ckpt
        else ckpt
    )
    model.load_state_dict(state_dict, strict=True)
    model.to(_MODEL_DEVICE)
    model.eval()

    load_ms = (time.perf_counter() - t0) * 1000.0
    logger.info(
        "Model ResNet34UNet berhasil dimuat dari %s dalam %.1f ms | total_parameters=%d (terverifikasi == %d)",
        ckpt_path,
        load_ms,
        total_params,
        EXPECTED_RESNET34_UNET_PARAMS,
    )
    _MODEL = model
    return _MODEL


def get_loaded_model() -> ResNet34UNet | None:
    return _MODEL


def get_last_inference_ms() -> float | None:
    return _LAST_INFERENCE_MS


def preprocess_image_bytes(
    image_bytes: bytes,
    normalization: str | None = None,
    input_size: int | None = None,
) -> torch.Tensor:
    """
    Prapemrosesan citra sesuai Bab 3.5 PRD:
    1. ImageOps.exif_transpose (orientasi foto ponsel) + konversi ke RGB
    2. Resize (input_size x input_size, bawaan 256x256) dengan interpolasi bilinear
    3. Normalisasi [0, 1] (x / 255.0) untuk 'zero_one' atau mean/std untuk 'imagenet'
    4. Konversi ke tensor float32 berbentuk (1, 3, H, W)
    """
    norm_mode = (normalization or settings.model_normalization).strip().lower()
    size = int(input_size if input_size is not None else settings.model_input_size)
    if norm_mode not in {"zero_one", "imagenet"}:
        raise ValueError(
            f"Mode normalisasi tidak dikenal: '{norm_mode}'. Gunakan 'zero_one' atau 'imagenet'."
        )
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        oriented = ImageOps.exif_transpose(raw_img)
        rgb_img = oriented.convert("RGB")
        resized = rgb_img.resize((size, size), resample=Image.Resampling.BILINEAR)

    img_np = np.array(resized, dtype=np.float32) / 255.0
    if norm_mode == "imagenet":
        img_np = (img_np - IMAGENET_MEAN) / IMAGENET_STD

    tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0).contiguous()
    return tensor


def run_model_segmentation(image_bytes: bytes) -> tuple[int, bytes]:
    """
    Menjalankan inferensi U-Net ResNet-34 pada CPU dengan model.eval() dan torch.no_grad().
    Mengembalikan tuple (n_wound_px, mask_png_bytes) dan mencatat waktu inferensi (ms).
    """
    global _MODEL, _LAST_INFERENCE_MS
    if _MODEL is None:
        load_segmentation_model(require_exists=True)
    if _MODEL is None:
        raise FileNotFoundError(
            "Model segmentasi belum dimuat (berkas checkpoint tidak ditemukan)."
        )

    t0 = time.perf_counter()
    input_tensor = preprocess_image_bytes(image_bytes)
    threshold = settings.model_binary_threshold
    with torch.no_grad():
        logits = _MODEL(input_tensor.to(_MODEL_DEVICE))
        probs = torch.sigmoid(logits)
        pred_bin = (probs > threshold).squeeze(0).squeeze(0).cpu().numpy().astype(np.uint8)

    n_wound_px = int(np.count_nonzero(pred_bin))
    total_px = float(pred_bin.size) or 65536.0
    mask_uint8 = (pred_bin * 255).astype(np.uint8)
    mask_img = Image.fromarray(mask_uint8, mode="L")
    buf = io.BytesIO()
    mask_img.save(buf, format="PNG")
    mask_bytes = buf.getvalue()

    latency_ms = (time.perf_counter() - t0) * 1000.0
    _LAST_INFERENCE_MS = latency_ms
    logger.info(
        "Inferensi segmentasi selesai dalam %.2f ms | n_wound_px=%d | area_pct=%.2f%%",
        latency_ms,
        n_wound_px,
        (n_wound_px / total_px) * 100.0,
    )
    return n_wound_px, mask_bytes


def run_stub_segmentation(_image_bytes: bytes) -> tuple[int, bytes]:
    """
    Stub segmentasi untuk pengujian cepat / fallback tanpa checkpoint.
    """
    n_px = DEFAULT_STUB_WOUND_PX
    return n_px, generate_stub_binary_mask_png(n_px)


def get_segmentation_service() -> SegmentationFn:
    if _MODEL is not None or resolve_checkpoint_path().is_file():
        return run_model_segmentation
    return run_stub_segmentation


SegmentationDep = Annotated[SegmentationFn, Depends(get_segmentation_service)]
