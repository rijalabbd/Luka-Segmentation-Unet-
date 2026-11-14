import assert from 'node:assert/strict'
import test from 'node:test'
import {
  displayClickToOriginalPoint,
  getContainedImageRect,
  originalToDisplayPoint,
  validateAndComputeCalibration,
} from './calibrationCoords.ts'

test('citra persegi: konversi klik tampil <-> piksel citra asli simetris', () => {
  const boxRect = { left: 100, top: 50, width: 512, height: 512 }
  const click = displayClickToOriginalPoint({
    clientX: 100 + 128,
    clientY: 50 + 384,
    boxRect,
    imgWidthPx: 1024,
    imgHeightPx: 1024,
  })
  assert.equal(click.ok, true)
  assert.deepEqual(click.point, { x: 256, y: 768 })

  const disp = originalToDisplayPoint({
    x: 256,
    y: 768,
    boxWidth: 512,
    boxHeight: 512,
    imgWidthPx: 1024,
    imgHeightPx: 1024,
  })
  assert.ok(disp)
  assert.equal(disp.x, 128)
  assert.equal(disp.y, 384)
})

test('citra tidak persegi (1600x1200 pada kotak 800x600): pemetaan rasio aspek tepat', () => {
  const boxRect = { left: 40, top: 20, width: 800, height: 600 }
  const click = displayClickToOriginalPoint({
    clientX: 40 + 400,
    clientY: 20 + 150,
    boxRect,
    imgWidthPx: 1600,
    imgHeightPx: 1200,
  })
  assert.equal(click.ok, true)
  assert.deepEqual(click.point, { x: 800, y: 300 })

  const disp = originalToDisplayPoint({
    x: 800,
    y: 300,
    boxWidth: 800,
    boxHeight: 600,
    imgWidthPx: 1600,
    imgHeightPx: 1200,
  })
  assert.ok(disp)
  assert.equal(disp.x, 400)
  assert.equal(disp.y, 150)
})

test('object-fit: contain dengan bidang kosong horizontal (letterbox) & vertikal (pillarbox)', () => {
  // Letterbox: citra landscape 1600x800 (2:1) di kotak 800x600 (4:3)
  // rendered = 800x400, offsetX = 0, offsetY = 100
  const letterbox = getContainedImageRect(800, 600, 1600, 800)
  assert.equal(letterbox.offsetX, 0)
  assert.equal(letterbox.offsetY, 100)
  assert.equal(letterbox.renderedWidth, 800)
  assert.equal(letterbox.renderedHeight, 400)

  const clickInsideLetterbox = displayClickToOriginalPoint({
    clientX: 200,
    clientY: 200, // berada di 100 px ke dalam gambar (top margin = 100)
    boxRect: { left: 0, top: 0, width: 800, height: 600 },
    imgWidthPx: 1600,
    imgHeightPx: 800,
  })
  assert.equal(clickInsideLetterbox.ok, true)
  assert.deepEqual(clickInsideLetterbox.point, { x: 400, y: 200 })

  const dispLetterbox = originalToDisplayPoint({
    x: 400,
    y: 200,
    boxWidth: 800,
    boxHeight: 600,
    imgWidthPx: 1600,
    imgHeightPx: 800,
  })
  assert.ok(dispLetterbox)
  assert.equal(dispLetterbox.x, 200)
  assert.equal(dispLetterbox.y, 200)

  // Pillarbox: citra portrait 600x1200 (1:2) di kotak 800x600 (4:3)
  // rendered = 300x600, offsetX = 250, offsetY = 0
  const pillarbox = getContainedImageRect(800, 600, 600, 1200)
  assert.equal(pillarbox.offsetX, 250)
  assert.equal(pillarbox.offsetY, 0)
  assert.equal(pillarbox.renderedWidth, 300)
  assert.equal(pillarbox.renderedHeight, 600)

  const clickInsidePillarbox = displayClickToOriginalPoint({
    clientX: 400, // tengah horizontal (250 + 150)
    clientY: 300, // tengah vertikal
    boxRect: { left: 0, top: 0, width: 800, height: 600 },
    imgWidthPx: 600,
    imgHeightPx: 1200,
  })
  assert.equal(clickInsidePillarbox.ok, true)
  assert.deepEqual(clickInsidePillarbox.point, { x: 300, y: 600 })
})

test('klik di area kosong object-fit: contain dan luar elemen ditolak', () => {
  // Citra portrait 600x1200 di kotak 800x600 -> margin kosong x < 250 atau x > 550
  const boxRect = { left: 10, top: 20, width: 800, height: 600 }
  const leftMarginClick = displayClickToOriginalPoint({
    clientX: 10 + 100,
    clientY: 20 + 300,
    boxRect,
    imgWidthPx: 600,
    imgHeightPx: 1200,
  })
  assert.equal(leftMarginClick.ok, false)
  assert.equal(leftMarginClick.reason, 'OUTSIDE_IMAGE')
  assert.equal(leftMarginClick.point, null)

  const rightMarginClick = displayClickToOriginalPoint({
    clientX: 10 + 700,
    clientY: 20 + 300,
    boxRect,
    imgWidthPx: 600,
    imgHeightPx: 1200,
  })
  assert.equal(rightMarginClick.ok, false)
  assert.equal(rightMarginClick.reason, 'OUTSIDE_IMAGE')

  // Letterbox atas/bawah: 1600x800 di 800x600 -> margin kosong y < 100 atau y > 500
  const topMarginClick = displayClickToOriginalPoint({
    clientX: 10 + 400,
    clientY: 20 + 40,
    boxRect,
    imgWidthPx: 1600,
    imgHeightPx: 800,
  })
  assert.equal(topMarginClick.ok, false)
  assert.equal(topMarginClick.reason, 'OUTSIDE_IMAGE')
})

test('perubahan ukuran jendela / zoom mempertahankan koordinat asli', () => {
  // Misalnya zoom 125%: bounding box tampil berubah menjadi 1000x750
  const zoomedClick = displayClickToOriginalPoint({
    clientX: 500,
    clientY: 375,
    boxRect: { left: 0, top: 0, width: 1000, height: 750 },
    imgWidthPx: 1600,
    imgHeightPx: 1200,
  })
  assert.equal(zoomedClick.ok, true)
  assert.deepEqual(zoomedClick.point, { x: 800, y: 600 })

  // Saat jendela diperkecil menjadi 400x300, koordinat asli (800, 600) tergambar tepat di pusat baru (200, 150)
  const resizedDisplay = originalToDisplayPoint({
    x: 800,
    y: 600,
    boxWidth: 400,
    boxHeight: 300,
    imgWidthPx: 1600,
    imgHeightPx: 1200,
  })
  assert.ok(resizedDisplay)
  assert.equal(resizedDisplay.x, 200)
  assert.equal(resizedDisplay.y, 150)
})

test('validateAndComputeCalibration: rumus G2 dan validasi batas cocok dengan backend', () => {
  // PRD v3 Tes wajib 1: W=1600, H=1200, N=3277, dpx=80, L=2 -> s=0.025, area=60.00
  const valid = validateAndComputeCalibration({
    p1: { x: 100, y: 100 },
    p2: { x: 180, y: 100 },
    lengthCm: 2,
    imgWidthPx: 1600,
    imgHeightPx: 1200,
    nWoundPx: 3277,
  })
  assert.equal(valid.ok, true)
  assert.equal(valid.scaleCmPerPx, 0.025)
  assert.equal(valid.areaCm2, 60)

  const zeroLen = validateAndComputeCalibration({
    p1: { x: 100, y: 100 },
    p2: { x: 180, y: 100 },
    lengthCm: 0,
    imgWidthPx: 1600,
    imgHeightPx: 1200,
    nWoundPx: 3277,
  })
  assert.equal(zeroLen.ok, false)

  const samePt = validateAndComputeCalibration({
    p1: { x: 100, y: 100 },
    p2: { x: 100, y: 100 },
    lengthCm: 2,
    imgWidthPx: 1600,
    imgHeightPx: 1200,
    nWoundPx: 3277,
  })
  assert.equal(samePt.ok, false)

  // 2% diagonal 1600x1200 = 0.02 * 2000 = 40 px; dpx = 39 harus ditolak
  const tooClose = validateAndComputeCalibration({
    p1: { x: 100, y: 100 },
    p2: { x: 139, y: 100 },
    lengthCm: 2,
    imgWidthPx: 1600,
    imgHeightPx: 1200,
    nWoundPx: 3277,
  })
  assert.equal(tooClose.ok, false)
})
