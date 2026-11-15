import assert from 'node:assert/strict';
import test from 'node:test';
import {
  clampGhostOffset,
  clampGhostPosition,
  clampGhostScale,
  createDefaultGhostTransform,
  isGhostModified,
} from './ghostTransform.ts';

test('createDefaultGhostTransform mengembalikan skala 100 dan posisi (0, 0)', () => {
  assert.deepEqual(createDefaultGhostTransform(), { scale: 100, x: 0, y: 0 });
});

test('clampGhostScale membatasi rentang 70..130 dan membulatkan angka', () => {
  assert.equal(clampGhostScale(50), 70);
  assert.equal(clampGhostScale(150), 130);
  assert.equal(clampGhostScale(105.4), 105);
  assert.equal(clampGhostScale(Number.NaN), 100);
});

test('clampGhostPosition membatasi geser maksimal 40% lebar dan tinggi bingkai', () => {
  assert.deepEqual(clampGhostPosition(250, -200, 400, 300), { x: 160, y: -120 });
  assert.deepEqual(clampGhostPosition(-180, 95, 400, 300), { x: -160, y: 95 });
  assert.equal(clampGhostOffset(50, 0), 0);
});

test('isGhostModified mendeteksi nilai non-bawaan untuk skala, geser, maupun transparansi', () => {
  assert.equal(isGhostModified(100, 0, 0, 40), false);
  assert.equal(isGhostModified(110, 0, 0, 40), true);
  assert.equal(isGhostModified(100, 12, 0, 40), true);
  assert.equal(isGhostModified(100, 0, -5, 40), true);
  assert.equal(isGhostModified(100, 0, 0, 60), true);
});
