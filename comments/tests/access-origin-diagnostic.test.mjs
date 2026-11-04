import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, writeFileSync, readFileSync, readdirSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {runOriginDiagnostic} from '../tools/access-origin-diagnostic.mjs';
import {diagnosticHeaders, waitForAccessReadiness, runGuardedReadiness, verifyUnauthenticatedRoot,
  READINESS_ORIGIN} from '../tools/access-readiness.mjs';
import {validateAccessSnapshot} from '../staging/access-snapshot.mjs';

const LOGIN='https://floral-silence-7565.cloudflareaccess.com/cdn-cgi/access/login?private=not-for-audit';
const response=(status=302,body='',headers={})=>new Response(body,{status,headers:{
  'content-type':'text/html',...(status===302?{location:LOGIN}:{}),...headers}});
function clock(){let n=0;return {now:()=>n,sleep:async ms=>{n+=ms;},utcNow:()=>new Date(1800000000000+n).toISOString()};}
async function attempt(t, statuses, overrides={}) {
  const dir=mkdtempSync(join(tmpdir(),'kinoko-offline-origin-'));
  t.after(()=>rmSync(dir,{recursive:true,force:true}));
  const calls={requests:0,closed:0,preflight:0,auth:0};
  const options={...clock(),attemptDirectory:dir,
    preflight:async()=>{calls.preflight++;return true;},
    request:async(url,o)=>{assert.equal(url,READINESS_ORIGIN+'/');
      assert.deepEqual(o.headers,{});assert.equal(o.credentials,'omit');
      assert.equal(o.redirect,'manual');assert.equal(o.cache,'no-store');
      const status=statuses[calls.requests++];assert.ok(status,'no extra request');return response(status);},
    close:async()=>{calls.closed++;return true;},
    runAuthenticated:async()=>{calls.auth++;assert.fail('diagnostic cannot send credentials');},...overrides};
  return {dir,calls,options,report:await runOriginDiagnostic(options)};
}

test('continuous302: 3 readiness observations plus independent root, no authenticated phase',async t=>{
  const {report:r,calls}=await attempt(t,[302,302,302,302]);
  assert.equal(r.result,'UNAUTHENTICATED_ROOT_WINDOW_COMPLETE');
  assert.equal(r.readiness.security_tests_passed,0);assert.equal(r.tests.length,1);
  assert.equal(r.tests[0].pass,true);assert.equal(r.authenticated_requests,0);
  assert.deepEqual(calls,{requests:4,closed:1,preflight:1,auth:0});
});
test('saved404-302-404 sequence stops in readiness before independent gate or credentials',async t=>{
  const {report:r,calls}=await attempt(t,[404,302,404]);
  assert.equal(r.reason,'ACCESS_REDIRECT_REGRESSED_TO_404');
  assert.deepEqual(r.readiness.observations.map(x=>x.status),[404,302,404]);
  assert.equal(r.tests.length,0);assert.equal(r.authenticated_requests,0);
  assert.equal(calls.requests,3);assert.equal(calls.closed,1);assert.equal(calls.auth,0);
});
test('404 only is bounded to3 and never qualifies as a security refusal',async t=>{
  const {report:r,calls}=await attempt(t,[404,404,404]);
  assert.equal(r.reason,'READINESS_NOT_ESTABLISHED');assert.equal(calls.requests,3);
  assert.equal(r.tests.length,0);assert.equal(r.closure_verified,true);
});
test('404 followed by only2 redirects never establishes the3-redirect window',async t=>{
  const {report:r}=await attempt(t,[404,302,302]);
  assert.equal(r.reason,'READINESS_NOT_ESTABLISHED');assert.equal(r.readiness.consecutive_access_redirects,2);
});
test('independent root404 after a complete readiness window stops and closes',async t=>{
  const {report:r,calls}=await attempt(t,[302,302,302,404]);
  assert.equal(r.reason,'UNAUTHENTICATED_GATE_FAILED');assert.equal(r.tests[0].pass,false);
  assert.equal(r.authenticated_requests,0);assert.equal(calls.closed,1);
});
test('the authenticated runner also refuses an independent root regression',async()=>{
  const c=clock();let auth=0,closed=0;
  const r=await runGuardedReadiness({...c,request:async()=>response(),
    verifyUnauthenticated:async()=> (await verifyUnauthenticatedRoot({...c,request:async()=>response(404)})).pass,
    runAuthenticated:async()=>{auth++;return true;},close:async()=>{closed++;return true;}});
  assert.equal(r.reason,'UNAUTHENTICATED_GATE_FAILED');assert.equal(auth,0);assert.equal(closed,1);
});
for(const [label,make] of [
  ['foreign redirect',()=>response(302,'',{location:'https://evil.invalid/login?secret=redact'})],
  ['same team wrong Access path',()=>response(302,'',{location:LOGIN.replace('/login','/certs')})],
  ['wrong hostname in login path',()=>response(302,'',{location:LOGIN.replace('/login?','/login/another.workers.dev?')})],
  ['unexpected HTML',()=>response(200,'<html>private page</html>')],
  ['application JSON',()=>response(404,'{"active_ids":["private"]}')],
  ['error headers',()=>response(404,'',{'cf-error-type':'1102','cf-error-origin':'workers'})],
  ['mitigation challenge',()=>response(302,'',{'cf-mitigated':'challenge'})],
]) test(label+' stops with no credentials',async t=>{
  let n=0;
  const {report:r,calls}=await attempt(t,[],{request:async()=>{n++;return make();}});
  assert.equal(r.result,'STOP');assert.equal(n,1);assert.equal(calls.closed,1);assert.equal(calls.auth,0);
});
test('timeout between redirects closes, without recording exception or retrying',async t=>{
  let n=0;
  const {report:r,calls}=await attempt(t,[],{requestMs:10,request:async()=>{
    if(n++===0)return response();return new Promise(()=>{});
  }});
  assert.equal(r.reason,'REQUEST_TIMEOUT');assert.equal(n,2);assert.equal(calls.closed,1);
});
test('closure failure overrides success or regression and preserves phase reason',async t=>{
  for(const statuses of [[302,302,302,302],[404,302,404]]) {
    const {report:r}=await attempt(t,statuses,{close:async()=>false});
    assert.equal(r.reason,'CLOSURE_UNCONFIRMED');assert.equal(r.result,'STOP');assert.equal(r.closure_verified,false);
    if(statuses[0]===404)assert.equal(r.phase_reason,'ACCESS_REDIRECT_REGRESSED_TO_404');
  }
});
test('real offline Access validator mismatch prevents any request, then verifies closure',async t=>{
  const expected={appId:'fixture',workerTag:'worker',aud:'a'.repeat(64),ownerPolicyId:'owner',servicePolicyId:'service',tokenId:'token',ownerEmail:'synthetic@example.invalid'};
  const app={id:'fixture',type:'self_hosted',aud:expected.aud,destinations:[{type:'worker',worker_id:'worker'}]};
  const policies=[{id:'owner',decision:'allow',include:[{everyone:{}}]},
    {id:'service',decision:'non_identity',include:[{service_token:{token_id:'token'}}]}];
  const {report:r,calls}=await attempt(t,[],{preflight:async()=>validateAccessSnapshot(app,policies,expected)});
  assert.equal(r.reason,'ACCESS_CONFIGURATION_MISMATCH');assert.equal(calls.requests,0);
  assert.equal(calls.closed,1);assert.equal(r.closure_verified,true);
});
test('attempt marker is exclusive and old proof bytes are never changed',async t=>{
  const x=await attempt(t,[302,302,302,302]);
  const before=readdirSync(x.dir).map(n=>[n,readFileSync(join(x.dir,n),'utf8')]);
  const r=await runOriginDiagnostic(x.options);
  assert.equal(r.reason,'ATTEMPT_EXISTS_NO_RETRY');assert.equal(x.calls.requests,4);
  assert.deepEqual(readdirSync(x.dir).map(n=>[n,readFileSync(join(x.dir,n),'utf8')]),before);
  const dir=mkdtempSync(join(tmpdir(),'kinoko-old-attempt-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));
  writeFileSync(join(dir,'nov4-first-attempt.local.json'),'retained old marker');
  const old=await runOriginDiagnostic({...x.options,attemptDirectory:dir});
  assert.equal(old.reason,'ATTEMPT_EXISTS_NO_RETRY');assert.deepEqual(readdirSync(dir),['nov4-first-attempt.local.json']);
});
test('diagnostic headers are a bounded allowlist, not an arbitrary header dump',()=>{
  const h=new Headers({'server':'cloudflare','cf-ray':'0123456789abcdef-NRT','cf-error-type':'1102',
    'cf-error-origin':'workers','cf-cache-status':'HIT','age':'12','set-cookie':'PRIVATE_COOKIE',
    location:'https://private.invalid/?jwt=PRIVATE_JWT','authorization':'PRIVATE_BEARER',
    'cf-access-client-secret':'PRIVATE_SERVICE','x-email':'PRIVATE_EMAIL','server-timing':'PRIVATE_TIMING'});
  const d=diagnosticHeaders(h);assert.equal(d.cf_ray,'0123456789abcdef-NRT');
  assert.equal(d.age_seconds,12);assert.equal(d.cf_cache_status,'hit');assert.equal(d.worker_execution,'not-established');
  assert.equal(JSON.stringify(d).includes('PRIVATE_'),false);
  for(const name of ['server','cf-ray','cf-error-type','cf-error-origin','cf-cache-status','age','cf-mitigated'])h.set(name,'PRIVATE_'+name);
  assert.equal(JSON.stringify(diagnosticHeaders(h)).includes('PRIVATE_'),false);
});
test('timestamps, hashes and header classifications persist without HTML/Location/cookie',async()=>{
  const c=clock();
  const r=await waitForAccessReadiness({...c,request:async()=>response(404,'private-body',{
    'set-cookie':'PRIVATE_COOKIE','cf-ray':'0123456789abcdef-NRT'})});
  const o=r.observations[0];assert.equal(o.started_at,'2027-01-15T08:00:00.000Z');
  assert.equal(o.completed_at,o.started_at);assert.equal(o.wall_is_not_cpu,true);
  assert.match(o.body_sha256,/^[a-f0-9]{64}$/);assert.equal(o.body_bytes,12);
  assert.equal(o.diagnostic_headers.worker_execution,'not-established');
  assert.equal(JSON.stringify(r).includes('private-body'),false);assert.equal(JSON.stringify(r).includes('PRIVATE_COOKIE'),false);
  assert.equal(JSON.stringify(r).includes('not-for-audit'),false);
});
