import { Image, StyleSheet, Text, View } from 'react-native';
import type { SourceImage } from '../media/normalize';
import { usePhotoPicker } from '../media/usePhotoPicker';
import { Button } from './Button';
import { PickerPanel } from './PickerPanel';
import { colors, radii, space, type } from './theme';

// Shows the chosen photo with a "Change" action, or the pickers when there is none.
export function SourceStrip({ source, onPicked }: { readonly source: SourceImage | null; readonly onPicked: (s: SourceImage) => void }) {
  const picker = usePhotoPicker(onPicked);
  if (source === null) {
    return (
      <View style={styles.card}>
        <Text style={styles.body}>Add a photo to style. A clear, well-lit photo of one face works best.</Text>
        <PickerPanel status={picker.status} busy={picker.busy} onChoose={picker.chooseFromLibrary} onTake={picker.takePhoto} />
      </View>
    );
  }
  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Image source={{ uri: source.uri }} style={styles.thumb} accessibilityLabel="Your chosen photo" resizeMode="cover" />
        <View style={styles.grow}>
          <Text style={styles.body}>Your photo</Text>
          <Text style={styles.muted}>{source.width} × {source.height}</Text>
        </View>
        <Button label="Change" onPress={picker.chooseFromLibrary} disabled={picker.busy} hint="Choose a different photo" />
      </View>
      {picker.status.kind === 'error' && <Text style={styles.error} accessibilityLiveRegion="assertive">{picker.status.message}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderRadius: radii.sheet, padding: space(3), gap: space(3) },
  row: { flexDirection: 'row', alignItems: 'center', gap: space(3) },
  grow: { flex: 1 },
  thumb: { width: 56, height: 56, borderRadius: radii.control, backgroundColor: colors.raised },
  body: { ...type('body'), color: colors.text },
  muted: { ...type('caption'), color: colors.muted },
  error: { ...type('body'), color: colors.error },
});
