import { StyleSheet, View } from 'react-native';

// A palette chip for a style. It is decoration, not a sample result, so it is hidden from screen readers.
export function StyleSwatch({ swatch, size }: { readonly swatch: readonly [string, string, string]; readonly size: number }) {
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.base, { width: size, height: size, borderRadius: size * 0.22, backgroundColor: swatch[2] }]}
    >
      <View style={[styles.dot, { width: size * 0.62, height: size * 0.62, borderRadius: size, backgroundColor: swatch[0], left: size * 0.08, top: size * 0.1 }]} />
      <View style={[styles.dot, { width: size * 0.46, height: size * 0.46, borderRadius: size, backgroundColor: swatch[1], right: size * 0.08, bottom: size * 0.08 }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  base: { overflow: 'hidden' },
  dot: { position: 'absolute', opacity: 0.95 },
});
