import math
from dataclasses import dataclass

from app.services.pac import TOTAL_MASK_PIXELS

MIN_RULER_LENGTH_CM: float = 0.0
MAX_RULER_LENGTH_CM: float = 50.0
MIN_DIAGONAL_RATIO: float = 0.02


class CalibrationValidationError(ValueError):
    """Raised when ruler two-point calibration inputs violate domain constraints."""


@dataclass(frozen=True)
class CalibrationResult:
    delta_px: float
    scale_cm_per_px: float
    area_cm2: float


def compute_and_validate_calibration(
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    length_cm: float,
    width_px: int,
    height_px: int,
    n_wound_px: int,
) -> CalibrationResult:
    """Validate two-point ruler coordinates in original image space (W x H) and compute cm² area.

    Coordinate space rationale:
    The segmentation model resizes original W x H images to 256 x 256 (65,536 px).
    When W != H, a 256 x 256 resize stretches X and Y anisotropically, making Euclidean
    pixel distance on 256 x 256 dependent on ruler angle. Therefore, calibration points
    (x1, y1) and (x2, y2) are defined in the post-EXIF original image coordinate space
    [0, W] x [0, H] where sensor pixels are square (1:1).
    Each 256 x 256 mask pixel maps to (W * H / 65536) original image pixels:
        A_cm2 = (n_wound_px / 65536) * W * H * s^2
    When W = 256 and H = 256, this simplifies directly to n_wound_px * s^2.
    """
    if width_px <= 0 or height_px <= 0:
        raise CalibrationValidationError("Dimensi citra asli tidak valid untuk kalibrasi.")

    for val in (x1, y1, x2, y2, length_cm):
        if not math.isfinite(val):
            raise CalibrationValidationError("Input kalibrasi harus berupa angka hingga (finite).")

    if length_cm <= MIN_RULER_LENGTH_CM or length_cm > MAX_RULER_LENGTH_CM:
        raise CalibrationValidationError(
            f"Panjang penggaris nyata (length_cm) harus berada pada rentang (0, {MAX_RULER_LENGTH_CM:g}] cm."
        )

    if not (0.0 <= x1 <= float(width_px) and 0.0 <= x2 <= float(width_px)):
        raise CalibrationValidationError(
            f"Koordinat X titik kalibrasi harus berada di dalam batas lebar citra [0, {width_px}]."
        )
    if not (0.0 <= y1 <= float(height_px) and 0.0 <= y2 <= float(height_px)):
        raise CalibrationValidationError(
            f"Koordinat Y titik kalibrasi harus berada di dalam batas tinggi citra [0, {height_px}]."
        )

    dx = x2 - x1
    dy = y2 - y1
    delta_px = math.hypot(dx, dy)
    if delta_px == 0.0:
        raise CalibrationValidationError("Dua titik penggaris tidak boleh berimpit (identik).")

    diagonal_px = math.hypot(float(width_px), float(height_px))
    min_delta_px = MIN_DIAGONAL_RATIO * diagonal_px
    if delta_px < min_delta_px:
        raise CalibrationValidationError(
            f"Jarak piksel antar titik penggaris terlalu dekat ({delta_px:.2f} px < minimal 2% diagonal {min_delta_px:.2f} px)."
        )

    scale_cm_per_px = length_cm / delta_px
    equiv_orig_wound_px = (float(max(0, n_wound_px)) / float(TOTAL_MASK_PIXELS)) * float(
        width_px * height_px
    )
    raw_area_cm2 = equiv_orig_wound_px * (scale_cm_per_px**2)

    return CalibrationResult(
        delta_px=round(delta_px, 4),
        scale_cm_per_px=round(scale_cm_per_px, 6),
        area_cm2=round(raw_area_cm2, 2),
    )
