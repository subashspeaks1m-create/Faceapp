import { Directory, File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';

const EXPORT_DIR = 'exports';

export class ExportError extends Error {
  override readonly name = 'ExportError';
}

function exportDir(): Directory {
  const dir = new Directory(Paths.cache, EXPORT_DIR);
  if (!dir.exists) dir.create({ intermediates: true });
  return dir;
}

// Writes a new export and removes earlier ones so edited portraits do not pile up in cache.
export function writeExport(jpeg: Uint8Array): File {
  const dir = exportDir();
  for (const entry of dir.list()) entry.delete();
  const file = new File(dir, `portraitlab-${Date.now()}.jpg`);
  file.create();
  file.write(jpeg);
  return file;
}

export async function shareExport(file: File): Promise<void> {
  if (!(await Sharing.isAvailableAsync())) throw new ExportError('Sharing is not available on this device.');
  await Sharing.shareAsync(file.uri, { mimeType: 'image/jpeg', UTI: 'public.jpeg', dialogTitle: 'Save or share your photo' });
}

// Native has no separate download: the share sheet offers "Save image".
export const downloadExport = shareExport;
export const canDownload = false;
