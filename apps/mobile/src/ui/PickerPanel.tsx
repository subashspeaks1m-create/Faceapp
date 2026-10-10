import { ActivityIndicator, Linking, StyleSheet, Text, View } from 'react-native';
import type { PickerStatus } from '../media/usePhotoPicker';
import { Button } from './Button';
import { colors, radii, space, type } from './theme';

interface Props {
  readonly status: PickerStatus;
  readonly busy: boolean;
  readonly onChoose: () => void;
  readonly onTake: () => void;
  readonly chooseLabel?: string;
}

export function PickerPanel({ status, busy, onChoose, onTake, chooseLabel = 'Choose photo' }: Props) {
  return (
    <View style={styles.wrap}>
      <Button label={chooseLabel} variant="primary" disabled={busy} onPress={onChoose} />
      <Button label="Take photo" disabled={busy} onPress={onTake} />
      {busy && (
        <View style={styles.row} accessibilityLiveRegion="polite">
          <ActivityIndicator color={colors.accent} />
          <Text style={styles.muted}>Opening photo…</Text>
        </View>
      )}
      {status.kind === 'error' && (
        <View style={styles.card} accessibilityLiveRegion="assertive">
          <Text style={styles.error}>{status.message}</Text>
          {status.settings && <Button label="Open Settings" onPress={() => void Linking.openSettings()} />}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space(3) },
  muted: { ...type('body'), color: colors.muted },
  error: { ...type('body'), color: colors.error },
  card: { backgroundColor: colors.surface, borderRadius: radii.sheet, padding: space(4), gap: space(3) },
  row: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
});
