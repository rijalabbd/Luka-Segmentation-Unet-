export const TOTAL_MASK_PIXELS = 65536
export const MIN_RULER_LENGTH_CM = 0
export const MAX_RULER_LENGTH_CM = 50
export const MIN_DIAGONAL_RATIO = 0.02

export interface Point2D {
  x: number
  y: number
}

export interface ElementBoxRect {
  left: number
  top: number
  width: number
  height: number
}

export interface ContainedImageRect {
  offsetX: number
  offsetY: number
  renderedWidth: number
  renderedHeight: number
  scale: number
}

export interface DisplayClickConversionResult {
  ok: boolean
  reason: 'INVALID_DIMENSIONS' | 'OUTSIDE_IMAGE' | null
  point: Point2D | null
}

export interface DisplayPointResult {
  x: number
  y: number
  pctX: number
  pctY: number
}

export interface ClientCalibrationResult {
  ok: boolean
  error: string | null
  deltaPx: number | null
  minDeltaPx: number
  scaleCmPerPx: number | null
  areaCm2: number | null
}

/** Hitung kotak gambar yang dirender di dalam elemen object-fit: contain. */
export function getContainedImageRect(
  boxWidth: number,
  boxHeight: number,
  imgWidthPx: number,
  imgHeightPx: number,
): ContainedImageRect {
  if (
    !Number.isFinite(boxWidth) ||
    !Number.isFinite(boxHeight) ||
    !Number.isFinite(imgWidthPx) ||
    !Number.isFinite(imgHeightPx) ||
    boxWidth <= 0 ||
    boxHeight <= 0 ||
    imgWidthPx <= 0 ||
    imgHeightPx <= 0
  ) {
    return {
      offsetX: 0,
      offsetY: 0,
      renderedWidth: 0,
      renderedHeight: 0,
      scale: 0,
    }
  }

  const scale = Math.min(boxWidth / imgWidthPx, boxHeight / imgHeightPx)
  const renderedWidth = imgWidthPx * scale
  const renderedHeight = imgHeightPx * scale
  const offsetX = (boxWidth - renderedWidth) / 2
  const offsetY = (boxHeight - renderedHeight) / 2

  return {
    offsetX,
    offsetY,
    renderedWidth,
    renderedHeight,
    scale,
  }
}

function clamp(val: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, val))
}

/**
 * Ubah koordinat klik (clientX, clientY) pada elemen <img> (object-fit: contain)
 * menjadi koordinat piksel citra asli (imgWidthPx x imgHeightPx).
 * Klik pada bidang kosong (letterbox/pillarbox) atau di luar elemen ditolak.
 */
export function displayClickToOriginalPoint(params: {
  clientX: number
  clientY: number
  boxRect: ElementBoxRect
  imgWidthPx: number
  imgHeightPx: number
}): DisplayClickConversionResult {
  const { clientX, clientY, boxRect, imgWidthPx, imgHeightPx } = params
  if (
    !Number.isFinite(clientX) ||
    !Number.isFinite(clientY) ||
    boxRect.width <= 0 ||
    boxRect.height <= 0 ||
    imgWidthPx <= 0 ||
    imgHeightPx <= 0
  ) {
    return { ok: false, reason: 'INVALID_DIMENSIONS', point: null }
  }

  const rect = getContainedImageRect(boxRect.width, boxRect.height, imgWidthPx, imgHeightPx)
  if (rect.renderedWidth <= 0 || rect.renderedHeight <= 0) {
    return { ok: false, reason: 'INVALID_DIMENSIONS', point: null }
  }

  const localX = clientX - boxRect.left
  const localY = clientY - boxRect.top
  const relX = localX - rect.offsetX
  const relY = localY - rect.offsetY

  const eps = 1e-6
  if (
    relX < -eps ||
    relX > rect.renderedWidth + eps ||
    relY < -eps ||
    relY > rect.renderedHeight + eps
  ) {
    return { ok: false, reason: 'OUTSIDE_IMAGE', point: null }
  }

  const x = clamp((relX / rect.renderedWidth) * imgWidthPx, 0, imgWidthPx)
  const y = clamp((relY / rect.renderedHeight) * imgHeightPx, 0, imgHeightPx)

  return {
    ok: true,
    reason: null,
    point: {
      x: Math.round(x * 100) / 100,
      y: Math.round(y * 100) / 100,
    },
  }
}

/**
 * Ubah koordinat piksel citra asli (x, y) menjadi koordinat pada kotak elemen <img>
 * yang tampil dengan object-fit: contain.
 */
export function originalToDisplayPoint(params: {
  x: number
  y: number
  boxWidth: number
  boxHeight: number
  imgWidthPx: number
  imgHeightPx: number
}): DisplayPointResult | null {
  const { x, y, boxWidth, boxHeight, imgWidthPx, imgHeightPx } = params
  const rect = getContainedImageRect(boxWidth, boxHeight, imgWidthPx, imgHeightPx)
  if (rect.renderedWidth <= 0 || rect.renderedHeight <= 0) return null
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null

  const displayX = rect.offsetX + (clamp(x, 0, imgWidthPx) / imgWidthPx) * rect.renderedWidth
  const displayY = rect.offsetY + (clamp(y, 0, imgHeightPx) / imgHeightPx) * rect.renderedHeight

  return {
    x: displayX,
    y: displayY,
    pctX: (displayX / boxWidth) * 100,
    pctY: (displayY / boxHeight) * 100,
  }
}

/** Validasi sisi klien yang sinkron dengan backend/app/services/calibration.py. */
export function validateAndComputeCalibration(params: {
  p1: Point2D | null
  p2: Point2D | null
  lengthCm: number
  imgWidthPx: number
  imgHeightPx: number
  nWoundPx: number
}): ClientCalibrationResult {
  const { p1, p2, lengthCm, imgWidthPx, imgHeightPx, nWoundPx } = params

  if (imgWidthPx <= 0 || imgHeightPx <= 0 || !Number.isFinite(imgWidthPx) || !Number.isFinite(imgHeightPx)) {
    return {
      ok: false,
      error: 'Dimensi citra asli tidak valid untuk kalibrasi.',
      deltaPx: null,
      minDeltaPx: 0,
      scaleCmPerPx: null,
      areaCm2: null,
    }
  }

  const diagonalPx = Math.hypot(imgWidthPx, imgHeightPx)
  const minDeltaPx = MIN_DIAGONAL_RATIO * diagonalPx

  if (!p1 || !p2) {
    return {
      ok: false,
      error: !p1
        ? 'Pilih dua titik pada garis penggaris terlebih dahulu.'
        : 'Pilih titik kedua pada garis penggaris.',
      deltaPx: null,
      minDeltaPx,
      scaleCmPerPx: null,
      areaCm2: null,
    }
  }

  for (const val of [p1.x, p1.y, p2.x, p2.y]) {
    if (!Number.isFinite(val)) {
      return {
        ok: false,
        error: 'Koordinat titik kalibrasi harus berupa angka valid.',
        deltaPx: null,
        minDeltaPx,
        scaleCmPerPx: null,
        areaCm2: null,
      }
    }
  }

  if (p1.x < 0 || p1.x > imgWidthPx || p2.x < 0 || p2.x > imgWidthPx) {
    return {
      ok: false,
      error: `Koordinat X titik kalibrasi harus berada di dalam batas lebar citra [0, ${imgWidthPx}].`,
      deltaPx: null,
      minDeltaPx,
      scaleCmPerPx: null,
      areaCm2: null,
    }
  }

  if (p1.y < 0 || p1.y > imgHeightPx || p2.y < 0 || p2.y > imgHeightPx) {
    return {
      ok: false,
      error: `Koordinat Y titik kalibrasi harus berada di dalam batas tinggi citra [0, ${imgHeightPx}].`,
      deltaPx: null,
      minDeltaPx,
      scaleCmPerPx: null,
      areaCm2: null,
    }
  }

  const deltaPx = Math.hypot(p2.x - p1.x, p2.y - p1.y)

  if (!Number.isFinite(lengthCm) || lengthCm <= MIN_RULER_LENGTH_CM || lengthCm > MAX_RULER_LENGTH_CM) {
    return {
      ok: false,
      error: `Panjang penggaris nyata (length_cm) harus berada pada rentang (0, ${MAX_RULER_LENGTH_CM}] cm.`,
      deltaPx: Math.round(deltaPx * 10000) / 10000,
      minDeltaPx,
      scaleCmPerPx: null,
      areaCm2: null,
    }
  }

  if (deltaPx === 0) {
    return {
      ok: false,
      error: 'Dua titik penggaris tidak boleh berimpit (identik).',
      deltaPx: 0,
      minDeltaPx,
      scaleCmPerPx: null,
      areaCm2: null,
    }
  }

  if (deltaPx < minDeltaPx) {
    return {
      ok: false,
      error: `Jarak piksel antar titik penggaris terlalu dekat (${deltaPx.toFixed(2)} px < minimal 2% diagonal ${minDeltaPx.toFixed(2)} px).`,
      deltaPx: Math.round(deltaPx * 10000) / 10000,
      minDeltaPx,
      scaleCmPerPx: null,
      areaCm2: null,
    }
  }

  const scaleCmPerPx = lengthCm / deltaPx
  const equivOrigWoundPx = (Math.max(0, nWoundPx) / TOTAL_MASK_PIXELS) * (imgWidthPx * imgHeightPx)
  const rawAreaCm2 = equivOrigWoundPx * scaleCmPerPx * scaleCmPerPx

  return {
    ok: true,
    error: null,
    deltaPx: Math.round(deltaPx * 10000) / 10000,
    minDeltaPx,
    scaleCmPerPx: Math.round(scaleCmPerPx * 1000000) / 1000000,
    areaCm2: Math.round(rawAreaCm2 * 100) / 100,
  }
}
