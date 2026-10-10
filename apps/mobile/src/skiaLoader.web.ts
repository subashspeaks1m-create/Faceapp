import { LoadSkiaWeb } from '@shopify/react-native-skia/lib/module/web';

// The web build loads Skia's CanvasKit WASM, served next to index.html.
export function loadSkia(): Promise<void> {
  return LoadSkiaWeb({ locateFile: (file: string) => new URL(file, document.baseURI).href });
}
