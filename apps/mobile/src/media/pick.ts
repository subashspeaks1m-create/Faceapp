import * as ImagePicker from 'expo-image-picker';

export type PickSource = 'library' | 'camera';

export type PickOutcome =
  | { readonly kind: 'picked'; readonly uri: string }
  | { readonly kind: 'canceled' }
  | { readonly kind: 'permission-denied'; readonly source: PickSource; readonly canAskAgain: boolean }
  | { readonly kind: 'failed'; readonly source: PickSource };

const OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  allowsEditing: false,
  quality: 1,
  exif: false,
  base64: false,
};

function outcome(result: ImagePicker.ImagePickerResult): PickOutcome {
  const asset = result.canceled ? undefined : result.assets[0];
  return asset ? { kind: 'picked', uri: asset.uri } : { kind: 'canceled' };
}

// The system photo picker (PHPicker / Android Photo Picker) needs no library permission.
export async function pickFromLibrary(): Promise<PickOutcome> {
  try {
    return outcome(await ImagePicker.launchImageLibraryAsync(OPTIONS));
  } catch {
    return { kind: 'failed', source: 'library' };
  }
}

export async function captureWithCamera(): Promise<PickOutcome> {
  try {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) return { kind: 'permission-denied', source: 'camera', canAskAgain: permission.canAskAgain };
    return outcome(await ImagePicker.launchCameraAsync({ ...OPTIONS, cameraType: ImagePicker.CameraType.back }));
  } catch {
    return { kind: 'failed', source: 'camera' };
  }
}
