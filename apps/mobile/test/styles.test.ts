import assert from 'node:assert/strict';
import { test } from 'node:test';
import { bandFor, CATALOG, filterStyles, styleById } from '../src/styles/catalog.ts';
import { errorAdvice, type FetchLike, fetchQuota, generate, normalizeBaseUrl } from '../src/styles/client.ts';
import { outputAspect, uploadSize } from '../src/styles/uploadSize.ts';

const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3]);

function fakeFetch(handler: (url: string, init: { method: string; body?: unknown }) => { status: number; headers?: Record<string, string>; body: unknown }): FetchLike {
  return async (url, init) => {
    const r = handler(url, init);
    const headers = new Map(Object.entries(r.headers ?? {}).map(([k, v]) => [k.toLowerCase(), v]));
    return {
      ok: r.status >= 200 && r.status < 300,
      status: r.status,
      headers: { get: (n: string) => headers.get(n.toLowerCase()) ?? null },
      json: async () => {
        if (typeof r.body === 'string') throw new SyntaxError('not json');
        return r.body;
      },
      arrayBuffer: async () => (r.body instanceof Uint8Array ? r.body.slice().buffer : new ArrayBuffer(0)),
    };
  };
}

class FakeForm {
  readonly entries: [string, unknown][] = [];
  append(name: string, value: unknown): void {
    this.entries.push([name, value]);
  }
}

test('catalog has the 25 styles in five categories, with no prompt text', () => {
  assert.equal(CATALOG.styles.length, 25);
  assert.deepEqual(CATALOG.categories.map((c) => c.id), ['retro', 'illustration', 'cinematic', 'editorial', 'artistic']);
  assert.equal(styleById('storybook-anime')?.name, 'Ghibli-Inspired Storybook');
  assert.ok(!JSON.stringify(CATALOG).includes('prompt'));
});

test('search and category filter', () => {
  assert.equal(filterStyles('', 'all').length, 25);
  assert.equal(filterStyles('', 'retro').length, 4);
  assert.deepEqual(filterStyles('noir', 'all').map((s) => s.id), ['film-noir']);
  assert.deepEqual(filterStyles('black and white', 'artistic').map((s) => s.id), ['fine-art-mono']);
  assert.ok(filterStyles('ANIME', 'all').some((s) => s.id === 'storybook-anime'));
  assert.equal(filterStyles('zzzz', 'all').length, 0);
});

test('intensity bands', () => {
  assert.equal(bandFor(0).label, 'Subtle');
  assert.equal(bandFor(25).label, 'Subtle');
  assert.equal(bandFor(26).label, 'Moderate');
  assert.equal(bandFor(75).label, 'Strong');
  assert.equal(bandFor(76).label, 'Full');
  assert.equal(bandFor(140).label, 'Full');
});

test('base URL must be https except for local development hosts', () => {
  assert.equal(normalizeBaseUrl(undefined), null);
  assert.equal(normalizeBaseUrl(''), null);
  assert.equal(normalizeBaseUrl('https://api.example.com/'), 'https://api.example.com');
  assert.equal(normalizeBaseUrl('http://api.example.com'), null);
  assert.equal(normalizeBaseUrl('http://localhost:8000'), 'http://localhost:8000');
  assert.equal(normalizeBaseUrl('javascript:alert(1)'), null);
});

test('upload size and output aspect', () => {
  assert.deepEqual(uploadSize(4000, 3000), { width: 1536, height: 1152 });
  assert.deepEqual(uploadSize(1000, 800), { width: 1000, height: 800 });
  assert.equal(outputAspect(3000, 4000), 1024 / 1536);
  assert.equal(outputAspect(1000, 1000), 1);
  assert.equal(outputAspect(1600, 900), 1.5);
});

test('generate sends style, intensity, consent and image; returns bytes and quota', async () => {
  const form = new FakeForm();
  let calledUrl = '';
  const out = await generate({
    baseUrl: 'https://api.example.com',
    fetch: fakeFetch((url) => {
      calledUrl = url;
      return { status: 200, headers: { 'content-type': 'image/jpeg', 'x-quota-remaining': '4', 'x-quota-limit': '5', 'x-quota-window': 'hour', 'x-request-id': 'abc' }, body: JPEG };
    }),
    form,
    imagePart: 'IMAGE',
    styleId: 'cyberpunk',
    intensity: 72.6,
  });
  assert.equal(calledUrl, 'https://api.example.com/api/generate');
  assert.deepEqual(form.entries, [['style_id', 'cyberpunk'], ['intensity', '73'], ['consent', 'true'], ['image', 'IMAGE']]);
  assert.equal(out.kind, 'ok');
  if (out.kind === 'ok') {
    assert.deepEqual(out.quota, { remaining: 4, limit: 5, window: 'hour' });
    assert.equal(out.requestId, 'abc');
    assert.deepEqual([...out.jpeg], [...JPEG]);
  }
});

test('generate maps server errors, bad output, network failure, cancel and missing config', async () => {
  const base = { baseUrl: 'https://api.example.com', imagePart: 'x', styleId: 'cyberpunk', intensity: 50 };
  const rate = await generate({
    ...base,
    form: new FakeForm(),
    fetch: fakeFetch(() => ({ status: 429, body: { error: { code: 'RATE_LIMITED', message: 'Limit reached.', retryable: true, request_id: 'r1', retry_after_seconds: 1200 } } })),
  });
  assert.equal(rate.kind, 'error');
  if (rate.kind === 'error') {
    assert.equal(rate.error.code, 'RATE_LIMITED');
    assert.equal(rate.error.retryAfterSeconds, 1200);
    assert.equal(errorAdvice(rate.error).action, 'wait');
  }
  const unknown = await generate({ ...base, form: new FakeForm(), fetch: fakeFetch(() => ({ status: 500, body: { error: { code: 'SOMETHING_NEW', message: 'x' } } })) });
  assert.equal(unknown.kind === 'error' && unknown.error.code, 'INTERNAL_ERROR');
  const html = await generate({ ...base, form: new FakeForm(), fetch: fakeFetch(() => ({ status: 502, body: '<html>bad gateway</html>' })) });
  assert.equal(html.kind === 'error' && html.error.code, 'INTERNAL_ERROR');
  const notJpeg = await generate({ ...base, form: new FakeForm(), fetch: fakeFetch(() => ({ status: 200, headers: { 'content-type': 'image/jpeg' }, body: new Uint8Array([1, 2, 3, 4]) })) });
  assert.equal(notJpeg.kind === 'error' && notJpeg.error.code, 'INVALID_PROVIDER_RESPONSE');
  const offline = await generate({ ...base, form: new FakeForm(), fetch: async () => { throw new TypeError('Failed to fetch'); } });
  assert.equal(offline.kind === 'error' && offline.error.code, 'NETWORK_ERROR');
  const aborted = await generate({ ...base, form: new FakeForm(), fetch: async () => { throw Object.assign(new Error('aborted'), { name: 'AbortError' }); } });
  assert.equal(aborted.kind === 'error' && aborted.error.code, 'CANCELED');
  let called = false;
  const off = await generate({ ...base, baseUrl: null, form: new FakeForm(), fetch: async () => { called = true; throw new Error(); } });
  assert.equal(off.kind === 'error' && off.error.code, 'NOT_CONNECTED');
  assert.equal(called, false);
});

test('quota fetch', async () => {
  const q = await fetchQuota('https://api.example.com', fakeFetch(() => ({ status: 200, body: { remaining: 3, limit: 5, window: 'hour' } })));
  assert.deepEqual(q, { remaining: 3, limit: 5, window: 'hour' });
});
