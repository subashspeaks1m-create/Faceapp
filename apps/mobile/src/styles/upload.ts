// Native: downscale the normalized source to the size the service uses and attach it as a file.
// The upload goes through expo/fetch, whose FormData accepts expo-file-system File objects.

import { fetch as expoFetch } from 'expo/fetch';
import { File } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import type { FetchLike } from './client.ts';
import { uploadSize } from './uploadSize.ts';

export const styleFetch = expoFetch as unknown as FetchLike;

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
    return new File(saved.uri);
  } finally {
    context.release();
  }
}
