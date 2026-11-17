export interface CropRect {
  sx: number;
  sy: number;
  sw: number;
  sh: number;
}

/**
 * Menghitung area potong (sx, sy, sw, sh) pada frame video agar sesuai
 * persis dengan area yang terlihat saat elemen <video> memakai object-fit: cover.
 */
export function computeCoverCropRect(
  videoWidth: number,
  videoHeight: number,
  stageWidth: number,
  stageHeight: number,
): CropRect {
  const vw = Math.max(1, Math.round(videoWidth));
  const vh = Math.max(1, Math.round(videoHeight));

  if (!Number.isFinite(stageWidth) || !Number.isFinite(stageHeight) || stageWidth <= 0 || stageHeight <= 0) {
    return { sx: 0, sy: 0, sw: vw, sh: vh };
  }

  const videoRatio = vw / vh;
  const stageRatio = stageWidth / stageHeight;

  if (Math.abs(videoRatio - stageRatio) < 1e-4) {
    return { sx: 0, sy: 0, sw: vw, sh: vh };
  }

  if (videoRatio > stageRatio) {
    const sw = Math.max(1, Math.min(vw, Math.round(vh * stageRatio)));
    const sx = Math.max(0, Math.round((vw - sw) / 2));
    return { sx, sy: 0, sw, sh: vh };
  }

  const sh = Math.max(1, Math.min(vh, Math.round(vw / stageRatio)));
  const sy = Math.max(0, Math.round((vh - sh) / 2));
  return { sx: 0, sy, sw: vw, sh };
}
