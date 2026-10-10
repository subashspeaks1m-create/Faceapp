// 4x5 row-major colour matrix in Skia's convention: out = M * [r, g, b, a, 1],
// with the translate column in normalized 0..1 units. The same matrix drives the
// preview canvas and the export surface, so both produce the same pixels.

import type { Adjustments } from './model.ts';

export type ColorMatrix = readonly number[];

// Rec. 709 luma weights applied to gamma-coded values: an artistic approximation.
const LR = 0.2126;
const LG = 0.7152;
const LB = 0.0722;

const IDENTITY_5: number[] = [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1];

function to5(m: ColorMatrix): number[] {
  return [...m, 0, 0, 0, 0, 1];
}

// Returns a * b (apply b first, then a).
function multiply(a: number[], b: number[]): number[] {
  const out = new Array<number>(25).fill(0);
  for (let r = 0; r < 5; r++) {
    for (let c = 0; c < 5; c++) {
      let sum = 0;
      for (let k = 0; k < 5; k++) sum += (a[r * 5 + k] ?? 0) * (b[k * 5 + c] ?? 0);
      out[r * 5 + c] = sum;
    }
  }
  return out;
}

export function warmthMatrix(w: number): ColorMatrix {
  return [1 + 0.12 * w, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1 - 0.12 * w, 0, 0, 0, 0, 0, 1, 0];
}

export function brightnessMatrix(b: number): ColorMatrix {
  const t = 0.25 * b;
  return [1, 0, 0, 0, t, 0, 1, 0, 0, t, 0, 0, 1, 0, t, 0, 0, 0, 1, 0];
}

export function contrastMatrix(c: number): ColorMatrix {
  const k = c >= 0 ? 1 + c : 1 + 0.75 * c;
  const t = 0.5 * (1 - k);
  return [k, 0, 0, 0, t, 0, k, 0, 0, t, 0, 0, k, 0, t, 0, 0, 0, 1, 0];
}

export function saturationMatrix(s: number): ColorMatrix {
  const k = 1 + s;
  const i = 1 - k;
  return [
    LR * i + k, LG * i, LB * i, 0, 0,
    LR * i, LG * i + k, LB * i, 0, 0,
    LR * i, LG * i, LB * i + k, 0, 0,
    0, 0, 0, 1, 0,
  ];
}

// Order: warmth -> brightness -> contrast -> saturation.
export function adjustmentMatrix(a: Adjustments): ColorMatrix {
  let m = IDENTITY_5;
  for (const step of [warmthMatrix(a.warmth), brightnessMatrix(a.brightness), contrastMatrix(a.contrast), saturationMatrix(a.saturation)]) {
    m = multiply(to5(step), m);
  }
  return m.slice(0, 20);
}

export function applyMatrix(m: ColorMatrix, rgb: readonly [number, number, number]): [number, number, number] {
  const [r, g, b] = rgb;
  const row = (i: number) => (m[i] ?? 0) * r + (m[i + 1] ?? 0) * g + (m[i + 2] ?? 0) * b + (m[i + 3] ?? 0) + (m[i + 4] ?? 0);
  const clamp = (v: number) => Math.min(1, Math.max(0, v));
  return [clamp(row(0)), clamp(row(5)), clamp(row(10))];
}
