import { Stack, useRouter } from 'expo-router';
import { useState } from 'react';
import { Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import { canDownload, downloadExport, ExportError, shareExport } from '../src/media/exportImage';
import { useSession } from '../src/session';
import { bandFor, styleById } from '../src/styles/catalog';
import { outputAspect } from '../src/styles/uploadSize';
import { Button } from '../src/ui/Button';
import { CompareView } from '../src/ui/CompareView';
import { QuotaBadge } from '../src/ui/QuotaBadge';
import { colors, radii, space, type } from '../src/ui/theme';

type View_ = 'compare' | 'result' | 'original';

export default function Result() {
  const router = useRouter();
  const { result, setResult, setSource, quota } = useSession();
  const [mode, setMode] = useState<View_>('compare');
  const [message, setMessage] = useState<string | null>(null);

  if (result === null) {
    return (
      <View style={styles.page}>
        <Text style={styles.body}>There is no result to show. Pick a style to create one.</Text>
        <Button label="Browse styles" variant="primary" onPress={() => router.replace('/styles')} />
      </View>
    );
  }
  const style = styleById(result.styleId);
  const name = style?.name ?? result.styleId;
  const aspect = outputAspect(result.source.width, result.source.height);

  async function share(kind: 'share' | 'download') {
    if (result === null) return;
    setMessage(null);
    try {
      // The handle comes from writeExport on this platform.
      await (kind === 'download' ? downloadExport : shareExport)(result.file as never);
    } catch (e) {
      setMessage(e instanceof ExportError ? e.message : 'The image could not be saved.');
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: name }} />
      <Text accessibilityRole="header" style={styles.h1}>{name}</Text>
      <Text style={styles.muted}>Strength {result.intensity} ({bandFor(result.intensity).label}). AI-generated: details can differ from your photo.</Text>

      {mode === 'compare' ? (
        <CompareView beforeUri={result.source.uri} afterUri={result.uri} aspect={aspect} />
      ) : (
        <View style={[styles.frame, { aspectRatio: aspect }]}>
          <Image
            source={{ uri: mode === 'result' ? result.uri : result.source.uri }}
            style={StyleSheet.absoluteFill}
            resizeMode="cover"
            accessibilityLabel={mode === 'result' ? `Your photo in the ${name} style` : 'Your original photo'}
            testID={mode === 'result' ? 'result-image' : 'original-image'}
          />
        </View>
      )}
      <View style={styles.row} accessibilityRole="radiogroup">
        <Button label="Compare" selected={mode === 'compare'} onPress={() => setMode('compare')} />
        <Button label="Result" selected={mode === 'result'} onPress={() => setMode('result')} />
        <Button label="Original" selected={mode === 'original'} onPress={() => setMode('original')} />
      </View>

      <View style={styles.row}>
        {canDownload && <Button label="Download" variant="primary" onPress={() => void share('download')} />}
        <Button label={canDownload ? 'Share' : 'Save or share'} variant={canDownload ? 'secondary' : 'primary'} onPress={() => void share('share')} />
      </View>
      {message !== null && <Text style={styles.error} accessibilityLiveRegion="assertive">{message}</Text>}

      <View style={styles.row}>
        <Button label="Adjust and regenerate" onPress={() => router.back()} />
        <Button label="Change style" onPress={() => router.navigate('/styles')} />
        <Button
          label="Start over"
          variant="quiet"
          onPress={() => {
            setResult(null);
            setSource(null);
            router.dismissAll();
          }}
        />
      </View>
      <QuotaBadge quota={quota} />
      <Text style={styles.caption}>This result is only on this device. PortraitLab does not keep a copy; save it if you want it.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space(4), gap: space(3), maxWidth: 720, width: '100%', alignSelf: 'center' },
  h1: { ...type('h1'), color: colors.text },
  body: { ...type('body'), color: colors.text },
  muted: { ...type('body'), color: colors.muted },
  caption: { ...type('caption'), color: colors.muted },
  error: { ...type('body'), color: colors.error },
  frame: { width: '100%', borderRadius: radii.sheet, overflow: 'hidden', backgroundColor: colors.raised },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2) },
});
