from collections.abc import Callable
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
IMAGE_SIZE = (256, 256)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)

SegmentationFn = Callable[[bytes], tuple[int, bytes]]

_MODEL: ResNet34UNet | None = None
_MODEL_DEVICE = torch.device("cpu")
_LAST_INFERENCE_MS: float | None = None


def resolve_checkpoint_path(custom_path: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if custom_path is not None:
        candidates.append(Path(custom_path))
    cfg_path = Path(settings.model_checkpoint_path)
    candidates.extend(
        [
            cfg_path,
            Path("/app/checkpoints") / cfg_path.name,
            Path("/app/ml/checkpoints") / cfg_path.name,
            Path("ml/checkpoints") / cfg_path.name,
            Path("../ml/checkpoints") / cfg_path.name,
        ]
    )
    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    return cfg_path


def load_segmentation_model(checkpoint_path: str | Path | None = None) -> ResNet34UNet | None:
    """
    Loads ResNet34UNet once at startup with strict=True and model.eval(),
    and verifies total_parameters == 24,860,105 (Bab 3.6).
    """
    global _MODEL
    ckpt_path = resolve_checkpoint_path(checkpoint_path)
    if not ckpt_path.is_file():
        logger.warning(
            "Checkpoint model tidak ditemukan di %s. Inferensi model asli tidak aktif.",
            ckpt_path,
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
) -> torch.Tensor:
    """
    Prapemrosesan citra sesuai Bab 3.5 PRD:
    1. ImageOps.exif_transpose (orientasi foto ponsel) + konversi ke RGB
    2. Resize 256x256 dengan interpolasi bilinear
    3. Normalisasi [0, 1] (x / 255.0) untuk 'zero_one' atau mean/std untuk 'imagenet'
    4. Konversi ke tensor float32 berbentuk (1, 3, 256, 256)
    """
    norm_mode = (normalization or settings.model_normalization).lower()
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        oriented = ImageOps.exif_transpose(raw_img)
        rgb_img = oriented.convert("RGB")
        resized = rgb_img.resize(IMAGE_SIZE, resample=Image.Resampling.BILINEAR)

    img_np = np.array(resized, dtype=np.float32) / 255.0
    if norm_mode == "imagenet":
        img_np = (img_np - IMAGENET_MEAN) / IMAGENET_STD
    elif norm_mode != "zero_one":
        raise ValueError(f"Mode normalisasi tidak dikenal: {norm_mode}")

    tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0).contiguous()
    return tensor


def run_model_segmentation(image_bytes: bytes) -> tuple[int, bytes]:
    """
    Menjalankan inferensi U-Net ResNet-34 pada CPU dengan model.eval() dan torch.no_grad().
    Mengembalikan tuple (n_wound_px, mask_png_bytes) dan mencatat waktu inferensi (ms).
    """
    global _MODEL, _LAST_INFERENCE_MS
    if _MODEL is None:
        load_segmentation_model()
    if _MODEL is None:
        raise RuntimeError("Model segmentasi belum dimuat (checkpoint tidak ditemukan).")

    t0 = time.perf_counter()
    input_tensor = preprocess_image_bytes(image_bytes)
    with torch.no_grad():
        logits = _MODEL(input_tensor.to(_MODEL_DEVICE))
        probs = torch.sigmoid(logits)
        pred_bin = (probs > 0.5).squeeze(0).squeeze(0).cpu().numpy().astype(np.uint8)

    n_wound_px = int(np.count_nonzero(pred_bin))
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
        (n_wound_px / 65536.0) * 100.0,
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
