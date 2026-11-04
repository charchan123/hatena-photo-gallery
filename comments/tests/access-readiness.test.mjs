import test from 'node:test';
import assert from 'node:assert/strict';
import {READINESS_ORIGIN, waitForAccessReadiness, runGuardedReadiness} from '../tools/access-readiness.mjs';

const login = 'https://floral-silence-7565.cloudflareaccess.com/cdn-cgi/access/login?token=DO_NOT_LOG';
const response = (status, body = '', location) => new Response(body, {status,
  headers: {'content-type': 'text/html', ...(location ? {location} : {})}});
const ready = () => response(302, '', login);
function clock() {let n = 0; return {now: () => n, sleep: async ms => {n += ms;}, advance: ms => {n += ms;}};}
function guard(request, options = {}) {
  const calls = {unauth: 0, auth: 0, close: 0};
  return {calls, run: () => runGuardedReadiness({request, ...clock(),
    verifyUnauthenticated: async () => {calls.unauth++; return true;},
    runAuthenticated: async () => {calls.auth++; return true;},
    close: async () => {calls.close++; return true;}, ...options})};
}

test('three exact Access redirects form only a readiness window, never a security test', async () => {
  let n = 0;
  const g = guard(async (url, options) => {
    assert.equal(url, READINESS_ORIGIN + '/');
    assert.equal(options.redirect, 'manual'); assert.equal(options.credentials, 'omit');
    assert.deepEqual(options.headers, {}); assert.equal(options.method, 'GET');
    assert.ok(options.signal instanceof AbortSignal);
    n++; return ready();
  });
  const r = await g.run();
  assert.equal(r.result, 'PHASE_COMPLETE'); assert.equal(r.closure_verified, true);
  assert.deepEqual(g.calls, {unauth: 1, auth: 1, close: 1});
  assert.deepEqual(r.readiness.observations.map(x => x.decision), ['pending', 'pending', 'ready']);
  assert.equal(r.readiness.security_tests_passed, 0);
  assert.equal(r.readiness.observations[0].reason, 'ACCESS_REDIRECT_CANDIDATE');
  assert.equal(r.readiness.observations[1].elapsed_ms, 3000);
  assert.ok(r.readiness.observations.every(x => x.authenticated === false && x.wall_is_not_cpu));
});

test('repeated404 stops on the second observation without authenticated or security test requests', async () => {
  const g = guard(async () => response(404, 'missing'));
  const r = await g.run();
  assert.equal(r.result, 'STOP'); assert.equal(r.reason, 'HTTP_404_REPEATED');
  assert.equal(r.readiness.observations.length, 2);
  assert.deepEqual(g.calls, {unauth: 0, auth: 0, close: 1});
});

test('overall budget expires even when final response would be an Access redirect', async () => {
  const c = clock(); let n = 0;
  const r = await waitForAccessReadiness({...c, budgetMs: 5, intervalMs: 1, request: async () => {
    c.advance(3); return n++ ? ready() : response(404);
  }});
  assert.equal(r.state, 'stop'); assert.equal(r.reason, 'READINESS_NOT_ESTABLISHED');
  assert.equal(n, 2);
});

for (const [label, make] of [
  ['200 HTML', () => response(200, '<h1>application</h1>')],
  ['401', () => response(401)], ['403', () => response(403)],
  ['unknown 500', () => response(500)],
  ...[301,303,307,308].map(status => ['non302 redirect '+status, () => response(status, '', login)]),
  ['foreign redirect', () => response(302, '', 'https://evil.test/cdn-cgi/access/login')],
  ['userinfo', () => response(302, '', login.replace('https://', 'https://user:secret@'))],
  ['team path mismatch', () => response(302, '', login.replace('/cdn-cgi/access/', '/other/'))],
  ['suffix hostname', () => response(302, '', login.replace('.com/', '.com.evil.test/'))],
  ['relative redirect', () => response(302, '', '/cdn-cgi/access/login')],
  ['404 JSON', () => response(404, '{"error":"NOT_FOUND"}')],
  ['404 JSON MIME', () => new Response('', {status: 404, headers: {'content-type': 'application/json'}})],
  ['redirect containing app body', () => response(302, '<main data-research-thread>private</main>', login)],
  ['404 Worker app error', () => response(404, 'STAGING_ACCESS_DENIED')],
  ['resource limit response', () => response(404, 'Error 1102')],
  ['oversize body', () => response(404, 'x'.repeat(65537))],
]) test('readiness rejects ' + label + ' and closes without sending credentials', async () => {
  const g = guard(async () => make()), r = await g.run();
  assert.equal(r.result, 'STOP'); assert.equal(r.readiness.observations.length, 1);
  assert.deepEqual(g.calls, {unauth: 0, auth: 0, close: 1});
});

test('followed redirects cannot be accepted as Access protection', async () => {
  const r = ready(); Object.defineProperty(r, 'redirected', {value: true});
  const g = guard(async () => r), result = await g.run();
  assert.equal(result.reason, 'REDIRECT_WAS_FOLLOWED'); assert.equal(g.calls.auth, 0);
});

test('secrets in body, headers, redirect query and thrown exception are never serialized', async () => {
  const secret = 'VERY_PRIVATE_VALUE';
  const g = guard(async () => response(302, secret, login + '&secret=' + secret));
  const r = await g.run(), serialized = JSON.stringify(r);
  assert.equal(serialized.includes(secret), false); assert.equal(serialized.includes('DO_NOT_LOG'), false);
  assert.match(r.readiness.observations[0].body_sha256, /^[a-f0-9]{64}$/);
  const failure = await guard(async () => {throw Error(secret);}).run();
  assert.equal(failure.reason, 'REQUEST_FAILED'); assert.equal(JSON.stringify(failure).includes(secret), false);
});

test('hanging response body times out and closes; no redirect following or retry', async () => {
  let cancelled = false;
  const g = guard(async () => new Response(new ReadableStream({cancel() {cancelled = true;}}), {status: 404}), {requestMs: 10});
  const r = await g.run();
  assert.equal(r.reason, 'REQUEST_TIMEOUT'); assert.equal(g.calls.auth, 0); assert.equal(g.calls.close, 1);
  assert.equal(cancelled, true);
});

test('network timeout still closes when the injected request ignores its AbortSignal', async () => {
  const g = guard(async () => new Promise(() => {}), {requestMs: 10});
  const r = await g.run(); assert.equal(r.reason, 'REQUEST_TIMEOUT'); assert.equal(g.calls.close, 1);
});

test('readiness never replaces the full unauthenticated gate', async () => {
  const g = guard(async () => ready(), {verifyUnauthenticated: async () => false});
  const r = await g.run(); assert.equal(r.reason, 'UNAUTHENTICATED_GATE_FAILED');
  assert.equal(g.calls.auth, 0); assert.equal(g.calls.close, 1);
});

test('unauthenticated and authenticated exceptions close without leaking exception text', async () => {
  for (const phase of ['verifyUnauthenticated', 'runAuthenticated']) {
    const g = guard(async () => ready(), {[phase]: async () => {throw Error('private');}});
    const r = await g.run(); assert.equal(r.reason, 'PHASE_EXCEPTION');
    assert.equal(r.closure_verified, true); assert.equal(JSON.stringify(r).includes('private'), false);
    if (phase === 'verifyUnauthenticated') assert.equal(g.calls.auth, 0);
  }
});

test('closure failure overrides success while retaining the preceding failure', async () => {
  for (const close of [async () => false, async () => {throw Error('private');}]) {
    const g = guard(async () => ready(), {close});
    const r = await g.run(); assert.equal(r.result, 'STOP'); assert.equal(r.reason, 'CLOSURE_UNCONFIRMED');
    assert.equal(r.closure_verified, false);
  }
  const r = await guard(async () => response(404), {close: async () => false}).run();
  assert.equal(r.phase_reason, 'HTTP_404_REPEATED');
});

test('bounds cannot be enlarged and missing closure cannot start a probe', async () => {
  for (const options of [{budgetMs: 15001}, {requestMs: 4001}, {intervalMs: 3001}, {maxObservations: 4}, {maxObservations: 0}]) {
    const g = guard(async () => {assert.fail('no request');}, options);
    const r = await g.run(); assert.equal(r.reason, 'PHASE_EXCEPTION'); assert.equal(g.calls.close, 1);
  }
  await assert.rejects(runGuardedReadiness({request: async () => assert.fail('no request')}), /REQUIRED_GUARD_MISSING/);
});
