import type { VisitRecord } from '../types/patient.ts'
import { formatDateID, formatDecimalID, formatSignedDecimalID } from './formatters.ts'

export type ChartMode =
  | 'empty'
  | 'baseline_only'
  | 'single_relative'
  | 'single_calibrated'
  | 'mixed_dual'

export interface ChartPoint {
  visitId: number
  visitNumber: number
  visitDate: string
  shortDate: string
  dayOffset: number
  x: number
  y: number
  pac: number
  measureMode: 'relative' | 'calibrated'
  areaText: string
  pacBasisLabel: string
  staggerTop: number
  staggerBottom: number
  staggerX: number
}

export interface ChartSeries {
  id: 'relative' | 'calibrated'
  label: string
  stroke: string
  dashed: boolean
  points: ChartPoint[]
  polylinePoints: string
}

export interface ChartTick {
  value: number
  y: number
  label: string
  isZero: boolean
}

export interface TrendChartModel {
  mode: ChartMode
  hasMixedMeasurementModes: boolean
  width: number
  height: number
  plotLeft: number
  plotRight: number
  plotTop: number
  plotBottom: number
  xAxisLabelY: number
  yMin: number
  yMax: number
  ticks: ChartTick[]
  series: ChartSeries[]
  xAxisVisits: ChartPoint[]
  ariaLabel: string
  description: string
}

const MONTHS_SHORT = [
  'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
  'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des',
]

function parseDayNumber(iso: string): number | null {
  const parts = iso.split('-').map(Number)
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return null
  const [y, m, d] = parts
  return Math.round(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1) / 86400000)
}

function formatShortDate(iso: string): string {
  const parts = iso.split('-').map(Number)
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return iso
  const [, m, d] = parts
  const mon = MONTHS_SHORT[(m ?? 1) - 1] ?? ''
  return `${String(d).padStart(2, '0')} ${mon}`
}

function computeStagger(xs: number[], minGap: number): number[] {
  const rows: number[] = []
  xs.forEach((x, idx) => {
    if (idx > 0 && x - (xs[idx - 1] ?? 0) < minGap) {
      rows.push(1 - (rows[idx - 1] ?? 0))
    } else {
      rows.push(0)
    }
  })
  return rows
}

function pickTickStep(span: number): number {
  if (span <= 80) return 10
  if (span <= 180) return 20
  if (span <= 300) return 25
  return 50
}

function formatTickPercent(val: number): string {
  if (val === 0) return '0%'
  return `${val > 0 ? '+' : '−'}${Math.abs(val)}%`
}

export function sortVisitsChronologically(visits: VisitRecord[]): VisitRecord[] {
  return [...visits].sort((a, b) => {
    const idxA = a.visit_index ?? Number.MAX_SAFE_INTEGER
    const idxB = b.visit_index ?? Number.MAX_SAFE_INTEGER
    if (idxA !== idxB) return idxA - idxB
    if (a.visit_date !== b.visit_date) return a.visit_date.localeCompare(b.visit_date)
    return a.id - b.id
  })
}

export function computeTrendChartModel(
  visits: VisitRecord[],
  containerWidth: number,
  compact = false,
): TrendChartModel {
  const sorted = sortVisitsChronologically(visits)
  const W = Math.max(260, Math.floor(containerWidth))

  if (sorted.length === 0) {
    return {
      mode: 'empty',
      hasMixedMeasurementModes: false,
      width: W,
      height: 200,
      plotLeft: 56,
      plotRight: W - 12,
      plotTop: 40,
      plotBottom: 160,
      xAxisLabelY: 185,
      yMin: 0,
      yMax: 20,
      ticks: [],
      series: [],
      xAxisVisits: [],
      ariaLabel: 'Grafik tren PAC kosong: belum ada kunjungan tersimpan.',
      description: 'Belum ada data kunjungan final untuk ditampilkan pada grafik.',
    }
  }

  if (sorted.length === 1) {
    const only = sorted[0]!
    return {
      mode: 'baseline_only',
      hasMixedMeasurementModes: false,
      width: W,
      height: 200,
      plotLeft: 56,
      plotRight: W - 12,
      plotTop: 40,
      plotBottom: 160,
      xAxisLabelY: 185,
      yMin: 0,
      yMax: 20,
      ticks: [],
      series: [],
      xAxisVisits: [],
      ariaLabel: `Grafik tren PAC untuk baseline Kunjungan 1 (${formatDateID(only.visit_date)}): PAC dihitung mulai kunjungan kedua.`,
      description: 'Baru ada satu kunjungan baseline. PAC mulai dihitung pada kunjungan kedua.',
    }
  }

  const base = sorted[0]!
  const baseDay = parseDayNumber(base.visit_date)
  const dayOffsets = sorted.map((v, i) => {
    const dn = parseDayNumber(v.visit_date)
    if (baseDay === null || dn === null) return i
    return Math.max(0, dn - baseDay)
  })
  const maxDay = dayOffsets[dayOffsets.length - 1] ?? 0

  const plotLeft = 58
  const xMin = plotLeft + (compact ? 34 : 44)
  const xMax = Math.max(xMin + 40, W - (compact ? 34 : 44))
  const plotRight = W - 8

  const xs = sorted.map((_, idx) => {
    if (maxDay <= 0) {
      return xMin + (idx / (sorted.length - 1)) * (xMax - xMin)
    }
    return xMin + ((dayOffsets[idx] ?? 0) / maxDay) * (xMax - xMin)
  })

  const baselineCalibrated =
    base.measure_mode === 'calibrated' && base.area_cm2 !== null && base.area_cm2 > 0
  const allCalibrated = sorted.every(
    (v) => v.measure_mode === 'calibrated' && v.area_cm2 !== null,
  )
  const anyCalibrated = sorted.some(
    (v) => v.measure_mode === 'calibrated' && v.area_cm2 !== null,
  )
  const anyRelative = sorted.some((v) => v.measure_mode !== 'calibrated')
  const hasMixedMeasurementModes = anyCalibrated && anyRelative

  const rawRelPoints = sorted
    .map((v, idx) => {
      const pacVal =
        idx === 0 ? 0 : (v.pac_rel ?? (v.pac_basis !== 'calibrated' ? v.pac : null))
      if (pacVal === null || Number.isNaN(pacVal)) return null
      return { visit: v, idx, pac: pacVal }
    })
    .filter((item): item is { visit: VisitRecord; idx: number; pac: number } => item !== null)

  const rawCalPoints = baselineCalibrated
    ? sorted
        .map((v, idx) => {
          if (v.measure_mode !== 'calibrated' || v.area_cm2 === null) return null
          const pacVal =
            idx === 0 ? 0 : (v.pac_cm2 ?? (v.pac_basis === 'calibrated' ? v.pac : null))
          if (pacVal === null || Number.isNaN(pacVal)) return null
          return { visit: v, idx, pac: pacVal }
        })
        .filter((item): item is { visit: VisitRecord; idx: number; pac: number } => item !== null)
    : []

  const showCalSeries = rawCalPoints.length >= 2
  const mode: ChartMode =
    showCalSeries && allCalibrated
      ? 'single_calibrated'
      : showCalSeries
        ? 'mixed_dual'
        : 'single_relative'

  const allValues = [
    0,
    ...(mode === 'single_calibrated'
      ? rawCalPoints.map((p) => p.pac)
      : [
          ...rawRelPoints.map((p) => p.pac),
          ...(showCalSeries ? rawCalPoints.map((p) => p.pac) : []),
        ]),
  ]

  const minVal = Math.min(...allValues)
  const maxVal = Math.max(...allValues)
  const step = pickTickStep(Math.max(20, maxVal - minVal))
  const yMin = minVal < 0 ? Math.floor((minVal - 2) / step) * step : 0
  const yMax = Math.max(step * 2, Math.ceil((maxVal + 2) / step) * step)

  const topStag = computeStagger(xs, compact ? 58 : 68)
  const absStag = computeStagger(xs, compact ? 62 : 92)
  const xStag = computeStagger(xs, compact ? 74 : 88)

  const topExtra = topStag.some(Boolean) ? 18 : 0
  const absExtra = absStag.some(Boolean) ? 16 : 0
  const xExtra = xStag.some(Boolean) ? 32 : 0

  const plotTop = 46 + topExtra
  const plotHeight = compact ? 155 : 175
  const plotBottom = plotTop + plotHeight
  const xAxisLabelY = plotBottom + 54 + absExtra
  const height = xAxisLabelY + 28 + xExtra

  const toY = (val: number) => plotBottom - ((val - yMin) / (yMax - yMin)) * plotHeight

  const ticks: ChartTick[] = []
  for (let t = yMin; t <= yMax; t += step) {
    ticks.push({
      value: t,
      y: toY(t),
      label: formatTickPercent(t),
      isZero: t === 0,
    })
  }

  const mapPoint = (
    item: { visit: VisitRecord; idx: number; pac: number },
    seriesId: 'relative' | 'calibrated',
  ): ChartPoint => {
    const v = item.visit
    const idx = item.idx
    const visitNumber = v.visit_index ?? idx + 1
    const isCalArea = v.measure_mode === 'calibrated' && v.area_cm2 !== null
    const areaText =
      seriesId === 'calibrated' && isCalArea
        ? `${formatDecimalID(v.area_cm2)} cm²`
        : `${formatDecimalID(v.area_pct)}%`
    return {
      visitId: v.id,
      visitNumber,
      visitDate: v.visit_date,
      shortDate: formatShortDate(v.visit_date),
      dayOffset: dayOffsets[idx] ?? 0,
      x: xs[idx] ?? xMin,
      y: toY(item.pac),
      pac: item.pac,
      measureMode: v.measure_mode,
      areaText,
      pacBasisLabel: seriesId === 'calibrated' ? 'Terkalibrasi cm²' : 'Basis Relatif %',
      staggerTop: topStag[idx] ?? 0,
      staggerBottom: absStag[idx] ?? 0,
      staggerX: xStag[idx] ?? 0,
    }
  }

  const series: ChartSeries[] = []
  if (showCalSeries) {
    const calPoints = rawCalPoints.map((item) => mapPoint(item, 'calibrated'))
    series.push({
      id: 'calibrated',
      label: 'PAC terkalibrasi cm² (%)',
      stroke: '#2A6F73',
      dashed: false,
      points: calPoints,
      polylinePoints: calPoints.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '),
    })
  }

  if (mode !== 'single_calibrated') {
    const relPoints = rawRelPoints.map((item) => mapPoint(item, 'relative'))
    series.push({
      id: 'relative',
      label: 'PAC relatif luas citra (%)',
      stroke: mode === 'mixed_dual' ? '#0F2942' : '#2A6F73',
      dashed: mode === 'mixed_dual',
      points: relPoints,
      polylinePoints: relPoints.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '),
    })
  }

  const xAxisVisits = sorted.map((v, idx) =>
    mapPoint({ visit: v, idx, pac: 0 }, allCalibrated ? 'calibrated' : 'relative'),
  )

  const summaryParts = series.flatMap((s) =>
    s.points.map(
      (p) =>
        `Kunjungan ${p.visitNumber} (${formatDateID(p.visitDate)}, ${s.label}): PAC ${
          p.visitNumber === 1 ? '0,0% (baseline)' : `${formatSignedDecimalID(p.pac, 1)}%`
        }, luas ${p.areaText}`,
    ),
  )

  return {
    mode,
    hasMixedMeasurementModes,
    width: W,
    height,
    plotLeft,
    plotRight,
    plotTop,
    plotBottom,
    xAxisLabelY,
    yMin,
    yMax,
    ticks,
    series,
    xAxisVisits,
    ariaLabel: `Grafik perkembangan PAC untuk ${sorted.length} kunjungan.`,
    description: `${summaryParts.join('. ')}. Garis menanjak menandakan pengecilan area luka.`,
  }
}
