/**
 * Pre-build guard: validates frontend environment variables.
 *
 * 1. VITE_API_BASE_URL must be set and not localhost in CI.
 * 2. No secret-looking VITE_* vars (keys, tokens, passwords, DB URLs)
 *    are allowed — those belong in the backend only.
 *
 * Runs automatically via the "prebuild" npm script.
 * Skipped gracefully during local `npm run dev`.
 */

const FORBIDDEN_VITE_PATTERNS = [
  /^VITE_.*SECRET/i,
  /^VITE_.*API_KEY/i,
  /^VITE_.*TOKEN/i,
  /^VITE_.*PASSWORD/i,
  /^VITE_.*PRIVATE/i,
  /^VITE_DATABASE/i,
  /^VITE_DB_/i,
  /^VITE_.*CREDENTIAL/i,
];

const url = process.env.VITE_API_BASE_URL;
const isCI = !!process.env.CI;
let failed = false;

// --- 1. Validate VITE_API_BASE_URL ---

if (!url) {
  if (isCI) {
    console.error('ERROR: VITE_API_BASE_URL is not set. Set it in Netlify → Site settings → Environment variables.');
    process.exit(1);
  }
  console.warn('WARN: VITE_API_BASE_URL not set — defaulting to localhost (OK for local dev).');
} else if (url.includes('localhost') || url.includes('127.0.0.1')) {
  if (isCI) {
    console.error(`ERROR: VITE_API_BASE_URL points to localhost (${url}). This must be the production API URL in CI.`);
    process.exit(1);
  }
  console.warn(`WARN: VITE_API_BASE_URL points to localhost (${url}) — OK for local dev.`);
} else {
  if (!url.startsWith('https://')) {
    console.warn(`WARN: VITE_API_BASE_URL does not use HTTPS: ${url}`);
  }
  console.log(`VITE_API_BASE_URL validated: ${url}`);
}

// --- 2. Scan for secret-looking VITE_* vars ---

for (const [key, value] of Object.entries(process.env)) {
  if (!key.startsWith('VITE_')) continue;
  for (const pattern of FORBIDDEN_VITE_PATTERNS) {
    if (pattern.test(key)) {
      console.error(
        `ERROR: Forbidden env var "${key}" detected. ` +
        'Secrets must never be exposed to the frontend. ' +
        'Move this to the backend and access it server-side only.',
      );
      failed = true;
      break;
    }
  }
}

if (failed) {
  process.exit(1);
}
