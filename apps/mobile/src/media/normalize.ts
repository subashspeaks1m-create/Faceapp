// Decodes the picked file once, applies orientation, and re-encodes it as a
// metadata-free PNG that becomes the immutable editing source.

import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { fitWithinPixels } from './fit.ts';

export const MAX_SOURCE_PIXELS = 24_000_000;

export interface SourceImage {
  readonly uri: string;
  readonly width: number;
  readonly height: number;
  /** Set when the original exceeded MAX_SOURCE_PIXELS and was downscaled. */
  readonly resizedFrom: { readonly width: number; readonly height: number } | null;
}

export class NormalizeError extends Error {
  override readonly name = 'NormalizeError';
}

export async function normalizeSource(uri: string): Promise<SourceImage> {
  const context = ImageManipulator.manipulate(uri);
  try {
    const decoded = await context.renderAsync();
    const original = { width: decoded.width, height: decoded.height };
    if (!(original.width > 0 && original.height > 0)) throw new NormalizeError('image has no pixels');
    const target = fitWithinPixels(original.width, original.height, MAX_SOURCE_PIXELS);
    let ref = decoded;
    if (target.width !== original.width || target.height !== original.height) {
      context.resize(target);
      ref = await context.renderAsync();
    }
    const saved = await ref.saveAsync({ format: SaveFormat.PNG });
    return {
      uri: saved.uri,
      width: saved.width,
      height: saved.height,
      resizedFrom: ref === decoded ? null : original,
    };
  } catch (e) {
    if (e instanceof NormalizeError) throw e;
    throw new NormalizeError('This photo could not be opened.');
  } finally {
    context.release();
  }
}
