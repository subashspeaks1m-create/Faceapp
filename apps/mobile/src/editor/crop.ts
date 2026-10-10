import type { CropAspect } from './model.ts';

export interface Rect {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

const RATIOS: Record<Exclude<CropAspect, 'original'>, number> = { '1:1': 1, '4:5': 4 / 5, '9:16': 9 / 16 };

// Largest centered integer rect of the requested aspect inside the source, in source pixels.
export function cropRect(width: number, height: number, aspect: CropAspect): Rect {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1) {
    throw new RangeError('source dimensions must be positive integers');
  }
  if (aspect === 'original') return { x: 0, y: 0, width, height };
  const ratio = RATIOS[aspect];
  let w = width;
  let h = Math.round(w / ratio);
  if (h > height) {
    h = height;
    w = Math.round(h * ratio);
  }
  w = Math.max(1, Math.min(width, w));
  h = Math.max(1, Math.min(height, h));
  return { x: Math.floor((width - w) / 2), y: Math.floor((height - h) / 2), width: w, height: h };
}

// Uniform scale that fits content inside a display box.
export function fitScale(box: { width: number; height: number }, content: { width: number; height: number }): number {
  return Math.min(box.width / content.width, box.height / content.height);
}
