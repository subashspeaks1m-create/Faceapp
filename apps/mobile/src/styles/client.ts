// Style API client. Platform-neutral: the caller supplies fetch and the image form part,
// so the same request/response handling runs in the app and in Node tests.

import type { StyleErrorCode } from './types.ts';

export interface Quota {
  readonly remaining: number;
  readonly limit: number;
  readonly window: string;
}

export interface StyleError {
  readonly code: StyleErrorCode;
  readonly message: string;
  readonly retryable: boolean;
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;
}

export type GenerateOutcome =
  | { readonly kind: 'ok'; readonly jpeg: Uint8Array; readonly quota: Quota | null; readonly requestId: string | null }
  | { readonly kind: 'error'; readonly error: StyleError };

export interface Health {
  readonly providerConfigured: boolean;
  /** "openai" or "gemini" when configured. */
  readonly provider: string | null;
  readonly status: string;
  readonly styleCount: number;
}

export type FetchLike = (url: string, init: { method: string; body?: unknown; signal?: AbortSignal; headers?: Record<string, string> }) => Promise<{
  readonly ok: boolean;
  readonly status: number;
  readonly headers: { get(name: string): string | null };
  json(): Promise<unknown>;
  arrayBuffer(): Promise<ArrayBuffer>;
}>;

const MESSAGES: Record<'NOT_CONNECTED' | 'NETWORK_ERROR' | 'CANCELED' | 'INVALID_PROVIDER_RESPONSE' | 'INTERNAL_ERROR', string> = {
  NOT_CONNECTED: 'AI styles are not connected in this version of the app yet.',
  NETWORK_ERROR: 'Could not reach the style service. Check your connection and try again.',
  CANCELED: 'Generation was canceled.',
  INVALID_PROVIDER_RESPONSE: 'The service returned an unusable image. Try again.',
  INTERNAL_ERROR: 'Something went wrong. Try again.',
};

const KNOWN_CODES: ReadonlySet<string> = new Set<StyleErrorCode>([
  'INVALID_IMAGE', 'UNSUPPORTED_IMAGE_FORMAT', 'IMAGE_TOO_LARGE', 'INVALID_STYLE', 'INVALID_REQUEST', 'CONSENT_REQUIRED',
  'ORIGIN_NOT_ALLOWED', 'PROVIDER_NOT_CONFIGURED', 'RATE_LIMITED', 'PROVIDER_TIMEOUT', 'PROVIDER_REJECTED', 'PROVIDER_ERROR',
  'INVALID_PROVIDER_RESPONSE', 'GENERATION_UNAVAILABLE', 'INTERNAL_ERROR',
]);

export function clientError(code: keyof typeof MESSAGES, retryable = true): StyleError {
  return { code, message: MESSAGES[code], retryable, requestId: null, retryAfterSeconds: null };
}

// Only an https URL (or http on localhost for development) is accepted.
export function normalizeBaseUrl(raw: string | undefined): string | null {
  if (raw === undefined) return null;
  const trimmed = raw.trim().replace(/\/+$/, '');
  if (trimmed === '') return null;
  try {
    const url = new URL(trimmed);
    const local = url.hostname === 'localhost' || url.hostname === '127.0.0.1' || url.hostname.endsWith('.local') || /^10\.|^192\.168\./.test(url.hostname);
    if (url.protocol === 'https:' || (url.protocol === 'http:' && local)) return trimmed;
  } catch {
    // fall through
  }
  return null;
}

function parseQuota(headers: { get(name: string): string | null }): Quota | null {
  const remaining = Number(headers.get('x-quota-remaining'));
  const limit = Number(headers.get('x-quota-limit'));
  const window = headers.get('x-quota-window');
  if (!Number.isInteger(remaining) || !Number.isInteger(limit) || window === null || headers.get('x-quota-remaining') === null) return null;
  return { remaining, limit, window };
}

export async function parseErrorBody(status: number, body: unknown, requestIdHeader: string | null): Promise<StyleError> {
  const err = typeof body === 'object' && body !== null ? (body as { error?: unknown }).error : undefined;
  if (typeof err === 'object' && err !== null) {
    const e = err as Record<string, unknown>;
    const code = typeof e.code === 'string' && KNOWN_CODES.has(e.code) ? (e.code as StyleErrorCode) : 'INTERNAL_ERROR';
    return {
      code,
      message: typeof e.message === 'string' && e.message.length > 0 && e.message.length < 300 ? e.message : MESSAGES.INTERNAL_ERROR,
      retryable: e.retryable === true,
      requestId: typeof e.request_id === 'string' ? e.request_id : requestIdHeader,
      retryAfterSeconds: typeof e.retry_after_seconds === 'number' ? e.retry_after_seconds : null,
    };
  }
  return { ...clientError('INTERNAL_ERROR'), retryable: status >= 500, requestId: requestIdHeader };
}

function isAbort(e: unknown): boolean {
  return typeof e === 'object' && e !== null && (e as { name?: unknown }).name === 'AbortError';
}

function looksLikeJpeg(bytes: Uint8Array): boolean {
  return bytes.length > 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

export interface GenerateArgs {
  readonly baseUrl: string | null;
  readonly fetch: FetchLike;
  readonly form: { append(name: string, value: unknown): void };
  readonly imagePart: unknown;
  readonly styleId: string;
  readonly intensity: number;
  readonly signal?: AbortSignal;
}

export async function generate(args: GenerateArgs): Promise<GenerateOutcome> {
  if (args.baseUrl === null) return { kind: 'error', error: clientError('NOT_CONNECTED', false) };
  const { form } = args;
  form.append('style_id', args.styleId);
  form.append('intensity', String(Math.max(0, Math.min(100, Math.round(args.intensity)))));
  form.append('consent', 'true');
  form.append('image', args.imagePart);
  let resp: Awaited<ReturnType<FetchLike>>;
  try {
    resp = await args.fetch(`${args.baseUrl}/api/generate`, { method: 'POST', body: form, signal: args.signal });
  } catch (e) {
    return { kind: 'error', error: clientError(isAbort(e) ? 'CANCELED' : 'NETWORK_ERROR') };
  }
  const requestId = resp.headers.get('x-request-id');
  try {
    if (!resp.ok) {
      let body: unknown = null;
      try {
        body = await resp.json();
      } catch {
        body = null;
      }
      return { kind: 'error', error: await parseErrorBody(resp.status, body, requestId) };
    }
    const contentType = resp.headers.get('content-type') ?? '';
    const jpeg = new Uint8Array(await resp.arrayBuffer());
    if (!contentType.startsWith('image/jpeg') || !looksLikeJpeg(jpeg)) {
      return { kind: 'error', error: { ...clientError('INVALID_PROVIDER_RESPONSE'), requestId } };
    }
    return { kind: 'ok', jpeg, quota: parseQuota(resp.headers), requestId };
  } catch (e) {
    return { kind: 'error', error: clientError(isAbort(e) ? 'CANCELED' : 'NETWORK_ERROR') };
  }
}

export async function fetchHealth(baseUrl: string | null, fetchImpl: FetchLike, signal?: AbortSignal): Promise<Health | StyleError> {
  if (baseUrl === null) return clientError('NOT_CONNECTED', false);
  try {
    const resp = await fetchImpl(`${baseUrl}/api/health`, { method: 'GET', signal });
    const body = (await resp.json()) as Record<string, unknown>;
    if (!resp.ok) return parseErrorBody(resp.status, body, resp.headers.get('x-request-id'));
    return {
      providerConfigured: body.provider_configured === true,
      provider: typeof body.provider === 'string' ? body.provider : null,
      status: typeof body.status === 'string' ? body.status : 'unknown',
      styleCount: typeof body.style_count === 'number' ? body.style_count : 0,
    };
  } catch (e) {
    return clientError(isAbort(e) ? 'CANCELED' : 'NETWORK_ERROR');
  }
}

export async function fetchQuota(baseUrl: string | null, fetchImpl: FetchLike, signal?: AbortSignal): Promise<Quota | StyleError> {
  if (baseUrl === null) return clientError('NOT_CONNECTED', false);
  try {
    const resp = await fetchImpl(`${baseUrl}/api/quota`, { method: 'GET', signal });
    const body = (await resp.json()) as Record<string, unknown>;
    if (!resp.ok) return parseErrorBody(resp.status, body, resp.headers.get('x-request-id'));
    if (typeof body.remaining !== 'number' || typeof body.limit !== 'number' || typeof body.window !== 'string') return clientError('INTERNAL_ERROR');
    return { remaining: body.remaining, limit: body.limit, window: body.window };
  } catch (e) {
    return clientError(isAbort(e) ? 'CANCELED' : 'NETWORK_ERROR');
  }
}

export function isStyleError(v: unknown): v is StyleError {
  return typeof v === 'object' && v !== null && 'code' in v && 'message' in v && 'retryable' in v;
}

// What the person should do next for each failure.
export function errorAdvice(e: StyleError): { readonly title: string; readonly action: 'retry' | 'new-photo' | 'wait' | 'none' } {
  switch (e.code) {
    case 'INVALID_IMAGE':
    case 'UNSUPPORTED_IMAGE_FORMAT':
    case 'IMAGE_TOO_LARGE':
    case 'PROVIDER_REJECTED':
      return { title: 'Try a different photo', action: 'new-photo' };
    case 'RATE_LIMITED':
      return { title: 'Limit reached', action: 'wait' };
    case 'NOT_CONNECTED':
    case 'PROVIDER_NOT_CONFIGURED':
    case 'ORIGIN_NOT_ALLOWED':
      return { title: 'AI styles are not available', action: 'none' };
    case 'CANCELED':
      return { title: 'Canceled', action: 'retry' };
    default:
      return { title: 'Generation failed', action: e.retryable ? 'retry' : 'none' };
  }
}

// Display name and data-handling summary for the AI provider the server reports.
export function providerInfo(provider: string | null): { readonly label: string; readonly retention: string } {
  switch (provider) {
    case 'openai':
      return { label: 'OpenAI', retention: 'OpenAI may keep request data for up to 30 days to monitor abuse and does not use it to train models by default.' };
    case 'gemini':
      return { label: 'Google (Gemini)', retention: 'Google logs requests for a limited time to detect abuse and, on paid accounts, does not use them to improve its products.' };
    default:
      return { label: 'our AI provider', retention: 'The AI provider may keep request data for a limited time to monitor abuse.' };
  }
}
