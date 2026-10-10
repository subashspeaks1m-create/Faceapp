// Fails the web build if the compiled output contains anything that looks like a server secret.
// The only style-service value the app may contain is its public URL (EXPO_PUBLIC_STYLE_API_URL).

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const root = process.argv[2] ?? 'dist';
const PATTERNS = [
  [/sk-[A-Za-z0-9_-]{16,}/, 'OpenAI-style secret key'],
  [/sk-proj-[A-Za-z0-9_-]{8,}/, 'OpenAI project key'],
  [/OPENAI_API_KEY/, 'provider key variable name'],
  [/UPSTASH_REDIS_REST_TOKEN/, 'Upstash token variable name'],
  [/RATE_LIMIT_SALT/, 'rate-limit salt variable name'],
  [/AX[A-Za-z0-9]{30,}=/, 'Upstash-style token'],
];

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* files(p);
    else if (/\.(js|html|json|map|css|txt)$/.test(name)) yield p;
  }
}

let found = 0;
for (const file of files(root)) {
  const text = readFileSync(file, 'utf8');
  for (const [re, label] of PATTERNS) {
    if (re.test(text)) {
      console.error(`possible secret (${label}) in ${file}`);
      found++;
    }
  }
}
if (found > 0) process.exit(1);
console.log(`no secrets found in ${root}`);
