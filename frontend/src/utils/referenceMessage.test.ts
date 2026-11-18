import assert from 'node:assert/strict';
import test from 'node:test';
import type { VisitRecord } from '../types/patient';
import { buildReferenceComparisonInfo } from './referenceMessage.ts';

function makeVisit(id: number, date: string, imagePath: string | null): VisitRecord {
  return {
    id,
    patient_id: 'RM-TEST',
    visit_date: date,
    status: 'final',
    visit_index: id,
    image_path: imagePath,
    mask_path: null,
    overlay_path: null,
    distance_confirmed: true,
    confirm_zero_area: false,
    n_wound_px: 1000,
    area_pct: 1.5,
    delta_area: null,
    pac: null,
    trend_status: null,
    measure_mode: 'relative',
    img_width_px: 256,
    img_height_px: 256,
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
    preview: null,
    clinician_notes: null,
    patient_narrative: null,
    narrative_source: null,
    warnings: [],
    created_at: `${date}T00:00:00Z`,
    confirmed_at: `${date}T00:05:00Z`,
  };
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des'];
function fmtShort(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  const [y, m, d] = dateStr.slice(0, 10).split('-').map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

test('kunjungan antara tanpa foto: tampilkan pembanding foto berfoto dan kalimat kunjungan tanpa foto', () => {
  const visits = [
    makeVisit(1, '2026-10-03', null),
    makeVisit(2, '2026-10-24', 'uploads/rm_2.jpg'),
  ];
  const info = buildReferenceComparisonInfo(visits, 'baseline', fmtShort);
  assert.equal(info.effectiveRefVisit?.id, 2);
  assert.equal(info.hasDistinctLatestWithPhoto, false);
  assert.equal(info.comparisonSentence, 'Foto awal dari 24 Okt 2026 dipakai sebagai pembanding.');
  assert.equal(info.missingPhotoSentence, 'Kunjungan 3 Okt 2026 tidak punya foto.');
});

test('semua kunjungan sebelumnya tidak punya foto (contoh RM-0012): tidak menampilkan tombol lihat foto terakhir palsu', () => {
  const visits = [
    makeVisit(43, '2026-10-03', null),
    makeVisit(44, '2026-10-17', null),
    makeVisit(45, '2026-10-24', null),
  ];
  const info = buildReferenceComparisonInfo(visits, 'baseline', fmtShort);
  assert.equal(info.effectiveRefVisit, null);
  assert.equal(info.hasDistinctLatestWithPhoto, false);
  assert.equal(
    info.comparisonSentence,
    'Belum ada foto pembanding dari kunjungan sebelumnya. Ikuti panduan foto di bawah.',
  );
  assert.equal(
    info.missingPhotoSentence,
    'Kunjungan 3 Okt 2026, 17 Okt 2026, dan 24 Okt 2026 tidak punya foto.',
  );
});

test('semua kunjungan punya foto dan berbeda antara awal dan terakhir', () => {
  const visits = [
    makeVisit(10, '2026-10-03', 'uploads/10.jpg'),
    makeVisit(11, '2026-10-24', 'uploads/11.jpg'),
  ];
  const baseInfo = buildReferenceComparisonInfo(visits, 'baseline', fmtShort);
  assert.equal(baseInfo.effectiveRefVisit?.id, 10);
  assert.equal(baseInfo.hasDistinctLatestWithPhoto, true);
  assert.equal(baseInfo.comparisonSentence, 'Foto awal dari 3 Okt 2026 dipakai sebagai pembanding.');
  assert.equal(baseInfo.missingPhotoSentence, '');

  const latestInfo = buildReferenceComparisonInfo(visits, 'latest', fmtShort);
  assert.equal(latestInfo.effectiveRefVisit?.id, 11);
  assert.equal(
    latestInfo.comparisonSentence,
    'Foto terakhir dari 24 Okt 2026 dipakai sebagai pembanding.',
  );
});

test('K.3: foto awal dan terakhir pada tanggal sama tidak memunculkan tautan lihat foto terakhir', () => {
  const visits = [
    makeVisit(52, '2026-11-15', 'uploads/RM-0024_awal.jpg'),
    makeVisit(53, '2026-11-15', 'uploads/RM-0024_kedua.jpg'),
  ];
  const info = buildReferenceComparisonInfo(visits, 'baseline', fmtShort);
  assert.equal(info.hasDistinctLatestWithPhoto, false);
  assert.equal(info.latestWithPhotoVisit, null);
});
