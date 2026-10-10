import { useRef, useState } from 'react';
import { Image, type LayoutChangeEvent, PanResponder, StyleSheet, Text, View } from 'react-native';
import { colors, radii, space, type } from './theme';

interface Props {
  readonly beforeUri: string;
  readonly afterUri: string;
  readonly aspect: number; // width / height of the frame
}

// Before/After with a draggable divider. Screen readers get an adjustable control
// (swipe up/down to move the divider) and the separate Show original toggle on the result screen.
export function CompareView({ beforeUri, afterUri, aspect }: Props) {
  const [width, setWidth] = useState(0);
  const [split, setSplit] = useState(0.5);
  const widthRef = useRef(0);

  const responder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e) => setSplit(clamp(e.nativeEvent.locationX / Math.max(1, widthRef.current))),
      onPanResponderMove: (e) => setSplit(clamp(e.nativeEvent.locationX / Math.max(1, widthRef.current))),
      onPanResponderTerminationRequest: () => false,
    }),
  ).current;

  function onLayout(e: LayoutChangeEvent) {
    widthRef.current = e.nativeEvent.layout.width;
    setWidth(e.nativeEvent.layout.width);
  }

  const pct = Math.round(split * 100);
  return (
    <View
      style={[styles.frame, { aspectRatio: aspect }]}
      onLayout={onLayout}
      accessible
      accessibilityRole="adjustable"
      accessibilityLabel="Before and after comparison"
      accessibilityValue={{ min: 0, max: 100, now: pct, text: `${pct}% original shown` }}
      accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
      onAccessibilityAction={(e) => setSplit((s) => clamp(s + (e.nativeEvent.actionName === 'increment' ? 0.1 : -0.1)))}
      testID="compare"
      {...responder.panHandlers}
    >
      <View pointerEvents="none" style={StyleSheet.absoluteFill}>
        <Image source={{ uri: afterUri }} style={StyleSheet.absoluteFill} resizeMode="cover" accessibilityIgnoresInvertColors />
      </View>
      <View pointerEvents="none" style={[styles.clip, { width: width * split }]}>
        <Image source={{ uri: beforeUri }} style={{ width, height: '100%' }} resizeMode="cover" />
      </View>
      <View pointerEvents="none" style={[styles.divider, { left: width * split - 1 }]}>
        <View style={styles.handle} />
      </View>
      <Text pointerEvents="none" style={[styles.tag, styles.tagLeft]}>Before</Text>
      <Text pointerEvents="none" style={[styles.tag, styles.tagRight]}>After</Text>
    </View>
  );
}

function clamp(v: number): number {
  return Math.max(0, Math.min(1, v));
}

const styles = StyleSheet.create({
  frame: { width: '100%', borderRadius: radii.sheet, overflow: 'hidden', backgroundColor: colors.raised },
  clip: { position: 'absolute', left: 0, top: 0, bottom: 0, overflow: 'hidden' },
  divider: { position: 'absolute', top: 0, bottom: 0, width: 2, backgroundColor: colors.text, alignItems: 'center', justifyContent: 'center' },
  handle: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.text, borderWidth: 3, borderColor: colors.background },
  tag: { position: 'absolute', top: space(2), ...type('caption'), color: colors.text, backgroundColor: 'rgba(0,0,0,0.55)', paddingHorizontal: space(2), paddingVertical: 2, borderRadius: radii.small, overflow: 'hidden' },
  tagLeft: { left: space(2) },
  tagRight: { right: space(2) },
});
