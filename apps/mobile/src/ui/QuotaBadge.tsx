import { StyleSheet, Text } from 'react-native';
import type { Quota } from '../styles/client';
import { colors, space, type } from './theme';

const WINDOW: Record<string, string> = { hour: 'this hour', day: 'today', global: 'today (service-wide)' };

export function quotaText(q: Quota): string {
  return `${q.remaining} of ${q.limit} generations left ${WINDOW[q.window] ?? ''}`.trim();
}

export function QuotaBadge({ quota }: { readonly quota: Quota | null }) {
  if (quota === null) return null;
  return (
    <Text style={[styles.text, quota.remaining === 0 && styles.empty]} accessibilityLiveRegion="polite">
      {quotaText(quota)}
    </Text>
  );
}

const styles = StyleSheet.create({
  text: { ...type('caption'), color: colors.muted, paddingVertical: space(1) },
  empty: { color: colors.warning },
});
