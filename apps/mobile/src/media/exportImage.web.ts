// Web: hand the JPEG to the system share sheet when the browser supports file
// sharing (most phones), otherwise download it.

export class ExportError extends Error {
  override readonly name = 'ExportError';
}

export interface ExportedFile {
  readonly uri: string;
  readonly blob: Blob;
  readonly name: string;
}

let previousUrl: string | null = null;

export function writeExport(jpeg: Uint8Array): ExportedFile {
  if (previousUrl !== null) URL.revokeObjectURL(previousUrl);
  const blob = new Blob([jpeg.slice().buffer], { type: 'image/jpeg' });
  previousUrl = URL.createObjectURL(blob);
  return { uri: previousUrl, blob, name: `portraitlab-${Date.now()}.jpg` };
}

export async function shareExport(file: ExportedFile): Promise<void> {
  const shareable = new File([file.blob], file.name, { type: 'image/jpeg' });
  if (typeof navigator.canShare === 'function' && navigator.canShare({ files: [shareable] })) {
    try {
      await navigator.share({ files: [shareable] });
      return;
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      // Fall through to a download if sharing is refused.
    }
  }
  const link = document.createElement('a');
  link.href = file.uri;
  link.download = file.name;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export async function downloadExport(file: ExportedFile): Promise<void> {
  const link = document.createElement('a');
  link.href = file.uri;
  link.download = file.name;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export const canDownload = true;
