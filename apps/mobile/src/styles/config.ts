import { normalizeBaseUrl } from './client.ts';

// Public base URL of the style API, inlined at build time. It is not a secret: the API key lives
// only on the server. Unset means AI styles show as "not connected" rather than pretending to work.
export const STYLE_API_URL: string | null = normalizeBaseUrl(process.env.EXPO_PUBLIC_STYLE_API_URL);
