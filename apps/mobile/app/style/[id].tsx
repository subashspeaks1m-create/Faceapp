import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { writeExport } from '../../src/media/exportImage';
import { useSession } from '../../src/session';
import { bandFor, categoryName, styleById } from '../../src/styles/catalog';
import { clientError, errorAdvice, fetchHealth, generate, isStyleError, type StyleError } from '../../src/styles/client';
import { STYLE_API_URL } from '../../src/styles/config';
import { newForm, prepareImagePart, styleFetch } from '../../src/styles/upload';
import { Button } from '../../src/ui/Button';
import { ConsentSheet } from '../../src/ui/ConsentSheet';
import { LabeledSlider } from '../../src/ui/LabeledSlider';
import { QuotaBadge } from '../../src/ui/QuotaBadge';
import { SourceStrip } from '../../src/ui/SourceStrip';
import { StyleSwatch } from '../../src/ui/StyleSwatch';
import { colors, radii, space, type } from '../../src/ui/theme';

type Phase =
  | { readonly kind: 'idle' }
  | { readonly kind: 'uploading' }
  | { readonly kind: 'generating'; readonly startedAt: number }
  | { readonly kind: 'error'; readonly error: StyleError };

function useElapsed(startedAt: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (startedAt === null) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [startedAt]);
  return startedAt === null ? 0 : Math.max(0, Math.floor((now - startedAt) / 1000));
}

export default function StyleDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const style = typeof id === 'string' ? styleById(id) : undefined;
  const { source, setSource, aiConsentProvider, grantAiConsent, setResult, quota, setQuota } = useSession();
  const [intensity, setIntensity] = useState(style?.default_intensity ?? 60);
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' });
  const [consentOpen, setConsentOpen] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const elapsed = useElapsed(phase.kind === 'generating' ? phase.startedAt : null);

  const [provider, setProvider] = useState<string | null>(null);

  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    if (STYLE_API_URL === null) return;
    const ctrl = new AbortController();
    void fetchHealth(STYLE_API_URL, styleFetch, ctrl.signal).then((h) => {
      if (!isStyleError(h)) setProvider(h.provider);
    });
    return () => ctrl.abort();
  }, []);

  if (style === undefined) {
    return (
      <View style={styles.page}>
        <Stack.Screen options={{ title: 'Style not found' }} />
        <Text style={styles.body}>This style is not available.</Text>
        <Button label="Back to styles" onPress={() => router.replace('/styles')} />
      </View>
    );
  }
  const current = style;
  const band = bandFor(intensity);
  const busy = phase.kind === 'uploading' || phase.kind === 'generating';

  async function run() {
    if (source === null) return;
    const ctrl = new AbortController();
    abort.current = ctrl;
    setPhase({ kind: 'uploading' });
    let imagePart: unknown;
    try {
      imagePart = await prepareImagePart(source.uri, source.width, source.height);
    } catch {
      setPhase({ kind: 'error', error: { ...clientError('INTERNAL_ERROR', false), code: 'INVALID_IMAGE', message: 'This photo could not be prepared for upload. Try a different photo.' } });
      return;
    }
    if (ctrl.signal.aborted) return;
    setPhase({ kind: 'generating', startedAt: Date.now() });
    const outcome = await generate({
      baseUrl: STYLE_API_URL,
      fetch: styleFetch,
      form: newForm(),
      imagePart,
      styleId: current.id,
      intensity,
      signal: ctrl.signal,
    });
    abort.current = null;
    if (outcome.kind === 'error') {
      setPhase({ kind: 'error', error: outcome.error });
      return;
    }
    if (outcome.quota !== null) setQuota(outcome.quota);
    const file = writeExport(outcome.jpeg);
    setResult({ uri: file.uri, file, styleId: current.id, intensity, source, requestId: outcome.requestId });
    setPhase({ kind: 'idle' });
    router.push('/result');
  }

  async function onGenerate() {
    // Consent names the provider, so it is asked again if the server switches providers.
    let current = provider;
    if (current === null && STYLE_API_URL !== null) {
      const h = await fetchHealth(STYLE_API_URL, styleFetch);
      if (isStyleError(h)) {
        setPhase({ kind: 'error', error: h });
        return;
      }
      if (!h.providerConfigured || h.provider === null) {
        setPhase({ kind: 'error', error: { ...clientError('INTERNAL_ERROR', false), code: 'PROVIDER_NOT_CONFIGURED', message: 'AI styles are not set up on this server yet.' } });
        return;
      }
      current = h.provider;
      setProvider(current);
    }
    if (current === null || aiConsentProvider !== current) {
      setConsentOpen(true);
      return;
    }
    void run();
  }

  function cancel() {
    abort.current?.abort();
    abort.current = null;
    setPhase({ kind: 'error', error: clientError('CANCELED') });
  }

  const advice = phase.kind === 'error' ? errorAdvice(phase.error) : null;
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Stack.Screen options={{ title: current.name }} />
      <View style={styles.hero}>
        <StyleSwatch swatch={current.swatch} size={96} />
        <View style={styles.grow}>
          <Text accessibilityRole="header" style={styles.h1}>{current.name}</Text>
          <Text style={styles.muted}>{categoryName(current.category)}</Text>
        </View>
      </View>
      <Text style={styles.body}>{current.summary}</Text>
      <Text style={styles.caption}>{current.tags.join(' · ')}</Text>

      <SourceStrip source={source} onPicked={(s) => { setSource(s); setPhase({ kind: 'idle' }); }} />

      <View style={styles.card}>
        <LabeledSlider label="Strength" value={intensity / 100} min={0} max={1} onChange={(v) => setIntensity(Math.round(v * 100))} />
        <Text style={styles.muted} accessibilityLiveRegion="polite">{band.label}: {bandHint(band.label)}</Text>
      </View>

      {phase.kind === 'uploading' || phase.kind === 'generating' ? (
        <View style={styles.card} accessibilityLiveRegion="polite" testID="progress">
          <View style={styles.row}>
            <ActivityIndicator color={colors.accent} />
            <Text style={styles.body}>
              {phase.kind === 'uploading' ? 'Preparing your photo…' : `Creating your ${current.name} image… ${elapsed}s`}
            </Text>
          </View>
          <Text style={styles.muted}>This can take a minute or two. Keep this screen open.</Text>
          <Button label="Cancel" onPress={cancel} hint="Stops waiting for this result" />
        </View>
      ) : (
        <>
          {STYLE_API_URL === null && (
            <Text style={styles.muted} accessibilityRole="alert">AI styles are not connected in this version of the app yet, so generating is turned off.</Text>
          )}
          <Button
            label={`Generate ${current.name}`}
            variant="primary"
            disabled={source === null || busy || STYLE_API_URL === null}
            onPress={() => void onGenerate()}
            hint={source === null ? 'Add a photo first' : 'Sends your photo to create the styled image'}
          />
          <QuotaBadge quota={quota} />
        </>
      )}

      {phase.kind === 'error' && advice !== null && (
        <View style={styles.errorCard} accessibilityRole="alert" testID="generation-error">
          <Text style={styles.h2}>{advice.title}</Text>
          <Text style={styles.body}>{phase.error.message}</Text>
          {phase.error.code === 'CANCELED' && <Text style={styles.muted}>If the service had already started, this attempt may still count toward your limit.</Text>}
          {phase.error.retryAfterSeconds !== null && <Text style={styles.muted}>Try again in about {formatWait(phase.error.retryAfterSeconds)}.</Text>}
          {phase.error.requestId !== null && <Text style={styles.caption}>Reference: {phase.error.requestId.slice(0, 12)}</Text>}
          <View style={styles.row}>
            {(advice.action === 'retry' || phase.error.code === 'CANCELED') && <Button label="Try again" variant="primary" onPress={() => void onGenerate()} />}
            <Button label="Choose another style" onPress={() => router.back()} />
          </View>
        </View>
      )}

      <ConsentSheet
        visible={consentOpen}
        provider={provider}
        onAccept={() => {
          if (provider !== null) grantAiConsent(provider);
          setConsentOpen(false);
          void run();
        }}
        onCancel={() => setConsentOpen(false)}
        onReadMore={() => {
          setConsentOpen(false);
          router.push('/privacy');
        }}
      />
    </ScrollView>
  );
}

function bandHint(label: string): string {
  switch (label) {
    case 'Subtle':
      return 'mostly colour, light and texture; still looks like a photo.';
    case 'Moderate':
      return 'clearly styled, face kept close to the photo.';
    case 'Strong':
      return 'background and clothing restyled, face stylised.';
    default:
      return 'the whole image in this style.';
  }
}

function formatWait(seconds: number): string {
  if (seconds < 90) return `${seconds} seconds`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} minutes`;
  return `${Math.round(seconds / 3600)} hours`;
}

const styles = StyleSheet.create({
  page: { padding: space(4), gap: space(3), maxWidth: 720, width: '100%', alignSelf: 'center' },
  hero: { flexDirection: 'row', gap: space(4), alignItems: 'center' },
  grow: { flex: 1, gap: space(1) },
  h1: { ...type('h1'), color: colors.text },
  h2: { ...type('h2'), color: colors.text },
  body: { ...type('body'), color: colors.text, flexShrink: 1 },
  muted: { ...type('body'), color: colors.muted },
  caption: { ...type('caption'), color: colors.muted },
  card: { backgroundColor: colors.surface, borderRadius: radii.sheet, padding: space(4), gap: space(3) },
  errorCard: { backgroundColor: colors.surface, borderRadius: radii.sheet, padding: space(4), gap: space(3), borderWidth: 1, borderColor: colors.error },
  row: { flexDirection: 'row', alignItems: 'center', gap: space(3), flexWrap: 'wrap' },
});
