// Adobe .cube 3D LUT parsing and the 2D atlas layout the Skia shader samples.
// Atlas: width = size*size, height = size; texel (r + b*size, g) holds LUT[r,g,b].

export interface Cube {
  readonly size: number;
  readonly data: Float32Array; // size^3 * 3, red fastest, then green, then blue
}

export class CubeParseError extends Error {
  override readonly name = 'CubeParseError';
}

export function parseCube(text: string): Cube {
  let size = 0;
  const values: number[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (line === '' || line.startsWith('#') || line.startsWith('TITLE')) continue;
    if (line.startsWith('LUT_3D_SIZE')) {
      size = Number(line.split(/\s+/)[1]);
      continue;
    }
    if (line.startsWith('DOMAIN_MIN')) {
      if (line.split(/\s+/).slice(1).some((v) => Number(v) !== 0)) throw new CubeParseError('DOMAIN_MIN must be 0');
      continue;
    }
    if (line.startsWith('DOMAIN_MAX')) {
      if (line.split(/\s+/).slice(1).some((v) => Number(v) !== 1)) throw new CubeParseError('DOMAIN_MAX must be 1');
      continue;
    }
    if (/^[A-Z_]/.test(line)) throw new CubeParseError(`unsupported keyword: ${line.split(/\s+/)[0]}`);
    const parts = line.split(/\s+/).map(Number);
    if (parts.length !== 3 || parts.some((v) => !Number.isFinite(v))) throw new CubeParseError('bad data row');
    values.push(...parts);
  }
  if (!Number.isInteger(size) || size < 2 || size > 64) throw new CubeParseError('LUT_3D_SIZE must be 2..64');
  if (values.length !== size * size * size * 3) throw new CubeParseError('row count does not match LUT_3D_SIZE');
  return { size, data: Float32Array.from(values) };
}

export function buildAtlas(cube: Cube): Uint8Array {
  const { size, data } = cube;
  const width = size * size;
  const out = new Uint8Array(width * size * 4);
  for (let b = 0; b < size; b++) {
    for (let g = 0; g < size; g++) {
      for (let r = 0; r < size; r++) {
        const src = ((b * size + g) * size + r) * 3;
        const dst = (g * width + (r + b * size)) * 4;
        for (let c = 0; c < 3; c++) {
          out[dst + c] = Math.round(Math.min(1, Math.max(0, data[src + c] ?? 0)) * 255);
        }
        out[dst + 3] = 255;
      }
    }
  }
  return out;
}

// CPU reference of the shader's trilinear lookup, used by tests.
export function sampleAtlas(atlas: Uint8Array, size: number, rgb: readonly [number, number, number]): [number, number, number] {
  const width = size * size;
  const p = rgb.map((v) => Math.min(1, Math.max(0, v)) * (size - 1)) as [number, number, number];
  const lo = p.map(Math.floor) as [number, number, number];
  const hi = lo.map((v) => Math.min(v + 1, size - 1)) as [number, number, number];
  const f = [p[0] - lo[0], p[1] - lo[1], p[2] - lo[2]] as const;
  const texel = (r: number, g: number, b: number, c: number) => (atlas[(g * width + r + b * size) * 4 + c] ?? 0) / 255;
  const out: [number, number, number] = [0, 0, 0];
  for (let c = 0; c < 3; c++) {
    const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
    const c00 = lerp(texel(lo[0], lo[1], lo[2], c), texel(hi[0], lo[1], lo[2], c), f[0]);
    const c10 = lerp(texel(lo[0], hi[1], lo[2], c), texel(hi[0], hi[1], lo[2], c), f[0]);
    const c01 = lerp(texel(lo[0], lo[1], hi[2], c), texel(hi[0], lo[1], hi[2], c), f[0]);
    const c11 = lerp(texel(lo[0], hi[1], hi[2], c), texel(hi[0], hi[1], hi[2], c), f[0]);
    out[c] = lerp(lerp(c00, c10, f[1]), lerp(c01, c11, f[1]), f[2]);
  }
  return out;
}

export function decodeBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
