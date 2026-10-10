import { Stack } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { SessionProvider } from '../src/session';
import { loadSkia } from '../src/skiaLoader';
import { colors } from '../src/ui/theme';

export default function RootLayout() {
  const [skia, setSkia] = useState<'loading' | 'ready' | 'failed'>('loading');
  useEffect(() => {
    loadSkia().then(
      () => setSkia('ready'),
      () => setSkia('failed'),
    );
  }, []);
  if (skia !== 'ready') {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}>
        {skia === 'loading' ? <ActivityIndicator color={colors.accent} /> : <Text style={{ color: colors.error }}>The editor could not start on this device.</Text>}
      </View>
    );
  }
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.background }}>
      <SafeAreaProvider>
        <SessionProvider>
          <StatusBar style="light" />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colors.background },
              headerTintColor: colors.text,
              contentStyle: { backgroundColor: colors.background },
            }}
          >
            <Stack.Screen name="index" options={{ title: 'PortraitLab' }} />
            <Stack.Screen name="editor" options={{ title: 'Edit' }} />
            <Stack.Screen name="+not-found" options={{ title: 'PortraitLab' }} />
          </Stack>
        </SessionProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
