// Offline-tested orchestration only: no default fetch, credentials, URL enable or CLI.
// A future authorized runner must supply its existing preflight, watchdog and callbacks.
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { setTimeout as pause } from 'node:timers/promises';

export const READINESS_ORIGIN = 'https://kinoko-comments-staging-20261031.sasama-bb.workers.dev';
const TEAM = 'https://floral-silence-7565.cloudflareaccess.com';
const LIMIT = 65536;
const REDIRECTS = new Set([301, 302, 303, 307, 308]);
const APP = /data-research-thread|STAGING_ACCESS_DENIED|STAGING_UNAVAILABLE|"active_ids"|"identity_hash"/;
export const DIAGNOSTIC_PROTOCOL = 'access-origin-diagnostic-v2';
const STABLE_REDIRECTS = 3;

// Never enumerate headers: credentials, cookies, URLs and arbitrary server text
// are not diagnostic output. Unknown values are classified, never echoed.
export function diagnosticHeaders(headers) {
  const value = name => headers.get(name);
  const choice = (name, allowed) => {
    const v = value(name)?.toLowerCase();
    return v == null ? 'absent' : allowed.includes(v) ? v : 'other-redacted';
  };
  const ray = value('cf-ray'), type = value('cf-error-type'), age = value('age');
  return {
    server: choice('server', ['cloudflare']),
    cf_ray: ray == null ? null : /^[a-f0-9]{16,32}-[A-Z]{3}$/.test(ray) ? ray : 'invalid-redacted',
    cf_error_type: type == null ? null : /^\d{3,5}$/.test(type) ? type : 'invalid-redacted',
    cf_error_origin: choice('cf-error-origin', ['workers', 'edge', 'origin', 'access', 'routing', 'assets']),
    cf_cache_status: choice('cf-cache-status', ['hit', 'miss', 'dynamic', 'bypass', 'expired', 'stale', 'updating', 'revalidated', 'none']),
    age_seconds: age == null ? null : /^\d{1,9}$/.test(age) ? Number(age) : 'invalid-redacted',
    cf_mitigated: choice('cf-mitigated', ['challenge']),
    // These headers can help correlate provider logs; none proves our fetch()
    // ran. No new response marker or runtime/observability change is needed.
    worker_execution: 'not-established',
  };
}

function redirectKind(location) {
  if (!location) return 'none';
  try {
    const u = new URL(location);
    return u.origin === TEAM && !u.username && !u.password &&
      ['/cdn-cgi/access/login', '/cdn-cgi/access/login/' + new URL(READINESS_ORIGIN).hostname].includes(u.pathname)
      ? 'exact_access_login' : 'unexpected';
  } catch { return 'unexpected'; }
}

async function observe(request, timeoutMs) {
  const controller = new AbortController();
  let timer, reader;
  const cancelReader = () => { if (reader) void reader.cancel().catch(() => {}); };
  controller.signal.addEventListener('abort', cancelReader, {once: true});
  try {
    return await Promise.race([
      (async () => {
        const r = await request(READINESS_ORIGIN + '/', {
          method: 'GET', headers: {}, credentials: 'omit', redirect: 'manual', cache: 'no-store',
          signal: controller.signal,
        });
        const item = {status: r.status, content_type: 'other', redirect: redirectKind(r.headers.get('location')),
          diagnostic_headers: diagnosticHeaders(r.headers)};
        const mime = (r.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
        if (['text/html', 'text/plain', 'application/json'].includes(mime)) item.content_type = mime;
        if (r.redirected || r.url && r.url !== READINESS_ORIGIN + '/') return {...item, decision: 'stop', reason: 'REDIRECT_WAS_FOLLOWED'};
        reader = r.body?.getReader();
        const chunks = [];
        let size = 0;
        if (reader) while (true) {
          const {value, done} = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > LIMIT) {
            controller.abort();
            return {...item, body_bytes_at_least: size, decision: 'stop', reason: 'BODY_LIMIT'};
          }
          chunks.push(Buffer.from(value));
        }
        const body = Buffer.concat(chunks), text = body.toString('utf8');
        item.body_bytes = body.length;
        item.body_sha256 = createHash('sha256').update(body).digest('hex');
        const code = text.match(/\bError\s+(1101|1102|1103|1015|1027)\b/i)?.[1];
        if (code) item.error_code_observed = Number(code);
        let json = false;
        try { const v = JSON.parse(text); json = v !== null && typeof v === 'object'; } catch {}
        if (APP.test(text) || json || item.content_type === 'application/json') return {...item, decision: 'stop', reason: 'APPLICATION_OR_JSON_BODY'};
        if (code) return {...item, decision: 'stop', reason: 'ERROR_CODE_RESPONSE'};
        if (item.diagnostic_headers.cf_error_type !== null || item.diagnostic_headers.cf_error_origin !== 'absent' ||
            item.diagnostic_headers.cf_mitigated !== 'absent') return {...item, decision: 'stop', reason: 'PROVIDER_ERROR_OR_CHALLENGE'};
        // A 404 is a bounded readiness observation, never an authentication pass.
        if (r.status === 404 && item.redirect === 'none') return {...item, decision: 'pending', reason: 'HTTP_404_UNCLASSIFIED'};
        if (REDIRECTS.has(r.status) && item.redirect === 'exact_access_login') return {...item, decision: 'ready', reason: 'ACCESS_REDIRECT_OBSERVED'};
        return {...item, decision: 'stop', reason: 'UNRECOGNIZED_RESPONSE'};
      })(),
      new Promise((_, reject) => { timer = setTimeout(() => {
        controller.abort(); reject(new Error('TIMEOUT'));
      }, timeoutMs); }),
    ]);
  } catch {
    // Never serialize response bodies, URLs, exception text or request secrets.
    return {decision: 'stop', reason: controller.signal.aborted ? 'REQUEST_TIMEOUT' : 'REQUEST_FAILED'};
  } finally { clearTimeout(timer); controller.signal.removeEventListener('abort', cancelReader); }
}

export async function waitForAccessReadiness({request, now = () => performance.now(), sleep = pause,
  utcNow = () => new Date().toISOString(),
  budgetMs = 15000, requestMs = 4000, intervalMs = 3000, maxObservations = 3}) {
  if (typeof request !== 'function' || !Number.isFinite(budgetMs) || budgetMs <= 0 || budgetMs > 15000 ||
      !Number.isFinite(requestMs) || requestMs <= 0 || requestMs > 4000 ||
      !Number.isFinite(intervalMs) || intervalMs < 1 || intervalMs > 3000 ||
      !Number.isInteger(maxObservations) || maxObservations < 1 || maxObservations > 3) throw new Error('INVALID_READINESS_BOUNDS');
  const start = now(), observations = [];
  let redirects = 0;
  for (let i = 0; i < maxObservations; i++) {
    const remaining = budgetMs - (now() - start);
    if (remaining <= 0) break;
    const started_at = utcNow(), begin = now();
    const item = await observe(request, Math.min(requestMs, remaining));
    if (item.decision === 'ready') {
      redirects++;
      if (redirects < STABLE_REDIRECTS) {
        item.decision = 'pending'; item.reason = 'ACCESS_REDIRECT_CANDIDATE';
      } else item.reason = 'ACCESS_REDIRECT_WINDOW_OBSERVED';
    } else if (item.reason === 'HTTP_404_UNCLASSIFIED' && redirects > 0) {
      item.decision = 'stop'; item.reason = 'ACCESS_REDIRECT_REGRESSED_TO_404';
    }
    observations.push({method: 'GET', path: '/', authenticated: false,
      started_at, completed_at: utcNow(), wall_ms: Math.max(0, now() - begin),
      elapsed_ms: Math.max(0, now() - start), wall_is_not_cpu: true, ...item});
    if (now() - start >= budgetMs) break;
    if (item.decision !== 'pending') return {state: item.decision, reason: item.reason, observations,
      consecutive_access_redirects: redirects, security_tests_passed: 0};
    if (i + 1 < maxObservations) {
      const delay = Math.min(intervalMs, budgetMs - (now() - start));
      if (delay <= 0) break;
      await sleep(delay);
    }
  }
  return {state: 'stop', reason: 'READINESS_NOT_ESTABLISHED', observations,
    consecutive_access_redirects: redirects, security_tests_passed: 0};
}

// The independent security gate uses exactly the same root request/metadata
// collector as readiness. It is not another wait/retry loop: any 404 stops.
export async function verifyUnauthenticatedRoot({request, now = () => performance.now(),
  utcNow = () => new Date().toISOString(), requestMs = 4000}) {
  if (typeof request !== 'function' || !Number.isFinite(requestMs) || requestMs <= 0 || requestMs > 4000)
    throw Error('INVALID_GATE_BOUNDS');
  const started_at = utcNow(), begin = now(), item = await observe(request, requestMs);
  return {method: 'GET', path: '/', authenticated: false, started_at, completed_at: utcNow(),
    wall_ms: Math.max(0, now() - begin), wall_is_not_cpu: true, ...item,
    pass: item.decision === 'ready'};
}

export async function runGuardedReadiness({close, verifyUnauthenticated, runAuthenticated, ...options}) {
  if (![close, verifyUnauthenticated, runAuthenticated].every(f => typeof f === 'function')) throw new Error('REQUIRED_GUARD_MISSING');
  const report = {result: 'STOP', authenticated_phase_started: false, closure_verified: false};
  try {
    report.readiness = await waitForAccessReadiness(options);
    if (report.readiness.state !== 'ready') report.reason = report.readiness.reason;
    else if (await verifyUnauthenticated() !== true) report.reason = 'UNAUTHENTICATED_GATE_FAILED';
    else {
      report.authenticated_phase_started = true;
      if (await runAuthenticated() === true) report.result = 'PHASE_COMPLETE';
      else report.reason = 'AUTHENTICATED_PHASE_FAILED';
    }
  } catch { report.reason = 'PHASE_EXCEPTION'; }
  finally {
    try { report.closure_verified = await close() === true; } catch {}
    if (!report.closure_verified) {
      report.phase_reason = report.reason || null;
      report.reason = 'CLOSURE_UNCONFIRMED'; report.result = 'STOP';
    }
  }
  return report;
}
