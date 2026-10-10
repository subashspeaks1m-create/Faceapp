// Loads React Native Skia's JS API on top of CanvasKit (WASM) so the device
// render path can be exercised in Node.
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import type { Skia as SkiaApi } from '@shopify/react-native-skia';

const require = createRequire(import.meta.url);

export async function loadSkia(): Promise<typeof SkiaApi> {
  const ckDir = dirname(require.resolve('canvaskit-wasm/bin/full/canvaskit.js'));
  const init = require('canvaskit-wasm/bin/full/canvaskit.js') as (o: { locateFile: (f: string) => string }) => Promise<unknown>;
  const CanvasKit = await init({ locateFile: (f) => join(ckDir, f) });
  const { JsiSkApi } = require('@shopify/react-native-skia/lib/commonjs/skia/web/JsiSkia.js') as {
    JsiSkApi: (ck: unknown) => typeof SkiaApi;
  };
  return JsiSkApi(CanvasKit);
}

export function skiaEnums(): Record<string, Record<string, number>> {
  const t = require('@shopify/react-native-skia/lib/commonjs/skia/types/index.js') as Record<string, Record<string, number>>;
  return t;
}
