import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildActiveWarnings,
  buildAreaComparisonBars,
  formatTrendSummary,
  getTrendCssClass,
} from './visitWarnings.ts'

test('formatTrendSummary memetakan status tren ke bahasa awam tanpa tanda +/- pada judul', () => {
  const down = formatTrendSummary('Tren Menurun (Mengecil)', 68.24)
  assert.equal(down.cssClass, 'down')
  assert.equal(down.arrow, '↓')
  assert.equal(down.label, 'Terlihat mengecil')
  assert.equal(down.unsignedPctText, '68,2%')
  assert.equal(down.headline, 'Terlihat mengecil 68,2%')

  const up = formatTrendSummary('Tren Meningkat (Membesar)', -109.34)
  assert.equal(up.cssClass, 'up')
  assert.equal(up.arrow, '↑')
  assert.equal(up.label, 'Terlihat membesar')
  assert.equal(up.unsignedPctText, '109,3%')
  assert.equal(up.headline, 'Terlihat membesar 109,3%')

  const flat = formatTrendSummary('Tren Stabil', -2.14)
  assert.equal(flat.cssClass, 'flat')
  assert.equal(flat.arrow, '→')
  assert.equal(flat.label, 'Relatif sama')
  assert.equal(flat.unsignedPctText, '2,1%')
  assert.equal(flat.headline, 'Relatif sama 2,1%')

  const na = formatTrendSummary('PAC tidak dapat dihitung', null)
  assert.equal(na.cssClass, 'na')
  assert.equal(na.headline, 'Perubahan belum dapat dihitung')
})

test('getTrendCssClass mengenali status backend maupun label frontend', () => {
  assert.equal(getTrendCssClass('Tren Menurun (Mengecil)'), 'down')
  assert.equal(getTrendCssClass('Tren Meningkat (Membesar)'), 'up')
  assert.equal(getTrendCssClass('Tren Stabil'), 'flat')
})

test('buildActiveWarnings memadatkan peringatan jarak tanpa duplikasi dan tanpa kata terlarang', () => {
  const forbidden = /\b(membaik|memburuk|sembuh|parah)\b|A₀|Aₜ|ΔA/i

  const relWarnings = buildActiveWarnings(
    ['DISTANCE_SENSITIVE', 'DISTANCE_LARGE', 'LOW_BASELINE'],
    'relative',
  )
  assert.equal(relWarnings.length, 2)
  assert.equal(
    relWarnings[0]?.text,
    'Foto tanpa penggaris: beda jarak bisa menggeser angka ini. Cek ulang dengan overlay.',
  )
  assert.equal(relWarnings[1]?.title, 'Luas awal sangat kecil')
  for (const w of relWarnings) {
    assert.doesNotMatch(w.title, forbidden)
    assert.doesNotMatch(w.text, forbidden)
  }

  const calWarnings = buildActiveWarnings(['DISTANCE_LARGE', 'MIXED_BASIS'], 'calibrated')
  assert.equal(calWarnings.length, 1)
  assert.equal(calWarnings[0]?.code, 'MIXED_BASIS')
})

test('buildAreaComparisonBars menghitung skala dari nol dan format 1 desimal berkoma', () => {
  const bars = buildAreaComparisonBars({ awal: 12.64, sekarang: 26.42, unit: '%' })
  assert.equal(bars.length, 2)
  assert.equal(bars[0]?.label, 'Awal')
  assert.equal(bars[0]?.valueText, '12,6%')
  assert.equal(bars[1]?.label, 'Sekarang')
  assert.equal(bars[1]?.valueText, '26,4%')
  assert.equal(bars[1]?.widthPct, 100)
  assert.ok(bars[0]!.widthPct > 45 && bars[0]!.widthPct < 50)

  const zeroBars = buildAreaComparisonBars({ awal: 4.0, sekarang: 0, unit: ' cm²' })
  assert.equal(zeroBars[0]?.valueText, '4,0 cm²')
  assert.equal(zeroBars[0]?.widthPct, 100)
  assert.equal(zeroBars[1]?.valueText, '0,0 cm²')
  assert.equal(zeroBars[1]?.widthPct, 0)
})
