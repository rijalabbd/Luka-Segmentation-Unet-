import csv
import io
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import torch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
if (ROOT_DIR / "backend").is_dir():
    sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.services.segmentation import (  # noqa: E402
    EXPECTED_RESNET34_UNET_PARAMS,
    get_last_inference_ms,
    load_segmentation_model,
    run_model_segmentation,
)


def calculate_binary_dice(pred_bin: np.ndarray, gt_bin: np.ndarray, smooth: float = 1e-5) -> float:
    pred_f = pred_bin.reshape(-1).astype(np.float64)
    gt_f = gt_bin.reshape(-1).astype(np.float64)
    tp = float((pred_f * gt_f).sum())
    fp = float((pred_f * (1.0 - gt_f)).sum())
    fn = float(((1.0 - pred_f) * gt_f).sum())
    return (2.0 * tp + smooth) / (2.0 * tp + fp + fn + smooth)


def main() -> int:
    ckpt_path = ROOT_DIR / "ml" / "checkpoints" / "best_resnet34_unet_01norm.pth"
    ref_csv_path = ROOT_DIR / "ml" / "reference_metrics.csv"

    model = load_segmentation_model(ckpt_path)
    if model is None:
        print(f"ERROR: Checkpoint not found at {ckpt_path}")
        return 1

    param_info = model.count_parameters()
    print(f"Loaded Model Parameters: {param_info['total_parameters']:,} (expected: {EXPECTED_RESNET34_UNET_PARAMS:,})")
    assert param_info["total_parameters"] == EXPECTED_RESNET34_UNET_PARAMS

    rows_out = []
    ref_dices = []
    backend_dices = []
    latencies = []

    with open(ref_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img_path = ROOT_DIR / row["image_path"]
            msk_path = ROOT_DIR / row["mask_path"]

            image_bytes = img_path.read_bytes()
            n_wound_px, mask_png_bytes = run_model_segmentation(image_bytes)
            inf_ms = get_last_inference_ms() or 0.0
            latencies.append(inf_ms)

            with Image.open(io.BytesIO(mask_png_bytes)) as pred_img:
                pred_bin = (np.asarray(pred_img.convert("L"), dtype=np.uint8) > 127).astype(np.uint8)

            with Image.open(msk_path) as gt_img:
                gt_resized = gt_img.convert("L").resize((256, 256), resample=Image.Resampling.NEAREST)
                gt_bin = (np.asarray(gt_resized, dtype=np.uint8) > 127).astype(np.uint8)

            backend_dice = calculate_binary_dice(pred_bin, gt_bin)
            ref_dice = float(row["dice"])
            ref_px = int(row["pred_wound_pixels"])
            ref_area_pct = float(row["pred_area_pct"])
            backend_area_pct = (n_wound_px / 65536.0) * 100.0

            ref_dices.append(ref_dice)
            backend_dices.append(backend_dice)

            rows_out.append(
                {
                    "image_id": row["image_id"],
                    "patient": row["patient_id"],
                    "time_point": row["time_point"],
                    "ref_px": ref_px,
                    "backend_px": n_wound_px,
                    "dice_ref": ref_dice,
                    "dice_backend": backend_dice,
                    "area_ref_pct": ref_area_pct,
                    "area_backend_pct": backend_area_pct,
                    "abs_diff": abs(backend_dice - ref_dice),
                    "latency_ms": inf_ms,
                }
            )

    print(
        f"{'No':>2} | {'image_id':<8} | {'patient':<10} | {'dice_ref':>8} | {'dice_backend':>12} | "
        f"{'area_ref_pct':>12} | {'area_backend_pct':>16} | {'|Δ Dice|':>8} | {'CPU ms':>7}"
    )
    print("-" * 108)
    for idx, r in enumerate(rows_out, start=1):
        print(
            f"{idx:>2} | {r['image_id']:<8} | {r['patient']:<10} | {r['dice_ref']:>8.6f} | {r['dice_backend']:>12.6f} | "
            f"{r['area_ref_pct']:>11.4f}% | {r['area_backend_pct']:>15.4f}% | {r['abs_diff']:>8.6f} | {r['latency_ms']:>6.1f}"
        )
    print("-" * 108)
    mean_ref = float(np.mean(ref_dices))
    mean_back = float(np.mean(backend_dices))
    mean_diff = abs(mean_back - mean_ref)
    mean_lat = float(np.mean(latencies))
    print(f"Mean Reference Dice : {mean_ref:.6f}")
    print(f"Mean Backend Dice   : {mean_back:.6f}")
    print(f"Absolute Difference : {mean_diff:.6f} (Threshold < 0.005)")
    print(f"Mean CPU Latency    : {mean_lat:.2f} ms")
    assert mean_diff < 0.005, f"Mean Dice difference {mean_diff} >= 0.005!"

    for target_dir in (ROOT_DIR / "ml", Path("/tmp")):
        try:
            csv_file = target_dir / "bab4_dice_per_image.csv"
            md_file = target_dir / "bab4_dice_per_image.md"
            with open(csv_file, "w", encoding="utf-8", newline="") as f_csv:
                writer = csv.DictWriter(
                    f_csv,
                    fieldnames=[
                        "image_id",
                        "patient",
                        "dice_ref",
                        "dice_backend",
                        "area_ref_pct",
                        "area_backend_pct",
                    ],
                )
                writer.writeheader()
                for r in rows_out:
                    writer.writerow(
                        {
                            "image_id": r["image_id"],
                            "patient": r["patient"],
                            "dice_ref": f"{r['dice_ref']:.6f}",
                            "dice_backend": f"{r['dice_backend']:.6f}",
                            "area_ref_pct": f"{r['area_ref_pct']:.4f}",
                            "area_backend_pct": f"{r['area_backend_pct']:.4f}",
                        }
                    )

            md_lines = [
                "# Acuan Bab 4: Evaluasi Dice Similarity Coefficient (DSC) terhadap Ground Truth per Citra (23 Citra Uji LUTSeg)",
                "",
                f"- **Model**: `ResNet34UNet` (`{param_info['total_parameters']:,}` parameter, normalisasi `[0, 1]` via `x / 255.0`, ambang sigmoid `0.5`)",
                f"- **Rata-rata `dice_ref` (terhadap Ground Truth di `ml/reference_metrics.csv`)**: `{mean_ref:.6f}`",
                f"- **Rata-rata `dice_backend` (terhadap Ground Truth lewat pipeline backend)**: `{mean_back:.6f}`",
                f"- **Selisih Absolut (`|Δ Mean Dice|`)**: `{mean_diff:.6f}` (Ambang batas `< 0.005`)",
                f"- **Rata-rata Waktu Inferensi CPU**: `{mean_lat:.2f} ms`",
                "",
                "| image_id | patient | dice_ref | dice_backend | area_ref_pct | area_backend_pct |",
                "|:---------|:--------|---------:|-------------:|-------------:|-----------------:|",
            ]
            for r in rows_out:
                md_lines.append(
                    f"| `{r['image_id']}` | `{r['patient']}` | {r['dice_ref']:.6f} | "
                    f"{r['dice_backend']:.6f} | {r['area_ref_pct']:.4f} | {r['area_backend_pct']:.4f} |"
                )
            md_file.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
            print(f"Saved Bab 4 per-image Dice tables to {csv_file} and {md_file}")
            break
        except OSError:
            continue

    # Single-image manual mask verification (P10T_2.jpg)
    sample_img = ROOT_DIR / "ml" / "test_set" / "Images" / "Patient_10" / "P10T_2.jpg"
    n_px, mask_bytes = run_model_segmentation(sample_img.read_bytes())
    api_area_pct = round((n_px / 65536.0) * 100.0, 2)
    with Image.open(io.BytesIO(mask_bytes)) as m_img:
        w, h = m_img.size
        total_px = w * h
        raw_vals = list(m_img.tobytes())
        count_255 = raw_vals.count(255)
        count_0 = raw_vals.count(0)
    manual_unrounded = (count_255 / total_px) * 100.0
    manual_rounded = round(manual_unrounded, 2)
    print("\n=== MANUAL MASK CALCULATION vs API (P10T_2.jpg) ===")
    print(f"Mask Dimensions      : {w} x {h} = {total_px} total pixels (mode=L)")
    print(f"Pixels == 255 (Luka) : {count_255}")
    print(f"Pixels == 0 (Latar)  : {count_0}")
    print(f"Check 255 + 0        : {count_255 + count_0} == {total_px}")
    print(f"Manual Formula A_t   : ({count_255} / {total_px}) * 100% = {manual_unrounded:.6f}% -> {manual_rounded:.2f}%")
    print(f"API Returned A_t     : {api_area_pct:.2f}% (n_wound_px = {n_px})")
    assert count_255 == n_px
    assert manual_rounded == api_area_pct
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

