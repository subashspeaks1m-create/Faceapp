// The single render path for preview and export. Transform chain, in order:
//   1. crop: source pixels -> crop rect (integer, source resolution)
//   2. look: 3D LUT, trilinear, blended with the source by lookIntensity
//   3. colour matrix: warmth -> brightness -> contrast -> saturation
//   4. scale: preview only; export always draws at scale 1 (crop-rect pixels)
// `Skia` is injected so the exact code runs on device and against CanvasKit in tests.

import type { Skia as SkiaApi, SkCanvas, SkImage, SkPicture, SkRuntimeEffect, SkShader } from '@shopify/react-native-skia';
import { adjustmentMatrix } from './colorMatrix.ts';
import { cropRect, type Rect } from './crop.ts';
import type { Adjustments, LookId } from './model.ts';

// Numeric values of Skia's enums, kept local so this module never imports the native entry.
const TILE_CLAMP = 0;
const FILTER_NEAREST = 0;
const FILTER_LINEAR = 1;
const MIPMAP_NONE = 0;
const COLOR_RGBA_8888 = 4;
const ALPHA_UNPREMUL = 3;
const IMAGE_FORMAT_JPEG = 3;
const IMAGE_FORMAT_PNG = 4;

export const SKIA_ENUMS = {
  TILE_CLAMP,
  FILTER_NEAREST,
  FILTER_LINEAR,
  MIPMAP_NONE,
  COLOR_RGBA_8888,
  ALPHA_UNPREMUL,
  IMAGE_FORMAT_JPEG,
  IMAGE_FORMAT_PNG,
} as const;

export const LUT_SKSL = `
uniform shader image;
uniform shader lut;
uniform float size;
uniform float intensity;

float3 texel(float r, float g, float b) {
  return lut.eval(float2(r + b * size + 0.5, g + 0.5)).rgb;
}

half4 main(float2 xy) {
  half4 c = image.eval(xy);
  float3 rgb = c.a > 0.0 ? float3(c.rgb) / float(c.a) : float3(0.0);
  float3 p = clamp(rgb, 0.0, 1.0) * (size - 1.0);
  float3 lo = floor(p);
  float3 hi = min(lo + 1.0, size - 1.0);
  float3 f = p - lo;
  float3 c00 = mix(texel(lo.r, lo.g, lo.b), texel(hi.r, lo.g, lo.b), f.r);
  float3 c10 = mix(texel(lo.r, hi.g, lo.b), texel(hi.r, hi.g, lo.b), f.r);
  float3 c01 = mix(texel(lo.r, lo.g, hi.b), texel(hi.r, lo.g, hi.b), f.r);
  float3 c11 = mix(texel(lo.r, hi.g, hi.b), texel(hi.r, hi.g, hi.b), f.r);
  float3 graded = mix(mix(c00, c10, f.g), mix(c01, c11, f.g), f.b);
  float3 outRgb = mix(rgb, graded, intensity);
  return half4(half3(outRgb * float(c.a)), c.a);
}
`;

export interface LutAtlas {
  readonly size: number;
  readonly pixels: Uint8Array;
}

export class RenderError extends Error {
  override readonly name = 'RenderError';
}

export interface Renderer {
  /** Records the edit at `scale` (display pixels per source pixel) for a <Picture>. */
  picture(image: SkImage, adjustments: Adjustments, scale: number): SkPicture;
  /** Renders the committed edit at source resolution (the crop rect's pixel size). */
  renderFull(image: SkImage, adjustments: Adjustments): SkImage;
  encodeJpeg(image: SkImage, quality: number): Uint8Array;
  outputRect(image: SkImage, adjustments: Adjustments): Rect;
}

export function createRenderer(Skia: typeof SkiaApi, atlases: Readonly<Record<LookId, LutAtlas>>): Renderer {
  const effect: SkRuntimeEffect | null = Skia.RuntimeEffect.Make(LUT_SKSL);
  if (effect === null) throw new RenderError('LUT shader failed to compile');

  const lutImages = new Map<LookId, SkImage>();
  const lutImage = (id: LookId): SkImage => {
    const cached = lutImages.get(id);
    if (cached) return cached;
    const atlas = atlases[id];
    const width = atlas.size * atlas.size;
    const img = Skia.Image.MakeImage(
      { width, height: atlas.size, colorType: COLOR_RGBA_8888, alphaType: ALPHA_UNPREMUL },
      Skia.Data.fromBytes(atlas.pixels),
      width * 4,
    );
    if (img === null) throw new RenderError('LUT image could not be created');
    lutImages.set(id, img);
    return img;
  };

  const draw = (canvas: SkCanvas, image: SkImage, a: Adjustments, scale: number): void => {
    const rect = cropRect(image.width(), image.height(), a.crop);
    let shader: SkShader = image.makeShaderOptions(TILE_CLAMP, TILE_CLAMP, FILTER_LINEAR, MIPMAP_NONE);
    if (a.look !== null && a.lookIntensity > 0) {
      const lut = lutImage(a.look);
      shader = effect.makeShaderWithChildren(
        [atlases[a.look].size, a.lookIntensity],
        [shader, lut.makeShaderOptions(TILE_CLAMP, TILE_CLAMP, FILTER_NEAREST, MIPMAP_NONE)],
      );
    }
    const paint = Skia.Paint();
    paint.setShader(shader);
    paint.setColorFilter(Skia.ColorFilter.MakeMatrix([...adjustmentMatrix(a)]));
    canvas.save();
    canvas.scale(scale, scale);
    canvas.translate(-rect.x, -rect.y);
    canvas.drawRect(Skia.XYWHRect(rect.x, rect.y, rect.width, rect.height), paint);
    canvas.restore();
  };

  return {
    outputRect: (image, a) => cropRect(image.width(), image.height(), a.crop),
    picture(image, a, scale) {
      if (!(scale > 0) || !Number.isFinite(scale)) throw new RenderError('invalid preview scale');
      const rect = cropRect(image.width(), image.height(), a.crop);
      const recorder = Skia.PictureRecorder();
      const canvas = recorder.beginRecording(Skia.XYWHRect(0, 0, rect.width * scale, rect.height * scale));
      draw(canvas, image, a, scale);
      return recorder.finishRecordingAsPicture();
    },
    renderFull(image, a) {
      const rect = cropRect(image.width(), image.height(), a.crop);
      const surface = Skia.Surface.MakeOffscreen(rect.width, rect.height) ?? Skia.Surface.Make(rect.width, rect.height);
      if (surface === null) throw new RenderError('could not allocate export surface');
      draw(surface.getCanvas(), image, a, 1);
      surface.flush();
      return surface.makeImageSnapshot();
    },
    encodeJpeg(image, quality) {
      const bytes = image.encodeToBytes(IMAGE_FORMAT_JPEG, quality);
      if (bytes.length === 0) throw new RenderError('JPEG encoding failed');
      return bytes;
    },
  };
}
