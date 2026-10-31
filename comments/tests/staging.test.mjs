import test from "node:test";
import assert from "node:assert/strict";
import { generateKeyPair, SignJWT } from "jose";
import { stagingFixture, ORIGIN, ISSUER, AUD, ADMIN } from "./staging-fixture.mjs";
import { createWorker } from "../worker.mjs";

async function setup(t) {const s=await stagingFixture();t.mock.method(globalThis,"fetch",s.certFetch);return s;}

test("JWT required on UI, assets, config, manifest, public/admin API and OPTIONS",async t=>{
  const s=await setup(t);
  for(const path of ['/','/research.html','/assets/research-comments.js','/assets/research.css','/assets/staging.css','/assets/synthetic.svg','/assets/unknown.json','/research-comments-config.json','/research-comment-cases.json',s.route,'/admin/cases']) {
    for(const token of [undefined,'forged.token.signature']) assert.equal((await s.call(path,{token})).status,403,path);
  }
  assert.equal((await s.call(s.route,{method:'OPTIONS',headers:{Origin:ORIGIN}})).status,403);
  assert.equal(s.certCalls.length,0);assert.equal(s.outbound.length,0);
  assert.equal(s.db.sql.prepare('SELECT count(*) n FROM limits').get().n,0);
});

test("signed valid user and service assertions pass; cached keys fetched only from pinned team",async t=>{
  const s=await setup(t),token=await s.sign();
  for(const path of ['/','/assets/research-comments.js','/research-comment-cases.json',s.route]) assert.equal((await s.call(path,{token})).status,200,path);
  assert.equal((await s.call('/admin/cases',{token,headers:{Authorization:'Bearer '+ADMIN}})).status,200);
  assert.equal((await s.call('/admin/cases',{token})).status,401,'Access alone is not app administration');
  assert.equal((await s.call('/admin/cases',{headers:{Authorization:'Bearer '+ADMIN}})).status,403,'Bearer alone is not Access');
  assert.deepEqual(s.certCalls,[ISSUER+'/cdn-cgi/access/certs']);
});

test("expired, missing claims, future times, wrong issuer/aud, unknown key and forged signatures reject",async t=>{
  const s=await setup(t),now=Math.floor(Date.now()/1000);
  const {privateKey:wrong}=await generateKeyPair('RS256');
  const tokens=await Promise.all([
    s.sign({exp:now-1}),s.sign({exp:undefined}),s.sign({iat:undefined}),s.sign({iat:now+600}),s.sign({nbf:now+600}),
    s.sign({aud:'b'.repeat(64)}),s.sign({iss:'https://evil.test'}),s.sign({},wrong),s.sign({},undefined,{kid:'evil',jku:'https://evil.test/keys'}),
  ]);
  const unsigned='eyJhbGciOiJub25lIn0.'+Buffer.from(JSON.stringify({iss:ISSUER,aud:[AUD],exp:now+300})).toString('base64url')+'.';
  for(const token of [...tokens,unsigned]) assert.equal((await s.call('/',{token})).status,403);
  assert.ok(s.certCalls.every(u=>u===ISSUER+'/cdn-cgi/access/certs'));
});

test("missing config and wrong origin remain closed even with valid JWT",async t=>{
  const s=await setup(t),token=await s.sign(),original={...s.env};
  for(const [k,v] of Object.entries({ENVIRONMENT:'production',STAGING_ORIGIN:'https://production.example.test',ACCESS_TEAM_DOMAIN:'https://evil.test',ACCESS_AUD:'',ALLOWED_ORIGINS:'*',TURNSTILE_HOSTNAME:'charchan123.github.io',MANIFEST_URL:'https://evil.test',STAGING_INSTALLATION_ID:'',REGISTRY_SHA256:'0'.repeat(64)})) {
    s.env[k]=v;assert.equal((await s.call('/',{token})).status,403,k);Object.assign(s.env,original);
  }
  const req=new Request('https://preview.fixture.workers.dev/research.html',{headers:{'Cf-Access-Jwt-Assertion':token}});
  assert.equal((await s.worker.fetch(req,s.env)).status,403);
});

test("frozen IDs/anchors/aliases and DB installation must all match before any operation",async t=>{
  const s=await setup(t),token=await s.sign();
  for(const [key,value] of [['installation_id','0'.repeat(32)],['registry_sha256','0'.repeat(64)]]){
    const old=s.db.sql.prepare('SELECT value FROM metadata WHERE key=?').get(key).value;
    s.db.sql.prepare('UPDATE metadata SET value=? WHERE key=?').run(value,key);
    assert.equal((await s.call(s.route,{token,body:s.packet()})).status,503);
    s.db.sql.prepare('UPDATE metadata SET value=? WHERE key=?').run(old,key);
  }
  s.db.sql.prepare('INSERT INTO cases(id,label,identity_hash) VALUES(?,?,?)').run('research-0000000000000000','synthetic','0'.repeat(64));
  assert.equal((await s.call('/',{token})).status,503);
  assert.equal(s.db.sql.prepare('SELECT count(*) n FROM comments').get().n,0);
});

test("unreviewed alias additions cannot attach a case to another thread",async t=>{
  const s=await setup(t),token=await s.sign();
  s.db.sql.prepare('INSERT INTO aliases(alias,case_id) VALUES(?,?)').run('research-0000000000000000',s.id);
  assert.equal((await s.call('/',{token})).status,503);
  assert.equal((await s.call('/admin/cases',{token,headers:{Authorization:'Bearer '+ADMIN}})).status,503);
});

test("same-origin CORS, strict JSON and admin Origin restrictions are retained",async t=>{
  const s=await setup(t),token=await s.sign();
  for(const method of ['GET','OPTIONS']) assert.equal((await s.call(s.route,{token,method,headers:{Origin:'https://evil.test'}})).status,403);
  const preflight=await s.call(s.route,{token,method:'OPTIONS',headers:{Origin:ORIGIN}});
  assert.equal(preflight.status,204);assert.equal(preflight.headers.get('Access-Control-Allow-Origin'),ORIGIN);
  assert.equal(preflight.headers.get('Access-Control-Allow-Credentials'),null);
  assert.equal((await s.call('/admin/cases',{token,headers:{Authorization:'Bearer '+ADMIN,Origin:ORIGIN}})).status,401);
  assert.equal((await s.call('/assets/other-secret.json',{token})).status,404);
});

test("posting uses bundled case manifest; replay, quotas and 500-character guards remain",async t=>{
  const s=await setup(t),token=await s.sign(),body=s.packet();
  body.body="<img src=x onerror=alert(1)>'); DROP TABLE comments;--";
  const first=await (await s.call(s.route,{token,body})).json();assert.ok(first.comment.id);
  const again=await (await s.call(s.route,{token,body})).json();assert.equal(first.comment.id,again.comment.id);
  assert.equal((await s.call(s.route,{token,body:{...s.packet(),body:'x'.repeat(501)}})).status,400);
  assert.deepEqual(s.outbound,['https://challenges.cloudflare.com/turnstile/v0/siteverify']);
  const del=s.route+'/'+first.comment.id+'/delete';
  // The unchanged shared quota also applies to deletion requests.
  assert.equal((await s.call(del,{token,body:{delete_token:'f'.repeat(64)},headers:{'CF-Connecting-IP':'198.51.100.25'}})).status,429);
  assert.equal(s.db.sql.prepare('SELECT count(*) n FROM comments').get().n,1);
});

test("author deletion still requires its token and cannot be replayed",async t=>{
  const s=await setup(t),token=await s.sign(),body=s.packet();
  const first=await (await s.call(s.route,{token,body})).json();
  const del=s.route+'/'+first.comment.id+'/delete';
  assert.equal((await s.call(del,{token,body:{delete_token:'f'.repeat(64)}})).status,403);
  assert.equal((await s.call(del,{token,body:{delete_token:body.delete_token}})).status,200);
  const row=s.db.sql.prepare('SELECT * FROM comments WHERE id=?').get(first.comment.id);
  assert.equal(row.state,'deleted');assert.equal(row.body,null);assert.equal(row.delete_hash,null);
});

test("flags, failed human verification, JWT authority failure, DB and asset outages fail closed",async t=>{
  const s=await setup(t),token=await s.sign();
  s.env.PUBLIC_READ_ENABLED='false';s.env.PUBLIC_WRITE_ENABLED='false';s.env.RELEASE_APPROVAL='not-approved';
  const config=await (await s.call('/research-comments-config.json',{token})).json();assert.equal(config.enabled,false);
  assert.equal((await s.call(s.route,{token})).status,503);
  assert.equal((await s.call(s.route,{token,body:s.packet()})).status,503);
  s.env.PUBLIC_READ_ENABLED='true';s.env.PUBLIC_WRITE_ENABLED='true';s.env.RELEASE_APPROVAL='approved';s.human(false);
  assert.equal((await s.call(s.route,{token,body:s.packet()})).status,400);
  assert.equal(s.db.sql.prepare('SELECT count(*) n FROM comments').get().n,0);
  s.env.DB={prepare(){throw Error('private SQL details')}};
  assert.deepEqual(await (await s.call('/',{token})).json(),{error:'STAGING_UNAVAILABLE'});
  s.env.DB=s.db;s.env.ASSETS={fetch(){throw Error('asset failure')}};
  assert.equal((await s.call('/',{token})).status,503);
  const other=await stagingFixture();other.outage(true);t.mock.method(globalThis,'fetch',other.certFetch);
  assert.equal((await other.call('/',{token:await other.sign()})).status,403);
});

test("production still rejects staging manifest URL and preserves fixed Pages constraint",async()=>{
  const s=await stagingFixture(),worker=createWorker({fetcher:async()=>{assert.fail('must not fetch staging manifest from production')}});
  const r=await worker.fetch(new Request(ORIGIN+s.route,{method:'POST',headers:{Origin:ORIGIN,'Content-Type':'application/json','CF-Connecting-IP':'198.51.100.5'},body:JSON.stringify(s.packet())}),s.env);
  assert.equal(r.status,503);assert.equal((await r.json()).error,'MANIFEST_CONFIGURATION');
});
