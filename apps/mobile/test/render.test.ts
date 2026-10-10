// Runs the device render path (src/editor/render.ts) on CanvasKit and checks it
// against the CPU reference of the same transform chain.
import assert from 'node:assert/strict';
import { before, test } from 'node:test';
import type { Skia as SkiaApi, SkImage } from '@shopify/react-native-skia';
import { adjustmentMatrix, applyMatrix } from '../src/editor/colorMatrix.ts';
import { cropRect } from '../src/editor/crop.ts';
import { sampleAtlas } from '../src/editor/cube.ts';
import { loadLutAtlases } from '../src/editor/luts.ts';
import { type Adjustments, IDENTITY } from '../src/editor/model.ts';
import { createRenderer, type Renderer, SKIA_ENUMS } from '../src/editor/render.ts';
import { loadSkia, skiaEnums } from './skia.ts';

let Skia: typeof SkiaApi;
let renderer: Renderer;
const atlases = loadLutAtlases();
const W = 48;
const H = 64;
const source = new Uint8Array(W * H * 4);

before(async () => {
  Skia = await loadSkia();
  renderer = createRenderer(Skia, atlases);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      source[i] = Math.round((x / (W - 1)) * 255);
      source[i + 1] = Math.round((y / (H - 1)) * 255);
      source[i + 2] = (x * 37 + y * 11) % 256;
      source[i + 3] = 255;
    }
  }
});

function sourceImage(): SkImage {
  const img = Skia.Image.MakeImage(
    { width: W, height: H, colorType: SKIA_ENUMS.COLOR_RGBA_8888, alphaType: SKIA_ENUMS.ALPHA_UNPREMUL },
    Skia.Data.fromBytes(source),
    W * 4,
  );
  assert.ok(img);
  return img;
}

function pixels(img: SkImage): Uint8Array {
  const out = img.readPixels(0, 0, {
    width: img.width(),
    height: img.height(),
    colorType: SKIA_ENUMS.COLOR_RGBA_8888,
    alphaType: SKIA_ENUMS.ALPHA_UNPREMUL,
  });
  assert.ok(out instanceof Uint8Array);
  return out;
}

function reference(a: Adjustments, x: number, y: number): [number, number, number] {
  const i = (y * W + x) * 4;
  let rgb: [number, number, number] = [source[i]! / 255, source[i + 1]! / 255, source[i + 2]! / 255];
  if (a.look !== null) {
    const g = sampleAtlas(atlases[a.look].pixels, atlases[a.look].size, rgb);
    rgb = [0, 1, 2].map((c) => rgb[c]! + (g[c]! - rgb[c]!) * a.lookIntensity) as [number, number, number];
  }
  return applyMatrix(adjustmentMatrix(a), rgb);
}

function maxError(a: Adjustments): { err: number; width: number; height: number } {
  const out = renderer.renderFull(sourceImage(), a);
  const rect = cropRect(W, H, a.crop);
  assert.equal(out.width(), rect.width);
  assert.equal(out.height(), rect.height);
  const px = pixels(out);
  let err = 0;
  for (let y = 0; y < rect.height; y++) {
    for (let x = 0; x < rect.width; x++) {
      const ref = reference(a, x + rect.x, y + rect.y);
      for (let c = 0; c < 3; c++) err = Math.max(err, Math.abs(px[(y * rect.width + x) * 4 + c]! - ref[c]! * 255));
    }
  }
  return { err, width: out.width(), height: out.height() };
}

test('local enum constants match React Native Skia', () => {
  const e = skiaEnums();
  assert.equal(SKIA_ENUMS.TILE_CLAMP, e.TileMode!.Clamp);
  assert.equal(SKIA_ENUMS.FILTER_NEAREST, e.FilterMode!.Nearest);
  assert.equal(SKIA_ENUMS.FILTER_LINEAR, e.FilterMode!.Linear);
  assert.equal(SKIA_ENUMS.MIPMAP_NONE, e.MipmapMode!.None);
  assert.equal(SKIA_ENUMS.COLOR_RGBA_8888, e.ColorType!.RGBA_8888);
  assert.equal(SKIA_ENUMS.ALPHA_UNPREMUL, e.AlphaType!.Unpremul);
  assert.equal(SKIA_ENUMS.IMAGE_FORMAT_JPEG, e.ImageFormat!.JPEG);
  assert.equal(SKIA_ENUMS.IMAGE_FORMAT_PNG, e.ImageFormat!.PNG);
});

test('identity export reproduces source pixels exactly at source resolution', () => {
  const { err, width, height } = maxError(IDENTITY);
  assert.equal(width, W);
  assert.equal(height, H);
  assert.equal(err, 0);
});

test('colour adjustments match the CPU reference within 1/255', () => {
  const { err } = maxError({ ...IDENTITY, brightness: 0.2, contrast: 0.35, saturation: -0.4, warmth: 0.6 });
  assert.ok(err <= 1.01, `max error ${err}`);
});

for (const look of ['soft-warm', 'cool-clean', 'muted-film', 'balanced-mono'] as const) {
  test(`LUT shader (${look}) matches the CPU reference within 2/255`, () => {
    const { err } = maxError({ ...IDENTITY, look, lookIntensity: 0.75, contrast: 0.1 });
    assert.ok(err <= 2.01, `max error ${err}`);
  });
}

test('crop exports the crop rect at source resolution', () => {
  const { err, width, height } = maxError({ ...IDENTITY, crop: '1:1', brightness: -0.1 });
  assert.equal(width, 48);
  assert.equal(height, 48);
  assert.ok(err <= 1.01);
});

test('preview picture uses the same render path as export', () => {
  const a: Adjustments = { ...IDENTITY, look: 'muted-film', lookIntensity: 1, saturation: 0.3, crop: '4:5' };
  const img = sourceImage();
  const full = pixels(renderer.renderFull(img, a));
  const rect = renderer.outputRect(img, a);
  const surface = Skia.Surface.Make(rect.width, rect.height);
  assert.ok(surface);
  surface.getCanvas().drawPicture(renderer.picture(img, a, 1));
  surface.flush();
  const preview = pixels(surface.makeImageSnapshot());
  let err = 0;
  for (let i = 0; i < full.length; i++) err = Math.max(err, Math.abs(full[i]! - preview[i]!));
  assert.equal(err, 0);
});

test('JPEG encoding produces a JPEG', () => {
  const bytes = renderer.encodeJpeg(renderer.renderFull(sourceImage(), IDENTITY), 95);
  assert.deepEqual([...bytes.slice(0, 3)], [0xff, 0xd8, 0xff]);
});

test('invalid preview scale is rejected', () => {
  assert.throws(() => renderer.picture(sourceImage(), IDENTITY, 0));
  assert.throws(() => renderer.picture(sourceImage(), IDENTITY, Number.NaN));
});
