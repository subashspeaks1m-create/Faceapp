import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Button } from './Button';
import { colors, radii, space, type } from './theme';

interface Props {
  readonly visible: boolean;
  readonly onAccept: () => void;
  readonly onCancel: () => void;
  readonly onReadMore: () => void;
}

const CHECKS = [
  { id: 'send', text: 'I agree to send this photo to the PortraitLab style service and its AI provider (OpenAI) to create the styled image.' },
  { id: 'rights', text: 'The photo is of me, or I have permission from everyone in it.' },
  { id: 'adult', text: 'I am 18 or older, and the photo does not show children.' },
] as const;

function Check({ checked, label, onToggle }: { readonly checked: boolean; readonly label: string; readonly onToggle: () => void }) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      accessibilityLabel={label}
      onPress={onToggle}
      style={styles.check}
    >
      <View style={[styles.box, checked && styles.boxOn]}>{checked && <Text style={styles.tick}>✓</Text>}</View>
      <Text style={styles.body}>{label}</Text>
    </Pressable>
  );
}

// Explicit opt-in before the first upload. Nothing is sent until every box is ticked and Agree is tapped.
export function ConsentSheet({ visible, onAccept, onCancel, onReadMore }: Props) {
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const all = CHECKS.every((c) => checked[c.id] === true);
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <View style={styles.sheet} accessibilityViewIsModal>
          <ScrollView contentContainerStyle={styles.content}>
            <Text accessibilityRole="header" style={styles.h2}>Send your photo for AI styling?</Text>
            <Text style={styles.muted}>
              To create a style, a copy of your photo is uploaded over an encrypted connection and processed by OpenAI. PortraitLab does not keep your photo or the result after sending it back to you. OpenAI may keep request data for up to 30 days to monitor abuse. AI results are artistic interpretations and can change details.
            </Text>
            {CHECKS.map((c) => (
              <Check key={c.id} label={c.text} checked={checked[c.id] === true} onToggle={() => setChecked((p) => ({ ...p, [c.id]: !(p[c.id] === true) }))} />
            ))}
            <Pressable accessibilityRole="link" onPress={onReadMore} hitSlop={8}>
              <Text style={styles.link}>Read the full privacy details</Text>
            </Pressable>
            <Button label="Agree and continue" variant="primary" disabled={!all} onPress={onAccept} hint={all ? undefined : 'Tick all three boxes first'} />
            <Button label="Not now" variant="quiet" onPress={onCancel} />
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: colors.surface, borderTopLeftRadius: radii.sheet, borderTopRightRadius: radii.sheet, maxHeight: '92%', width: '100%', maxWidth: 720, alignSelf: 'center' },
  content: { padding: space(4), gap: space(3) },
  h2: { ...type('h2'), color: colors.text },
  body: { ...type('body'), color: colors.text, flex: 1 },
  muted: { ...type('body'), color: colors.muted },
  link: { ...type('label'), color: colors.accent, textDecorationLine: 'underline' },
  check: { flexDirection: 'row', gap: space(3), alignItems: 'flex-start', minHeight: 44 },
  box: { width: 26, height: 26, borderRadius: radii.small, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  boxOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  tick: { color: colors.on_accent, fontWeight: '700' },
});
