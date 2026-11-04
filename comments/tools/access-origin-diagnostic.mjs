// Offline adapter for a FUTURE separately approved Windows runner. No default
// fetch, API client, credentials, URL toggle, deployment or executable live CLI.
import {writeFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';
import {DIAGNOSTIC_PROTOCOL, waitForAccessReadiness, verifyUnauthenticatedRoot} from './access-readiness.mjs';

export async function runOriginDiagnostic({attemptDirectory, preflight, request, close, ...timing}) {
  if (typeof attemptDirectory !== 'string' || ![preflight, request, close].every(f => typeof f === 'function'))
    throw Error('DIAGNOSTIC_GUARD_MISSING');
  // Never reuse a directory containing any earlier attempt marker. Do not
  // remove/overwrite one or silently generate another directory on failure.
  if (readdirSync(attemptDirectory).some(n => /attempt.*\.json$/i.test(n)))
    return {protocol: DIAGNOSTIC_PROTOCOL, result: 'STOP', reason: 'ATTEMPT_EXISTS_NO_RETRY', authenticated_requests: 0};
  try {
    writeFileSync(join(attemptDirectory, DIAGNOSTIC_PROTOCOL + '.attempt.json'),
      JSON.stringify({protocol: DIAGNOSTIC_PROTOCOL, mode: 'unauthenticated-only'}) + '\n', {flag: 'wx'});
  } catch (e) {
    if (e.code !== 'EEXIST') throw e;
    return {protocol: DIAGNOSTIC_PROTOCOL, result: 'STOP', reason: 'ATTEMPT_EXISTS_NO_RETRY', authenticated_requests: 0};
  }
  const report = {protocol: DIAGNOSTIC_PROTOCOL, authenticated_requests: 0,
    scope: 'root-only; not full security approval or CPU measurement', tests: []};
  let preflightVerified = false;
  try {
    // The approved host runner owns strict Access/flags/version/scope/lease
    // checks and independent watchdog. A true return is required before any
    // HTTP. Configuration mismatch must never be "fixed" by this adapter.
    if (await preflight() !== true) throw Error('ACCESS_CONFIGURATION_MISMATCH');
    preflightVerified = true;
    report.readiness = await waitForAccessReadiness({request, ...timing});
    report.result = 'STOP'; report.reason = report.readiness.reason;
    if (report.readiness.state === 'ready') {
      const item = await verifyUnauthenticatedRoot({request, ...timing});
      report.tests.push(item);
      if (item.pass === true) {
        report.result = 'UNAUTHENTICATED_ROOT_WINDOW_COMPLETE'; delete report.reason;
      } else report.reason = 'UNAUTHENTICATED_GATE_FAILED';
    }
  } catch {
    report.result = 'STOP';
    report.reason = preflightVerified ? 'DIAGNOSTIC_EXCEPTION' : 'ACCESS_CONFIGURATION_MISMATCH';
  } finally {
    try {report.closure_verified = await close() === true;} catch {report.closure_verified = false;}
    if (!report.closure_verified) {
      report.phase_reason = report.reason || null;
      report.result = 'STOP'; report.reason = 'CLOSURE_UNCONFIRMED';
    }
  }
  return report;
}
