import { decodeBase64 } from './cube.ts';
import { LUT_ATLAS_BASE64 } from './luts.generated.ts';
import type { LookId } from './model.ts';
import type { LutAtlas } from './render.ts';

export function loadLutAtlases(): Record<LookId, LutAtlas> {
  const out = {} as Record<LookId, LutAtlas>;
  for (const [id, { size, base64 }] of Object.entries(LUT_ATLAS_BASE64) as [LookId, { size: number; base64: string }][]) {
    out[id] = { size, pixels: decodeBase64(base64) };
  }
  return out;
}
