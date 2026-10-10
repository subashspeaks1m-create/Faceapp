import { useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { NormalizeError, normalizeSource } from '../src/media/normalize';
import { captureWithCamera, type PickOutcome, pickFromLibrary } from '../src/media/pick';
import { useSession } from '../src/session';
import { Button } from '../src/ui/Button';
import { colors, radii, space, type } from '../src/ui/theme';

type Status =
  | { readonly kind: 'idle' }
  | { readonly kind: 'opening' }
  | { readonly kind: 'error'; readonly message: string; readonly settings: boolean };

export default function Home() {
  const router = useRouter();
  const { privacyAcknowledged, acknowledgePrivacy, setSource } = useSession();
  const [status, setStatus] = useState<Status>({ kind: 'idle' });

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
          setSource(await normalizeSource(result.uri));
          setStatus({ kind: 'idle' });
          router.push('/editor');
        } catch (e) {
          setStatus({ kind: 'error', message: e instanceof NormalizeError ? e.message : 'This photo could not be opened.', settings: false });
        }
    }
  }

  if (!privacyAcknowledged) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Text accessibilityRole="header" style={styles.h1}>Before you start</Text>
        <View style={styles.card}>
          <Text style={styles.body}>
            Adjustments, looks and crops run on this device. Your photo is not uploaded to edit it, and your original file is never changed.
          </Text>
          <Text style={styles.body}>
            AI portrait effects are not available yet. When they are, they will need a copy of your photo to be processed on our servers, and we will ask for your permission separately each time.
          </Text>
        </View>
        <Button label="Continue" variant="primary" onPress={acknowledgePrivacy} />
      </ScrollView>
    );
  }

  const busy = status.kind === 'opening';
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text accessibilityRole="header" style={styles.h1}>Edit a portrait</Text>
      <Text style={styles.muted}>Pick a photo from your library or take a new one.</Text>
      <Button label="Choose photo" variant="primary" disabled={busy} onPress={() => void open(pickFromLibrary)} />
      <Button label="Take photo" disabled={busy} onPress={() => void open(captureWithCamera)} />
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
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space(4), gap: space(3) },
  h1: { ...type('h1'), color: colors.text },
  body: { ...type('body'), color: colors.text },
  muted: { ...type('body'), color: colors.muted },
  error: { ...type('body'), color: colors.error },
  card: { backgroundColor: colors.surface, borderRadius: radii.sheet, padding: space(4), gap: space(3) },
  row: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
});
