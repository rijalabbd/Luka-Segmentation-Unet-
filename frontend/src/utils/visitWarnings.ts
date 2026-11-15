import { formatDecimalID } from './formatters.ts'

export interface WarningMeta {
  code: string
  title: string
  text: string
  strong: boolean
  role: 'alert' | 'status'
}

const DISTANCE_WARNING_BODY =
  'Foto tanpa penggaris: beda jarak bisa menggeser angka ini. Cek ulang dengan overlay.'

export const WARNING_DEFINITIONS: Record<string, Omit<WarningMeta, 'code'>> = {
  DISTANCE_SENSITIVE: {
    title: 'Peka terhadap jarak foto',
    text: DISTANCE_WARNING_BODY,
    strong: false,
    role: 'status',
  },
  DISTANCE_LARGE: {
    title: 'Peka terhadap jarak foto',
    text: DISTANCE_WARNING_BODY,
    strong: true,
    role: 'alert',
  },
  MIXED_BASIS: {
    title: 'Mode ukur berbeda dengan pemeriksaan pertama',
    text: 'Perubahan luas dihitung dari luas foto karena pemeriksaan pertama belum memakai penggaris.',
    strong: false,
    role: 'status',
  },
  LOW_BASELINE: {
    title: 'Luas awal sangat kecil',
    text: 'Luas pemeriksaan pertama kurang dari 1% foto, sehingga angka perubahan luas sangat peka terhadap selisih kecil.',
    strong: false,
    role: 'status',
  },
}

/**
 * Filter dan petakan kode peringatan sesuai basis PAC:
 * peringatan variasi jarak hanya berlaku pada pac_basis === 'relative'
 * dan ditampilkan maksimal satu kali agar tidak berulang.
 */
export function buildActiveWarnings(
  warnings: string[] | null | undefined,
  pacBasis: 'relative' | 'calibrated' | null | undefined,
): WarningMeta[] {
  const list: WarningMeta[] = []
  let hasDistanceWarning = false
  for (const code of warnings ?? []) {
    if (code === 'DISTANCE_SENSITIVE' || code === 'DISTANCE_LARGE') {
      if (pacBasis !== 'relative' || hasDistanceWarning) continue
      hasDistanceWarning = true
    }
    const def = WARNING_DEFINITIONS[code]
    if (def) {
      list.push({ code, ...def })
    }
  }
  return list
}

export type TrendClass = 'down' | 'up' | 'flat' | 'na'

export interface TrendSummary {
  cssClass: TrendClass
  arrow: string
  label: string
  unsignedPctText: string
  headline: string
}

export function getTrendCssClass(trendStatus: string | null | undefined): TrendClass {
  const txt = (trendStatus || '').toLowerCase()
  if (txt.includes('tidak dapat dihitung')) return 'na'
  if (txt.includes('menurun') || txt.includes('mengecil')) return 'down'
  if (txt.includes('meningkat') || txt.includes('membesar')) return 'up'
  return 'flat'
}

export function formatTrendSummary(
  trendStatus: string | null | undefined,
  pac: number | null | undefined,
): TrendSummary {
  const cssClass = getTrendCssClass(trendStatus)
  if (cssClass === 'na' || pac === null || pac === undefined || Number.isNaN(pac)) {
    return {
      cssClass: 'na',
      arrow: '·',
      label: 'Perubahan belum dapat dihitung',
      unsignedPctText: '',
      headline: 'Perubahan belum dapat dihitung',
    }
  }

  const label =
    cssClass === 'down'
      ? 'Terlihat mengecil'
      : cssClass === 'up'
        ? 'Terlihat membesar'
        : 'Relatif sama'
  const arrow = cssClass === 'down' ? '↓' : cssClass === 'up' ? '↑' : '→'
  const unsignedPctText = `${formatDecimalID(Math.abs(pac), 1)}%`
  return {
    cssClass,
    arrow,
    label,
    unsignedPctText,
    headline: `${label} ${unsignedPctText}`,
  }
}

export interface AreaBarItem {
  key: 'awal' | 'sekarang'
  label: string
  value: number
  widthPct: number
  valueText: string
}

export function buildAreaComparisonBars(params: {
  awal: number | null | undefined
  sekarang: number | null | undefined
  unit: '%' | ' cm²'
}): AreaBarItem[] {
  const { awal, sekarang, unit } = params
  if (
    awal === null ||
    awal === undefined ||
    Number.isNaN(awal) ||
    sekarang === null ||
    sekarang === undefined ||
    Number.isNaN(sekarang)
  ) {
    return []
  }

  const safeAwal = Math.max(0, awal)
  const safeSekarang = Math.max(0, sekarang)
  const scaleMax = Math.max(safeAwal, safeSekarang, 0.1)

  const toWidth = (v: number): number => {
    if (v <= 0) return 0
    return Math.min(100, Math.max(4, (v / scaleMax) * 100))
  }

  return [
    {
      key: 'awal',
      label: 'Awal',
      value: safeAwal,
      widthPct: toWidth(safeAwal),
      valueText: `${formatDecimalID(safeAwal, 1)}${unit}`,
    },
    {
      key: 'sekarang',
      label: 'Sekarang',
      value: safeSekarang,
      widthPct: toWidth(safeSekarang),
      valueText: `${formatDecimalID(safeSekarang, 1)}${unit}`,
    },
  ]
}
