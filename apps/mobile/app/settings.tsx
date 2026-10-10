import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { AI_CONSENT_VERSION, useSession } from '../src/session';
import { CATALOG } from '../src/styles/catalog';
import { fetchHealth, fetchQuota, type Health, isStyleError, providerInfo, type StyleError } from '../src/styles/client';
import { STYLE_API_URL } from '../src/styles/config';
import { styleFetch } from '../src/styles/upload';
import { Button } from '../src/ui/Button';
import { quotaText } from '../src/ui/QuotaBadge';
import { colors, radii, space, type } from '../src/ui/theme';

export default function Settings() {
  const router = useRouter();
  const { aiConsentProvider, withdrawAiConsent, source, result, setSource, setResult, quota, setQuota } = useSession();
  const [health, setHealth] = useState<Health | StyleError | null>(null);
  const [cleared, setCleared] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    void fetchHealth(STYLE_API_URL, styleFetch, ctrl.signal).then(setHealth);
    if (STYLE_API_URL !== null) {
      void fetchQuota(STYLE_API_URL, styleFetch, ctrl.signal).then((q) => {
        if (!isStyleError(q)) setQuota(q);
      });
    }
    return () => ctrl.abort();
  }, [setQuota]);

  const status =
    health === null ? 'Checking…'
    : isStyleError(health) ? health.message
    : health.providerConfigured ? `Connected and ready (images by ${providerInfo(health.provider).label}).`
    : 'Connected, but the AI provider is not set up on the server yet.';

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text accessibilityRole="header" style={styles.h1}>Settings</Text>

      <View style={styles.card}>
        <Text accessibilityRole="header" style={styles.h2}>AI Styles</Text>
        <Text style={styles.body} accessibilityLiveRegion="polite">Service: {status}</Text>
        {quota !== null && <Text style={styles.body}>Usage: {quotaText(quota)}</Text>}
        <Text style={styles.muted}>{CATALOG.styles.length} styles, catalog {CATALOG.version}</Text>
      </View>

      <View style={styles.card}>
        <Text accessibilityRole="header" style={styles.h2}>Consent</Text>
        <Text style={styles.body}>
          {aiConsentProvider !== null ? `You agreed to send photos to ${providerInfo(aiConsentProvider).label} for AI styling (terms version ${AI_CONSENT_VERSION}).` : 'You have not agreed to send photos for AI styling. The app asks before the first upload.'}
        </Text>
        {aiConsentProvider !== null && <Button label="Withdraw AI consent" onPress={withdrawAiConsent} />}
      </View>

      <View style={styles.card}>
        <Text accessibilityRole="header" style={styles.h2}>This session</Text>
        <Text style={styles.body}>{source === null && result === null ? 'No photo or result is loaded.' : 'A photo or result is loaded in the app.'}</Text>
        <Button
          label="Clear photo and result"
          disabled={source === null && result === null}
          onPress={() => {
            setSource(null);
            setResult(null);
            setCleared(true);
          }}
        />
        {cleared && <Text style={styles.muted} accessibilityLiveRegion="polite">Cleared.</Text>}
      </View>

      <Button label="Privacy details" onPress={() => router.push('/privacy')} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space(4), gap: space(3), maxWidth: 720, width: '100%', alignSelf: 'center' },
  h1: { ...type('h1'), color: colors.text },
  h2: { ...type('h2'), color: colors.text },
  body: { ...type('body'), color: colors.text },
  muted: { ...type('caption'), color: colors.muted },
  card: { backgroundColor: colors.surface, borderRadius: radii.sheet, padding: space(4), gap: space(3) },
});
