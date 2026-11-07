import io
from pathlib import Path
import uuid

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.models.visit import derive_overlay_rel_path
from app.services.pac import CANVAS_TOTAL_PX

DEFAULT_STUB_WOUND_PX = 3277  # 5.00% dari 65.536 piksel (contoh Bab 3.7)
ALLOWED_STORAGE_SUBDIRS = ("uploads", "masks", "overlays")


def get_storage_root() -> Path:
    root = Path(settings.storage_dir)
    for sub in ALLOWED_STORAGE_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def resolve_storage_path(rel_path: str) -> Path:
    if not rel_path or ".." in rel_path.replace("\\", "/").split("/"):
        raise ValueError("Path penyimpanan tidak valid.")
    root_resolved = get_storage_root().resolve()
    candidate = (root_resolved / rel_path).resolve()
    if not candidate.is_relative_to(root_resolved) or candidate == root_resolved:
        raise ValueError("Path berada di luar root penyimpanan.")
    return candidate


def validate_and_orient_image_bytes(image_bytes: bytes) -> tuple[Image.Image, bytes, str]:
    """
    Memvalidasi berkas JPG/PNG <= 10 MB, menerapkan orientasi EXIF (exif_transpose),
    mengonversi ke RGB, dan menghapus seluruh metadata EXIF/GPS/XMP dari berkas keluaran.
    """
    if not image_bytes:
        raise ValueError("Berkas foto luka tidak boleh kosong.")
    if len(image_bytes) > settings.max_upload_size_bytes:
        raise ValueError("Ukuran berkas melebihi batas maksimal 10 MB.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            fmt = (raw_img.format or "").upper()
            if fmt not in ("JPEG", "PNG"):
                raise ValueError("Berkas harus berupa gambar berformat JPG atau PNG yang valid.")
            transposed = ImageOps.exif_transpose(raw_img)
            rgb_raw = transposed.convert("RGB")
            clean_rgb = Image.frombytes("RGB", rgb_raw.size, rgb_raw.tobytes())
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("Berkas harus berupa gambar berformat JPG atau PNG yang valid.") from exc

    ext = ".jpg" if fmt == "JPEG" else ".png"
    out_buf = io.BytesIO()
    if fmt == "JPEG":
        clean_rgb.save(out_buf, format="JPEG", quality=95)
    else:
        clean_rgb.save(out_buf, format="PNG")

    return clean_rgb, out_buf.getvalue(), ext


def generate_stub_binary_mask_png(n_wound_px: int) -> bytes:
    """
    Membuat masker biner PNG 256x256 (mode 'L') dengan nilai piksel 0 atau 255,
    di mana tepat `n_wound_px` piksel bernilai 255 (area luka).
    """
    clamped = max(0, min(CANVAS_TOTAL_PX, int(n_wound_px)))
    raw_pixels = bytes([255]) * clamped + bytes([0]) * (CANVAS_TOTAL_PX - clamped)
    img = Image.frombytes("L", (256, 256), raw_pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_overlay_png(image_bytes: bytes, mask_bytes: bytes) -> bytes:
    """
    Membuat citra overlay 256x256 PNG dengan area masker berwarna hijau transparan
    (rgba(34, 197, 94, 0.40) + garis tepi #16A34A) di atas citra RGB 256x256.
    """
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        rgb_256 = (
            ImageOps.exif_transpose(raw_img)
            .convert("RGB")
            .resize((256, 256), resample=Image.Resampling.BILINEAR)
        )
    with Image.open(io.BytesIO(mask_bytes)) as mask_img:
        mask_l = mask_img.convert("L").resize((256, 256), resample=Image.Resampling.NEAREST)

    base_np = np.asarray(rgb_256, dtype=np.float32).copy()
    mask_bool = np.asarray(mask_l, dtype=np.uint8) > 127

    if np.any(mask_bool):
        green_fill = np.array([34.0, 197.0, 94.0], dtype=np.float32)
        alpha = 0.40
        base_np[mask_bool] = (1.0 - alpha) * base_np[mask_bool] + alpha * green_fill

        # 1px boundary contour (#16A34A = rgb(22, 163, 74))
        padded = np.pad(mask_bool, pad_width=1, mode="constant", constant_values=False)
        eroded = (
            padded[1:-1, 1:-1]
            & padded[:-2, 1:-1]
            & padded[2:, 1:-1]
            & padded[1:-1, :-2]
            & padded[1:-1, 2:]
        )
        border = mask_bool & (~eroded)
        base_np[border] = np.array([22.0, 163.0, 74.0], dtype=np.float32)

    overlay_img = Image.fromarray(np.clip(base_np, 0, 255).astype(np.uint8), mode="RGB")
    buf = io.BytesIO()
    overlay_img.save(buf, format="PNG")
    return buf.getvalue()


def save_visit_files(
    patient_id: str,
    image_bytes: bytes,
    original_filename: str | None,
    mask_bytes: bytes,
    overlay_bytes: bytes | None = None,
) -> tuple[str, str]:
    root = get_storage_root()
    safe_pid = patient_id.strip().upper().replace("/", "_").replace("\\", "_")
    ext = Path(original_filename or "image.png").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        ext = ".png"

    token = uuid.uuid4().hex[:12]
    image_rel = f"uploads/{safe_pid}_{token}{ext}"
    mask_rel = f"masks/{safe_pid}_{token}_mask.png"
    overlay_rel = f"overlays/{safe_pid}_{token}_overlay.png"

    if overlay_bytes is None:
        overlay_bytes = generate_overlay_png(image_bytes, mask_bytes)

    (root / image_rel).write_bytes(image_bytes)
    (root / mask_rel).write_bytes(mask_bytes)
    (root / overlay_rel).write_bytes(overlay_bytes)

    return image_rel, mask_rel


def delete_file_if_exists(rel_path: str | None) -> None:
    if not rel_path:
        return
    try:
        target = resolve_storage_path(rel_path)
    except ValueError:
        return
    if target.is_file():
        target.unlink()


def delete_visit_files(image_path: str | None, mask_path: str | None) -> None:
    delete_file_if_exists(image_path)
    delete_file_if_exists(mask_path)
    delete_file_if_exists(derive_overlay_rel_path(mask_path))
