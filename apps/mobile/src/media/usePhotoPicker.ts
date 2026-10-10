import { useState } from 'react';
import { NormalizeError, normalizeSource, type SourceImage } from './normalize';
import { captureWithCamera, type PickOutcome, pickFromLibrary } from './pick';

export type PickerStatus =
  | { readonly kind: 'idle' }
  | { readonly kind: 'opening' }
  | { readonly kind: 'error'; readonly message: string; readonly settings: boolean };

// Shared photo-picking flow: system picker or camera, then normalization into an immutable source.
export function usePhotoPicker(onPicked: (source: SourceImage) => void) {
  const [status, setStatus] = useState<PickerStatus>({ kind: 'idle' });

  async function open(pick: () => Promise<PickOutcome>) {
    setStatus({ kind: 'opening' });
    const result = await pick();
    switch (result.kind) {
      case 'canceled':
        setStatus({ kind: 'idle' });
        return;
      case 'permission-denied':
        setStatus({
          kind: 'error',
          message: result.canAskAgain
            ? 'Camera access is needed to take a photo.'
            : 'Camera access is off for PortraitLab. You can turn it on in Settings, or choose a photo instead.',
          settings: !result.canAskAgain,
        });
        return;
      case 'failed':
        setStatus({ kind: 'error', message: `The ${result.source === 'camera' ? 'camera' : 'photo picker'} could not be opened.`, settings: false });
        return;
      case 'picked':
        try {
          const source = await normalizeSource(result.uri);
          setStatus({ kind: 'idle' });
          onPicked(source);
        } catch (e) {
          setStatus({ kind: 'error', message: e instanceof NormalizeError ? e.message : 'This photo could not be opened.', settings: false });
        }
    }
  }

  return {
    status,
    busy: status.kind === 'opening',
    chooseFromLibrary: () => void open(pickFromLibrary),
    takePhoto: () => void open(captureWithCamera),
  };
}
