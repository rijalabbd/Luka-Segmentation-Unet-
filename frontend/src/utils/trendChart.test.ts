import assert from 'node:assert/strict'
import test from 'node:test'
import type { VisitRecord } from '../types/patient.ts'
import { computeTrendChartModel } from './trendChart.ts'

function makeVisit(overrides: Partial<VisitRecord> & { id: number; visit_date: string }): VisitRecord {
  return {
    patient_id: 'RM-TEST',
    status: 'final',
    visit_index: 1,
    image_path: null,
    mask_path: null,
    overlay_path: null,
    distance_confirmed: true,
    confirm_zero_area: false,
    n_wound_px: 3000,
    area_pct: 5.0,
    delta_area: null,
    pac: null,
    trend_status: null,
    measure_mode: 'relative',
    img_width_px: 1200,
    img_height_px: 900,
    calib_x1: null,
    calib_y1: null,
    calib_x2: null,
    calib_y2: null,
    calib_length_cm: null,
    scale_cm_per_px: null,
    area_cm2: null,
    pac_rel: null,
    pac_cm2: null,
    pac_basis: null,
    warnings: null,
    preview: null,
    clinician_notes: null,
    patient_narrative: null,
    narrative_source: null,
    created_at: '2026-10-01T00:00:00Z',
    confirmed_at: '2026-10-01T00:00:00Z',
    ...overrides,
  }
}

test('grafik kosong dan baseline tunggal mengembalikan mode khusus', () => {
  const emptyModel = computeTrendChartModel([], 640)
  assert.equal(emptyModel.mode, 'empty')
  assert.equal(emptyModel.series.length, 0)

  const singleModel = computeTrendChartModel(
    [makeVisit({ id: 1, visit_index: 1, visit_date: '2026-10-01', area_pct: 8.5 })],
    640,
  )
  assert.equal(singleModel.mode, 'baseline_only')
  assert.equal(singleModel.series.length, 0)
  assert.match(singleModel.ariaLabel, /kunjungan kedua/i)
})

test('pasien semua relatif (3 kunjungan seperti RM-0012): satu seri PAC relatif dengan skala dinamis', () => {
  const visits = [
    makeVisit({ id: 1, visit_index: 1, visit_date: '2026-10-01', area_pct: 10.26 }),
    makeVisit({
      id: 2,
      visit_index: 2,
      visit_date: '2026-10-17',
      area_pct: 7.65,
      delta_area: -2.61,
      pac: 25.44,
      pac_rel: 25.44,
      pac_basis: 'relative',
    }),
    makeVisit({
      id: 3,
      visit_index: 3,
      visit_date: '2026-10-31',
      area_pct: 8.1,
      delta_area: -2.16,
      pac: 21.05,
      pac_rel: 21.05,
      pac_basis: 'relative',
    }),
  ]

  const model = computeTrendChartModel(visits, 720)
  assert.equal(model.mode, 'single_relative')
  assert.equal(model.hasMixedMeasurementModes, false)
  assert.equal(model.series.length, 1)
  assert.equal(model.series[0]?.id, 'relative')
  assert.equal(model.series[0]?.points.length, 3)
  assert.equal(model.yMin, 0)
  assert.ok(model.yMax >= 30)
})

test('pasien semua terkalibrasi cm²: memakai seri tunggal terkalibrasi tanpa garis relatif', () => {
  const visits = [
    makeVisit({
      id: 1,
      visit_index: 1,
      visit_date: '2026-10-01',
      measure_mode: 'calibrated',
      area_pct: 10.0,
      area_cm2: 12.0,
      scale_cm_per_px: 0.02,
    }),
    makeVisit({
      id: 2,
      visit_index: 2,
      visit_date: '2026-10-15',
      measure_mode: 'calibrated',
      area_pct: 6.5,
      area_cm2: 9.0,
      scale_cm_per_px: 0.021,
      delta_area: -3.0,
      pac: 25.0,
      pac_rel: 35.0,
      pac_cm2: 25.0,
      pac_basis: 'calibrated',
    }),
  ]

  const model = computeTrendChartModel(visits, 720)
  assert.equal(model.mode, 'single_calibrated')
  assert.equal(model.hasMixedMeasurementModes, false)
  assert.equal(model.series.length, 1)
  assert.equal(model.series[0]?.id, 'calibrated')
  assert.equal(model.series[0]?.points[1]?.pac, 25.0)
  assert.match(model.series[0]?.points[1]?.areaText ?? '', /9,00 cm²/)
})

test('mode campuran dengan baseline terkalibrasi menampilkan dua seri terpisah; titik cm² hanya untuk kunjungan terkalibrasi', () => {
  const visits = [
    makeVisit({
      id: 1,
      visit_index: 1,
      visit_date: '2026-10-01',
      measure_mode: 'calibrated',
      area_pct: 10.0,
      area_cm2: 12.0,
    }),
    makeVisit({
      id: 2,
      visit_index: 2,
      visit_date: '2026-10-10',
      measure_mode: 'relative',
      area_pct: 8.0,
      delta_area: -2.0,
      pac: 20.0,
      pac_rel: 20.0,
      pac_cm2: null,
      pac_basis: 'relative',
    }),
    makeVisit({
      id: 3,
      visit_index: 3,
      visit_date: '2026-10-20',
      measure_mode: 'calibrated',
      area_pct: 5.0,
      area_cm2: 7.2,
      delta_area: -4.8,
      pac: 40.0,
      pac_rel: 50.0,
      pac_cm2: 40.0,
      pac_basis: 'calibrated',
    }),
  ]

  const model = computeTrendChartModel(visits, 720)
  assert.equal(model.mode, 'mixed_dual')
  assert.equal(model.hasMixedMeasurementModes, true)
  assert.equal(model.series.length, 2)

  const calSeries = model.series.find((s) => s.id === 'calibrated')
  const relSeries = model.series.find((s) => s.id === 'relative')
  assert.equal(calSeries?.points.length, 2)
  assert.deepEqual(
    calSeries?.points.map((p) => p.visitNumber),
    [1, 3],
  )
  assert.equal(relSeries?.points.length, 3)
})

test('mode campuran saat baseline relatif (MIXED_BASIS) dan skala Y dinamis nilai ekstrem', () => {
  const visits = [
    makeVisit({ id: 1, visit_index: 1, visit_date: '2026-10-01', area_pct: 5.0 }),
    makeVisit({
      id: 2,
      visit_index: 2,
      visit_date: '2026-10-10',
      measure_mode: 'calibrated',
      area_pct: 8.25,
      area_cm2: 10.5,
      delta_area: 3.25,
      pac: -65.0,
      pac_rel: -65.0,
      pac_cm2: null,
      pac_basis: 'relative',
    }),
    makeVisit({
      id: 3,
      visit_index: 3,
      visit_date: '2026-10-20',
      measure_mode: 'calibrated',
      area_pct: 0.25,
      area_cm2: 0.4,
      delta_area: -4.75,
      pac: 95.0,
      pac_rel: 95.0,
      pac_cm2: null,
      pac_basis: 'relative',
    }),
  ]

  const model = computeTrendChartModel(visits, 720)
  assert.equal(model.mode, 'single_relative')
  assert.equal(model.hasMixedMeasurementModes, true)
  assert.ok(model.yMin <= -70)
  assert.ok(model.yMax >= 100)
  assert.ok(model.ticks.some((t) => t.isZero))
})

test('data lama / seed relatif dengan pac_rel=null dan pac_basis=null tetap memakai kolom pac', () => {
  const visits = [
    makeVisit({ id: 1, visit_index: 1, visit_date: '2026-10-03', area_pct: 10.26 }),
    makeVisit({
      id: 2,
      visit_index: 2,
      visit_date: '2026-10-17',
      area_pct: 7.65,
      delta_area: -2.61,
      pac: 25.44,
      pac_rel: null,
      pac_cm2: null,
      pac_basis: null,
    }),
    makeVisit({
      id: 3,
      visit_index: 3,
      visit_date: '2026-10-24',
      area_pct: 8.1,
      delta_area: -2.16,
      pac: 21.05,
      pac_rel: null,
      pac_cm2: null,
      pac_basis: null,
    }),
  ]

  const model = computeTrendChartModel(visits, 720)
  assert.equal(model.mode, 'single_relative')
  assert.equal(model.series[0]?.points.length, 3)
  assert.equal(model.series[0]?.points[1]?.pac, 25.44)
  assert.equal(model.series[0]?.points[2]?.pac, 21.05)
})
