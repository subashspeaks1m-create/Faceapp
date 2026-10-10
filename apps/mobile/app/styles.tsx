import { useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSession } from '../src/session';
import { CATALOG, categoryName, filterStyles } from '../src/styles/catalog';
import { fetchQuota, isStyleError } from '../src/styles/client';
import { STYLE_API_URL } from '../src/styles/config';
import type { CategoryId } from '../src/styles/types';
import { styleFetch } from '../src/styles/upload';
import { Button } from '../src/ui/Button';
import { QuotaBadge } from '../src/ui/QuotaBadge';
import { SourceStrip } from '../src/ui/SourceStrip';
import { StyleSwatch } from '../src/ui/StyleSwatch';
import { colors, radii, space, type } from '../src/ui/theme';

export default function Styles() {
  const router = useRouter();
  const { source, setSource, quota, setQuota } = useSession();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<CategoryId | 'all'>('all');
  const results = useMemo(() => filterStyles(query, category), [query, category]);

  useEffect(() => {
    if (STYLE_API_URL === null) return;
    const ctrl = new AbortController();
    void fetchQuota(STYLE_API_URL, styleFetch, ctrl.signal).then((q) => {
      if (!isStyleError(q)) setQuota(q);
    });
    return () => ctrl.abort();
  }, [setQuota]);

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      {STYLE_API_URL === null && (
        <View style={styles.notice} accessibilityRole="alert">
          <Text style={styles.body}>AI styles are switched off for now, so you can look through them but not create images yet. The free photo editor on the home screen works.</Text>
        </View>
      )}
      <SourceStrip source={source} onPicked={setSource} />
      <QuotaBadge quota={quota} />

      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search styles"
        placeholderTextColor={colors.muted}
        accessibilityLabel="Search styles"
        style={styles.search}
        autoCorrect={false}
        returnKeyType="search"
      />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips} accessibilityRole="tablist">
        <Button label="All" selected={category === 'all'} onPress={() => setCategory('all')} />
        {CATALOG.categories.map((c) => (
          <Button key={c.id} label={c.name} selected={category === c.id} onPress={() => setCategory(c.id)} />
        ))}
      </ScrollView>

      <Text style={styles.muted} accessibilityLiveRegion="polite">
        {results.length === CATALOG.styles.length ? `${results.length} styles` : `${results.length} of ${CATALOG.styles.length} styles`}
      </Text>
      {results.length === 0 ? (
        <View style={styles.notice}>
          <Text style={styles.body}>No styles match “{query}”.</Text>
          <Button label="Clear search" onPress={() => { setQuery(''); setCategory('all'); }} />
        </View>
      ) : (
        <View style={styles.grid}>
          {results.map((s) => (
            <Pressable
              key={s.id}
              accessibilityRole="button"
              accessibilityLabel={`${s.name}. ${categoryName(s.category)}. ${s.summary}`}
              accessibilityHint="Opens the style so you can set strength and generate"
              onPress={() => router.push({ pathname: '/style/[id]', params: { id: s.id } })}
              style={({ pressed }) => [styles.tile, pressed && styles.pressed]}
              testID={`style-${s.id}`}
            >
              <StyleSwatch swatch={s.swatch} size={64} />
              <Text style={styles.tileName} numberOfLines={2}>{s.name}</Text>
              <Text style={styles.tileSummary} numberOfLines={2}>{s.summary}</Text>
            </Pressable>
          ))}
        </View>
      )}
      <Text style={styles.caption}>Colour chips show each style's palette. They are not sample results.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space(4), gap: space(3), maxWidth: 960, width: '100%', alignSelf: 'center' },
  body: { ...type('body'), color: colors.text },
  muted: { ...type('caption'), color: colors.muted },
  caption: { ...type('caption'), color: colors.muted, textAlign: 'center' },
  notice: { backgroundColor: colors.raised, borderRadius: radii.sheet, padding: space(3), gap: space(3) },
  search: {
    ...type('body'),
    color: colors.text,
    backgroundColor: colors.surface,
    borderRadius: radii.control,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: space(3),
    minHeight: 48,
  },
  chips: { gap: space(2), paddingVertical: space(1) },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space(3) },
  tile: {
    flexGrow: 1,
    flexBasis: 150,
    maxWidth: 220,
    backgroundColor: colors.surface,
    borderRadius: radii.sheet,
    padding: space(3),
    gap: space(2),
  },
  pressed: { opacity: 0.8 },
  tileName: { ...type('label'), color: colors.text },
  tileSummary: { ...type('caption'), color: colors.muted },
});
