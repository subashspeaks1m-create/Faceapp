import { Link, useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { usePhotoPicker } from '../src/media/usePhotoPicker';
import { useSession } from '../src/session';
import { CATALOG } from '../src/styles/catalog';
import { Button } from '../src/ui/Button';
import { PickerPanel } from '../src/ui/PickerPanel';
import { StyleSwatch } from '../src/ui/StyleSwatch';
import { colors, radii, space, type } from '../src/ui/theme';

const FEATURED = ['storybook-anime', 'seventies-film', 'cyberpunk', 'pro-headshot', 'watercolor', 'film-noir'];

export default function Home() {
  const router = useRouter();
  const { privacyAcknowledged, acknowledgePrivacy, setSource } = useSession();
  const picker = usePhotoPicker((source) => {
    setSource(source);
    router.push('/editor');
  });

  if (!privacyAcknowledged) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Text accessibilityRole="header" style={styles.h1}>Before you start</Text>
        <View style={styles.card}>
          <Text style={styles.body}>
            The photo editor (adjustments, looks and crops) runs on this device. Your photo is not uploaded to edit it, and your original file is never changed.
          </Text>
          <Text style={styles.body}>
            AI Styles are different: they send a copy of your photo to our server and an AI provider to create the styled image. We ask for your permission before the first one, and nothing is sent until you tap Generate.
          </Text>
        </View>
        <Button label="Continue" variant="primary" onPress={acknowledgePrivacy} />
        <Link href="/privacy" style={styles.link}>Read the privacy details</Link>
      </ScrollView>
    );
  }

  const featured = FEATURED.map((id) => CATALOG.styles.find((s) => s.id === id)).filter((s) => s !== undefined);
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text accessibilityRole="header" style={styles.h1}>PortraitLab</Text>

      <View style={styles.card}>
        <Text accessibilityRole="header" style={styles.h2}>AI Styles</Text>
        <Text style={styles.muted}>Turn a photo into one of {CATALOG.styles.length} looks with one tap, from 70s film to storybook anime.</Text>
        <View style={styles.swatches} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {featured.map((s) => (
            <StyleSwatch key={s.id} swatch={s.swatch} size={40} />
          ))}
        </View>
        <Button label="Browse AI styles" variant="primary" onPress={() => router.push('/styles')} />
      </View>

      <View style={styles.card}>
        <Text accessibilityRole="header" style={styles.h2}>Photo editor</Text>
        <Text style={styles.muted}>Adjust light and colour, apply looks and crop. Runs on this device; nothing is uploaded.</Text>
        <PickerPanel status={picker.status} busy={picker.busy} onChoose={picker.chooseFromLibrary} onTake={picker.takePhoto} />
      </View>

      <View style={styles.footer}>
        <Pressable accessibilityRole="link" onPress={() => router.push('/privacy')} hitSlop={8}>
          <Text style={styles.link}>Privacy</Text>
        </Pressable>
        <Pressable accessibilityRole="link" onPress={() => router.push('/settings')} hitSlop={8}>
          <Text style={styles.link}>Settings</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space(4), gap: space(4), maxWidth: 720, width: '100%', alignSelf: 'center' },
  h1: { ...type('h1'), color: colors.text },
  h2: { ...type('h2'), color: colors.text },
  body: { ...type('body'), color: colors.text },
  muted: { ...type('body'), color: colors.muted },
  card: { backgroundColor: colors.surface, borderRadius: radii.sheet, padding: space(4), gap: space(3) },
  swatches: { flexDirection: 'row', gap: space(2), flexWrap: 'wrap' },
  footer: { flexDirection: 'row', gap: space(5), justifyContent: 'center', paddingVertical: space(2) },
  link: { ...type('label'), color: colors.accent, textDecorationLine: 'underline' },
});
