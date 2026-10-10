import Slider from '@react-native-community/slider';
import { StyleSheet, Text, View } from 'react-native';
import { colors, space, type } from './theme';

interface Props {
  readonly label: string;
  readonly value: number;
  readonly min: number;
  readonly max: number;
  readonly onChange: (value: number) => void;
}

// Shows the value as a signed percentage so every slider is labelled numerically.
// The control itself runs from 0 to (max - min): the web slider mishandles negative minimums.
export function formatValue(value: number, min: number): string {
  const pct = Math.round(value * 100);
  return min < 0 && pct > 0 ? `+${pct}` : `${pct}`;
}

export function LabeledSlider({ label, value, min, max, onChange }: Props) {
  const text = formatValue(value, min);
  return (
    <View style={styles.row}>
      <View style={styles.header}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.value}>{text}</Text>
      </View>
      <Slider
        accessibilityLabel={label}
        accessibilityValue={{ min: Math.round(min * 100), max: Math.round(max * 100), now: Math.round(value * 100), text }}
        minimumValue={0}
        maximumValue={max - min}
        step={0.01}
        value={value - min}
        onValueChange={(v) => onChange(Math.round((v + min) * 100) / 100)}
        minimumTrackTintColor={colors.accent}
        maximumTrackTintColor={colors.border}
        thumbTintColor={colors.text}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { paddingVertical: space(1) },
  header: { flexDirection: 'row', justifyContent: 'space-between' },
  label: { ...type('label'), color: colors.text },
  value: { ...type('label'), color: colors.muted, fontVariant: ['tabular-nums'] },
});
