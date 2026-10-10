import assert from 'node:assert/strict';
import { test } from 'node:test';

// normalize.ts imports a native module; test its pure helper in isolation.
const { fitWithinPixels } = await import('../src/media/fit.ts');

test('fitWithinPixels keeps images at or under the cap unchanged', () => {
  assert.deepEqual(fitWithinPixels(4000, 6000, 24_000_000), { width: 4000, height: 6000 });
});

test('fitWithinPixels downscales larger images under the cap, keeping aspect', () => {
  for (const [w, h] of [[8064, 6048], [8160, 6120], [12000, 9000], [50000, 3]] as const) {
    const r = fitWithinPixels(w, h, 24_000_000);
    assert.ok(r.width * r.height <= 24_000_000);
    assert.ok(r.width * r.height > 23_900_000 || h < 10);
    assert.ok(Math.abs(r.width / r.height - w / h) / (w / h) < 0.01 || h < 10);
  }
});
