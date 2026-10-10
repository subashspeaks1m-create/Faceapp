// Copies Skia's CanvasKit WASM into public/ so the web build serves it next to index.html.
import { copyFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const src = join(dirname(require.resolve('canvaskit-wasm/bin/full/canvaskit.js')), 'canvaskit.wasm');
mkdirSync(join(here, '../public'), { recursive: true });
copyFileSync(src, join(here, '../public/canvaskit.wasm'));
console.log('copied canvaskit.wasm to public/');
