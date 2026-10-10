import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { colors, radii, space, type } from '../src/ui/theme';

const SECTIONS: readonly { title: string; body: readonly string[] }[] = [
  {
    title: 'Photo editor',
    body: ['Adjustments, looks and crops run on your device. Your photo is not uploaded for them, and your original file is never changed.'],
  },
  {
    title: 'AI Styles: what is sent',
    body: [
      'Only when you tap Generate, the app uploads one copy of your chosen photo (resized to at most 1536 pixels and re-encoded, which removes location and camera metadata) with the style name and strength.',
      'The PortraitLab style service checks the photo, then sends it with a style description to its AI provider, which creates the styled image. The provider is OpenAI or Google (Gemini), depending on how the service is set up; the consent screen names the one in use, and the app asks again if it changes.',
    ],
  },
  {
    title: 'What is kept',
    body: [
      'The PortraitLab style service does not save your photo or the result. They exist in memory while the request runs and are discarded when the result is sent back to you. There is no gallery or account.',
      'The service logs a random request ID, the style, timing and an error code if something fails. It does not log images or your IP address. To apply usage limits it stores a one-way hashed form of your IP address with counters that expire within a day.',
      'OpenAI processes photos under its API terms: API data is not used to train its models by default, and request data may be kept for up to 30 days to detect abuse.',
      'Google processes photos under the Gemini API terms for paid accounts: requests are not used to improve Google products and are logged for a limited time to detect abuse. The service is only allowed to use Gemini with a paid account.',
      'The result stays on your device until you close or reset the app, unless you save or share it.',
    ],
  },
  {
    title: 'Your choices',
    body: [
      'Only upload photos of yourself or of people who have agreed. Do not upload photos of children.',
      'You can withdraw AI consent at any time in Settings. The app will ask again before any future upload.',
      'AI results are artistic interpretations. They can change details and should not be used to identify anyone or as a real photo of them.',
    ],
  },
];

export default function Privacy() {
  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text accessibilityRole="header" style={styles.h1}>Privacy</Text>
      {SECTIONS.map((s) => (
        <View key={s.title} style={styles.card}>
          <Text accessibilityRole="header" style={styles.h2}>{s.title}</Text>
          {s.body.map((p) => (
            <Text key={p} style={styles.body}>{p}</Text>
          ))}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space(4), gap: space(3), maxWidth: 720, width: '100%', alignSelf: 'center' },
  h1: { ...type('h1'), color: colors.text },
  h2: { ...type('h2'), color: colors.text },
  body: { ...type('body'), color: colors.text },
  card: { backgroundColor: colors.surface, borderRadius: radii.sheet, padding: space(4), gap: space(3) },
});
