import assert from 'node:assert/strict';
import test from 'node:test';
import { computeCoverCropRect } from './cameraCrop.ts';

test('computeCoverCropRect memotong sisi kiri/kanan saat video 4:3 tampil di layar potret', () => {
  // Video 1600x1200 (4:3) di stage potret 360x540 (2:3) -> area terlihat 800x1200 di tengah
  const rect = computeCoverCropRect(1600, 1200, 360, 540);
  assert.deepEqual(rect, { sx: 400, sy: 0, sw: 800, sh: 1200 });
});

test('computeCoverCropRect memotong atas/bawah saat video potret tampil di layar lanskap', () => {
  // Video 720x960 (3:4) di stage 800x400 (2:1) -> area terlihat 720x360 di tengah
  const rect = computeCoverCropRect(720, 960, 800, 400);
  assert.deepEqual(rect, { sx: 0, sy: 300, sw: 720, sh: 360 });
});

test('computeCoverCropRect mengembalikan frame penuh saat rasio sama atau stage tidak terukur', () => {
  assert.deepEqual(computeCoverCropRect(1280, 960, 400, 300), {
    sx: 0,
    sy: 0,
    sw: 1280,
    sh: 960,
  });
  assert.deepEqual(computeCoverCropRect(1280, 960, 0, 0), {
    sx: 0,
    sy: 0,
    sw: 1280,
    sh: 960,
  });
});
