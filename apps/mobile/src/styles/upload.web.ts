// Web: same downscale through expo-image-manipulator (canvas), then attach a Blob.

import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import type { FetchLike } from './client.ts';
import { uploadSize } from './uploadSize.ts';

export const styleFetch: FetchLike = (url, init) => globalThis.fetch(url, init as RequestInit);

export function newForm(): FormData {
  return new FormData();
}

export async function prepareImagePart(uri: string, width: number, height: number): Promise<unknown> {
  const context = ImageManipulator.manipulate(uri);
  try {
    const target = uploadSize(width, height);
    if (target.width !== width || target.height !== height) context.resize(target);
    const ref = await context.renderAsync();
    const saved = await ref.saveAsync({ format: SaveFormat.JPEG, compress: 0.9 });
    const blob = await (await globalThis.fetch(saved.uri)).blob();
    return new globalThis.File([blob], 'photo.jpg', { type: 'image/jpeg' });
  } finally {
    context.release();
  }
}
