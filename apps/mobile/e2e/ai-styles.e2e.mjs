// Browser end-to-end test of the AI Styles flow against the REAL style API running locally,
// whose provider URL points at tests/e2e/fake_openai.py (a sepia-toning stand-in, NOT OpenAI).
// See docs/TESTING.md for how to start the three local servers. Requires Playwright + Chromium.
//
//   APP_URL=http://localhost:8765/ API_URL=http://localhost:8790 node e2e/ai-styles.e2e.mjs

import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  ({ chromium } = require(join(execSync('npm root -g').toString().trim(), 'playwright')));
}

const APP_URL = process.env.APP_URL ?? 'http://localhost:8765/';
const API_URL = process.env.API_URL ?? 'http://localhost:8790';
const PORTRAIT = new URL('../../../assets/demo/portrait-original.png', import.meta.url);
const out = mkdtempSync(join(tmpdir(), 'ai-styles-e2e-'));
const log = (m) => console.log(`✓ ${m}`);

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage({ viewport: { width: 412, height: 915 }, acceptDownloads: true });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
const requests = [];
page.on('request', (r) => requests.push(r));

try {
  await page.goto(APP_URL);
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Browse AI styles' }).click();
  await page.getByText('25 styles', { exact: true }).waitFor();
  log('style browser lists 25 styles');

  await page.getByLabel('Search styles').fill('noir');
  await page.getByText('1 of 25 styles').waitFor();
  await page.getByLabel('Search styles').fill('');
  await page.getByRole('button', { name: 'Retro', exact: true }).click();
  await page.getByText('4 of 25 styles').waitFor();
  await page.getByRole('button', { name: 'All', exact: true }).click();
  log('search and category filter work');

  const chooser = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Choose photo' }).click();
  await (await chooser).setFiles(PORTRAIT.pathname);
  await page.getByText('Your photo').waitFor();
  log('photo chosen');

  await page.getByTestId('style-seventies-film').click();
  await page.getByRole('button', { name: 'Generate 70s Retro Film' }).click();

  // Consent is required before the first upload; nothing has been sent yet.
  assert.equal(requests.filter((r) => r.url().includes('/api/generate')).length, 0);
  if (process.env.EXPECT_PROVIDER_LABEL) {
    await page.getByText(new RegExp(`processed by ${process.env.EXPECT_PROVIDER_LABEL.replace(/[()]/g, '\\$&')}`)).filter({ visible: true }).waitFor();
  }
  const agree = page.getByRole('button', { name: 'Agree and continue' });
  assert.equal(await agree.isDisabled(), true);
  for (const box of await page.getByRole('checkbox').all()) await box.click();
  await agree.click();
  log('consent sheet shown and accepted');

  await page.getByTestId('compare').waitFor({ timeout: 60_000 });
  const gen = requests.filter((r) => r.url() === `${API_URL}/api/generate`);
  assert.equal(gen.length, 1);
  const resp = await gen[0].response();
  assert.equal(resp.status(), 200);
  assert.equal((await resp.allHeaders())['x-style-id'], 'seventies-film');
  assert.equal((await resp.allHeaders())['content-type'], 'image/jpeg');
  log('generation request sent to the style API and a result shown');

  await page.getByText(/1 of 2 generations left this hour/).filter({ visible: true }).first().waitFor();
  log('quota indicator updated from response headers');

  await page.getByRole('button', { name: 'Result', exact: true }).click();
  await page.getByTestId('result-image').waitFor();
  await page.getByRole('button', { name: 'Original', exact: true }).click();
  await page.getByTestId('original-image').waitFor();
  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  log('before/after views switch');

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download' }).click();
  const file = join(out, 'result.jpg');
  await (await download).saveAs(file);
  const bytes = readFileSync(file);
  assert.deepEqual([...bytes.subarray(0, 3)], [0xff, 0xd8, 0xff]);
  log(`download saved a JPEG (${bytes.length} bytes)`);
  await page.screenshot({ path: join(out, 'result.png'), fullPage: true });

  // Second generation uses the last of the hourly quota; the third is refused by the server.
  await page.getByRole('button', { name: 'Adjust and regenerate' }).click();
  await page.getByRole('button', { name: 'Generate 70s Retro Film' }).click();
  await page.getByTestId('compare').waitFor({ timeout: 60_000 });
  await page.getByRole('button', { name: 'Adjust and regenerate' }).click();
  await page.getByRole('button', { name: 'Generate 70s Retro Film' }).click();
  await page.getByTestId('generation-error').waitFor({ timeout: 30_000 });
  await page.getByText('Limit reached').filter({ visible: true }).waitFor();
  log('server rate limit surfaces as a clear error');
  await page.screenshot({ path: join(out, 'rate-limited.png'), fullPage: true });

  const relevantErrors = errors.filter((e) => !e.includes('429'));
  assert.deepEqual(relevantErrors, []);
  log('no unexpected console errors');
  console.log(`screenshots and download in ${out}`);
} finally {
  await browser.close();
}
