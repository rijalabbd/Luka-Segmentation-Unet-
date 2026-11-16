import assert from 'node:assert/strict';
import test from 'node:test';
import { COARSE_POINTER_QUERY, isCoarsePointerDevice } from './touchDevice.ts';

test('isCoarsePointerDevice mengembalikan true bila query (any-pointer: coarse) cocok', () => {
  let receivedQuery = '';
  const result = isCoarsePointerDevice((q) => {
    receivedQuery = q;
    return { matches: true };
  });
  assert.equal(receivedQuery, COARSE_POINTER_QUERY);
  assert.equal(result, true);
});

test('isCoarsePointerDevice mengembalikan false pada desktop mouse', () => {
  assert.equal(
    isCoarsePointerDevice(() => ({ matches: false })),
    false,
  );
});

test('isCoarsePointerDevice mengembalikan false bila matchMedia tidak tersedia atau gagal', () => {
  assert.equal(isCoarsePointerDevice(null), false);
  assert.equal(
    isCoarsePointerDevice(() => {
      throw new Error('matchMedia unsupported');
    }),
    false,
  );
});
