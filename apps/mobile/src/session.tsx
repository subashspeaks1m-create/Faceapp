import { File, Paths } from 'expo-file-system';
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from 'react';
import { Platform } from 'react-native';
import type { SourceImage } from './media/normalize';

// Version of the on-device privacy notice the user acknowledged.
export const PRIVACY_NOTICE_VERSION = '2026-10-10';
const ACK_FILE = 'privacy-ack.json';

interface Session {
  readonly source: SourceImage | null;
  readonly setSource: (s: SourceImage | null) => void;
  readonly privacyAcknowledged: boolean;
  readonly acknowledgePrivacy: () => void;
}

const SessionContext = createContext<Session | null>(null);

function readStored(): string | null {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(ACK_FILE) ?? null;
  const file = new File(Paths.document, ACK_FILE);
  return file.exists ? file.textSync() : null;
}

function writeStored(value: string): void {
  if (Platform.OS === 'web') {
    globalThis.localStorage?.setItem(ACK_FILE, value);
    return;
  }
  const file = new File(Paths.document, ACK_FILE);
  if (!file.exists) file.create();
  file.write(value);
}

function readAck(): boolean {
  try {
    const stored = readStored();
    if (stored === null) return false;
    const parsed: unknown = JSON.parse(stored);
    return typeof parsed === 'object' && parsed !== null && (parsed as { version?: unknown }).version === PRIVACY_NOTICE_VERSION;
  } catch {
    return false;
  }
}

export function SessionProvider({ children }: { readonly children: ReactNode }) {
  const [source, setSource] = useState<SourceImage | null>(null);
  const [privacyAcknowledged, setAck] = useState(readAck);
  const acknowledgePrivacy = useCallback(() => {
    try {
      writeStored(JSON.stringify({ version: PRIVACY_NOTICE_VERSION }));
    } catch {
      // Acknowledgement still holds for this session; it is asked again next launch.
    }
    setAck(true);
  }, []);
  const value = useMemo(() => ({ source, setSource, privacyAcknowledged, acknowledgePrivacy }), [source, privacyAcknowledged, acknowledgePrivacy]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (s === null) throw new Error('useSession outside SessionProvider');
  return s;
}
