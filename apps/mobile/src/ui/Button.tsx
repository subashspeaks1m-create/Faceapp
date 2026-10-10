import { Pressable, StyleSheet, Text, type StyleProp, type ViewStyle } from 'react-native';
import { colors, radii, space, touchMin, type } from './theme';

interface Props {
  readonly label: string;
  readonly onPress: () => void;
  readonly variant?: 'primary' | 'secondary' | 'quiet';
  readonly disabled?: boolean;
  readonly selected?: boolean;
  readonly hint?: string;
  readonly style?: StyleProp<ViewStyle>;
}

export function Button({ label, onPress, variant = 'secondary', disabled = false, selected, hint, style }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={hint}
      accessibilityState={{ disabled, selected }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.base,
        variant === 'primary' && styles.primary,
        variant === 'quiet' && styles.quiet,
        selected === true && styles.selected,
        pressed && styles.pressed,
        disabled && styles.disabled,
        style,
      ]}
    >
      <Text style={[styles.label, variant === 'primary' && styles.primaryLabel, selected === true && styles.selectedLabel]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: touchMin,
    minWidth: touchMin,
    paddingHorizontal: space(3),
    borderRadius: radii.control,
    backgroundColor: colors.raised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primary: { backgroundColor: colors.accent },
  quiet: { backgroundColor: 'transparent' },
  selected: { backgroundColor: colors.accent },
  pressed: { opacity: 0.8 },
  disabled: { opacity: 0.4 },
  label: { ...type('label'), color: colors.text },
  primaryLabel: { color: colors.on_accent },
  selectedLabel: { color: colors.on_accent },
});
