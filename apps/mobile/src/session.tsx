import { File, Paths } from 'expo-file-system';
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from 'react';
import { Platform } from 'react-native';
import type { SourceImage } from './media/normalize';
import type { Quota } from './styles/client';

// Version of the on-device privacy notice the user acknowledged.
export const PRIVACY_NOTICE_VERSION = '2026-10-10.2';
// Version of the consent to send a photo to the AI style service.
export const AI_CONSENT_VERSION = '2026-10-10.2';
const ACK_FILE = 'privacy-ack.json';
const AI_CONSENT_FILE = 'ai-consent.json';

export interface StyleResult {
  /** Displayable URI of the generated JPEG (blob: URL on web, cache file on native). */
  readonly uri: string;
  /** Handle passed to shareExport/downloadExport. */
  readonly file: unknown;
  readonly styleId: string;
  readonly intensity: number;
  /** The source the result was generated from, for Before/After. */
  readonly source: SourceImage;
  readonly requestId: string | null;
}

interface Session {
  readonly source: SourceImage | null;
  readonly setSource: (s: SourceImage | null) => void;
  readonly privacyAcknowledged: boolean;
  readonly acknowledgePrivacy: () => void;
  /** Provider the person agreed to send photos to, or null. Consent is asked again if it changes. */
  readonly aiConsentProvider: string | null;
  readonly grantAiConsent: (provider: string) => void;
  readonly withdrawAiConsent: () => void;
  readonly result: StyleResult | null;
  readonly setResult: (r: StyleResult | null) => void;
  readonly quota: Quota | null;
  readonly setQuota: (q: Quota | null) => void;
}

const SessionContext = createContext<Session | null>(null);

function readStored(name: string): string | null {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(name) ?? null;
  const file = new File(Paths.document, name);
  return file.exists ? file.textSync() : null;
}

function writeStored(name: string, value: string | null): void {
  if (Platform.OS === 'web') {
    if (value === null) globalThis.localStorage?.removeItem(name);
    else globalThis.localStorage?.setItem(name, value);
    return;
  }
  const file = new File(Paths.document, name);
  if (value === null) {
    if (file.exists) file.delete();
    return;
  }
  if (!file.exists) file.create();
  file.write(value);
}

function readVersion(name: string, version: string): boolean {
  try {
    const stored = readStored(name);
    if (stored === null) return false;
    const parsed: unknown = JSON.parse(stored);
    return typeof parsed === 'object' && parsed !== null && (parsed as { version?: unknown }).version === version;
  } catch {
    return false;
  }
}

function readConsentProvider(): string | null {
  try {
    const stored = readStored(AI_CONSENT_FILE);
    if (stored === null) return null;
    const parsed: unknown = JSON.parse(stored);
    if (typeof parsed !== 'object' || parsed === null) return null;
    const { version, provider } = parsed as { version?: unknown; provider?: unknown };
    return version === AI_CONSENT_VERSION && typeof provider === 'string' ? provider : null;
  } catch {
    return null;
  }
}

function persist(name: string, value: string | null): void {
  try {
    writeStored(name, value);
  } catch {
    // The choice still holds for this session; it is asked again next launch.
  }
}

export function SessionProvider({ children }: { readonly children: ReactNode }) {
  const [source, setSource] = useState<SourceImage | null>(null);
  const [privacyAcknowledged, setAck] = useState(() => readVersion(ACK_FILE, PRIVACY_NOTICE_VERSION));
  const [aiConsentProvider, setAiConsentProvider] = useState<string | null>(readConsentProvider);
  const [result, setResult] = useState<StyleResult | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);

  const acknowledgePrivacy = useCallback(() => {
    persist(ACK_FILE, JSON.stringify({ version: PRIVACY_NOTICE_VERSION }));
    setAck(true);
  }, []);
  const grantAiConsent = useCallback((provider: string) => {
    persist(AI_CONSENT_FILE, JSON.stringify({ version: AI_CONSENT_VERSION, provider, at: new Date().toISOString() }));
    setAiConsentProvider(provider);
  }, []);
  const withdrawAiConsent = useCallback(() => {
    persist(AI_CONSENT_FILE, null);
    setAiConsentProvider(null);
  }, []);

  const value = useMemo(
    () => ({ source, setSource, privacyAcknowledged, acknowledgePrivacy, aiConsentProvider, grantAiConsent, withdrawAiConsent, result, setResult, quota, setQuota }),
    [source, privacyAcknowledged, acknowledgePrivacy, aiConsentProvider, grantAiConsent, withdrawAiConsent, result, quota],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (s === null) throw new Error('useSession outside SessionProvider');
  return s;
}
