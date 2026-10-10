import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { adjustmentMatrix, applyMatrix } from '../src/editor/colorMatrix.ts';
import { cropRect } from '../src/editor/crop.ts';
import { buildAtlas, CubeParseError, parseCube, sampleAtlas } from '../src/editor/cube.ts';
import { canRedo, canUndo, committed, editorReducer, initialEditorState, isDirty, MAX_HISTORY } from '../src/editor/history.ts';
import { IDENTITY, InvalidAdjustment, normalizeAdjustments } from '../src/editor/model.ts';
import { generate } from '../scripts/build-luts.mjs';

test('identity adjustments produce the identity matrix', () => {
  assert.deepEqual([...adjustmentMatrix(IDENTITY)].map((v) => Math.round(v * 1e9) / 1e9), [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0]);
});

test('saturation -1 yields equal channels (Rec.709 luma)', () => {
  const m = adjustmentMatrix({ ...IDENTITY, saturation: -1 });
  const [r, g, b] = applyMatrix(m, [0.8, 0.4, 0.1]);
  assert.ok(Math.abs(r - g) < 1e-9 && Math.abs(g - b) < 1e-9);
  assert.ok(Math.abs(r - (0.2126 * 0.8 + 0.7152 * 0.4 + 0.0722 * 0.1)) < 1e-9);
});

test('brightness and contrast move values in the expected direction, clamped', () => {
  const up = applyMatrix(adjustmentMatrix({ ...IDENTITY, brightness: 1 }), [0.5, 0.5, 0.5]);
  assert.ok(up[0] > 0.5);
  const hi = applyMatrix(adjustmentMatrix({ ...IDENTITY, contrast: 1 }), [0.9, 0.5, 0.1]);
  assert.deepEqual(hi, [1, 0.5, 0]);
  const warm = applyMatrix(adjustmentMatrix({ ...IDENTITY, warmth: 1 }), [0.5, 0.5, 0.5]);
  assert.ok(warm[0] > 0.5 && warm[2] < 0.5);
});

test('normalizeAdjustments clamps and rejects non-finite or unknown values', () => {
  assert.equal(normalizeAdjustments({ ...IDENTITY, brightness: 3 }).brightness, 1);
  assert.throws(() => normalizeAdjustments({ ...IDENTITY, contrast: Number.NaN }), InvalidAdjustment);
  assert.throws(() => normalizeAdjustments({ ...IDENTITY, look: 'neon' as never }), InvalidAdjustment);
  assert.throws(() => normalizeAdjustments({ ...IDENTITY, crop: '3:2' as never }), InvalidAdjustment);
});

test('crop rects are centered, integer and inside the source', () => {
  assert.deepEqual(cropRect(1024, 1536, 'original'), { x: 0, y: 0, width: 1024, height: 1536 });
  assert.deepEqual(cropRect(1024, 1536, '1:1'), { x: 0, y: 256, width: 1024, height: 1024 });
  assert.deepEqual(cropRect(1024, 1536, '4:5'), { x: 0, y: 128, width: 1024, height: 1280 });
  assert.deepEqual(cropRect(4000, 3000, '9:16'), { x: 1156, y: 0, width: 1688, height: 3000 });
  for (const [w, h] of [[1, 1], [3, 7], [4032, 3024], [6000, 4000]] as const) {
    for (const a of ['original', '1:1', '4:5', '9:16'] as const) {
      const r = cropRect(w, h, a);
      assert.ok(r.x >= 0 && r.y >= 0 && r.x + r.width <= w && r.y + r.height <= h && r.width >= 1 && r.height >= 1);
    }
  }
  assert.throws(() => cropRect(0, 10, 'original'), RangeError);
});

test('candidate does not commit until apply; undo/redo walk committed history', () => {
  let s = initialEditorState();
  s = editorReducer(s, { type: 'edit', patch: { brightness: 0.3 } });
  assert.ok(isDirty(s));
  assert.equal(committed(s).brightness, 0);
  s = editorReducer(s, { type: 'apply' });
  assert.ok(!isDirty(s));
  assert.equal(committed(s).brightness, 0.3);
  s = editorReducer(s, { type: 'edit', patch: { look: 'soft-warm' } });
  s = editorReducer(s, { type: 'apply' });
  assert.equal(s.index, 2);
  s = editorReducer(s, { type: 'undo' });
  assert.equal(committed(s).look, null);
  assert.equal(s.candidate.brightness, 0.3);
  assert.ok(canRedo(s));
  s = editorReducer(s, { type: 'redo' });
  assert.equal(committed(s).look, 'soft-warm');
  // A new apply after undo drops the redo branch.
  s = editorReducer(editorReducer(s, { type: 'undo' }), { type: 'edit', patch: { contrast: 0.2 } });
  s = editorReducer(s, { type: 'apply' });
  assert.equal(s.history.length, 3);
  assert.ok(!canRedo(s));
});

test('undo with an unapplied candidate only discards the candidate', () => {
  let s = editorReducer(initialEditorState(), { type: 'edit', patch: { brightness: 0.5 } });
  s = editorReducer(s, { type: 'apply' });
  s = editorReducer(s, { type: 'edit', patch: { brightness: -0.5 } });
  const before = s.candidateRevision;
  s = editorReducer(s, { type: 'undo' });
  assert.equal(s.candidate.brightness, 0.5);
  assert.equal(s.index, 1);
  assert.equal(s.candidateRevision, before + 1);
});

test('reset is a candidate that must be applied; apply of unchanged state is a no-op', () => {
  let s = editorReducer(editorReducer(initialEditorState(), { type: 'edit', patch: { saturation: 0.4 } }), { type: 'apply' });
  s = editorReducer(s, { type: 'reset' });
  assert.equal(committed(s).saturation, 0.4);
  s = editorReducer(s, { type: 'apply' });
  assert.equal(committed(s).saturation, 0);
  assert.equal(editorReducer(s, { type: 'apply' }), s);
  assert.ok(canUndo(s));
  assert.ok(!canUndo(initialEditorState()));
});

test('history is capped and always keeps the unedited source first', () => {
  let s = initialEditorState();
  for (let i = 1; i <= MAX_HISTORY + 20; i++) {
    s = editorReducer(editorReducer(s, { type: 'edit', patch: { brightness: (i % 100) / 100 + 0.001 } }), { type: 'apply' });
  }
  assert.equal(s.history.length, MAX_HISTORY);
  assert.equal(s.history[0], IDENTITY);
  assert.equal(s.index, MAX_HISTORY - 1);
});

const lutDir = new URL('../../../assets/luts/', import.meta.url);

test('cube files parse to 17^3 LUTs and identity-like corners', () => {
  for (const id of ['soft-warm', 'cool-clean', 'muted-film', 'balanced-mono']) {
    const cube = parseCube(readFileSync(new URL(`${id}.cube`, lutDir), 'utf8'));
    assert.equal(cube.size, 17);
    assert.equal(cube.data.length, 17 ** 3 * 3);
  }
  assert.throws(() => parseCube('LUT_3D_SIZE 2\n0 0 0\n'), CubeParseError);
  assert.throws(() => parseCube('LUT_1D_SIZE 2\n'), CubeParseError);
});

test('atlas sampling at grid points returns the cube entry', () => {
  const cube = parseCube(readFileSync(new URL('soft-warm.cube', lutDir), 'utf8'));
  const atlas = buildAtlas(cube);
  const idx = ((5 * 17 + 3) * 17 + 11) * 3; // r=11, g=3, b=5
  const got = sampleAtlas(atlas, 17, [11 / 16, 3 / 16, 5 / 16]);
  for (let c = 0; c < 3; c++) assert.ok(Math.abs(got[c]! - Math.round(cube.data[idx + c]! * 255) / 255) < 1e-9);
});

test('generated LUT module matches assets/luts', () => {
  assert.equal(readFileSync(new URL('../src/editor/luts.generated.ts', import.meta.url), 'utf8'), generate());
});
