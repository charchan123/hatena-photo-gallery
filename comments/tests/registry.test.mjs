import test from "node:test";
import assert from "node:assert/strict";
import registry from "../cases.json" with { type: "json" };
import manifest from "../staging/manifest.json" with { type: "json" };
import { createRegistryChecker } from "../staging/registry.mjs";
import { stagingFixture } from "./staging-fixture.mjs";
import { canonical, digest } from "../worker.mjs";

test("67 bundled hashes initialize once; every warm request still reads all three D1 tables", async t => {
  const s = await stagingFixture(), check = createRegistryChecker(registry, manifest);
  const native = crypto.subtle.digest.bind(crypto.subtle);
  let hashes = 0, reads = [];
  t.mock.method(crypto.subtle, "digest", (...args) => { hashes++; return native(...args); });
  const prepare = s.db.prepare.bind(s.db);
  t.mock.method(s.db, "prepare", sql => { reads.push(sql); return prepare(sql); });
  await Promise.all([check(s.env), check(s.env), check(s.env)]);
  assert.equal(hashes, 67, "concurrent initialization has one shared promise");
  assert.equal(reads.length, 9);
  reads = [];
  await check(s.env);
  assert.equal(hashes, 67, "zero additional SHA calls on warm requests");
  assert.deepEqual(reads, ["SELECT key,value FROM metadata",
    "SELECT id,identity_hash FROM cases ORDER BY id", "SELECT alias,case_id FROM aliases ORDER BY alias"]);
});

test("bundled registry and manifest corruption fails initialization and stays failed", async () => {
  const s = await stagingFixture();
  const altered = structuredClone(registry); altered.cases[0].observation_ids.push("unreviewed-photo");
  const badInputs = [
    [altered, manifest],
    [registry, {...manifest, version: 2}],
    [registry, {...manifest, active_ids: manifest.active_ids.slice(1)}],
    [registry, {...manifest, registry_sha256: "0".repeat(64)}],
  ];
  for (const [r,m] of badInputs) {
    const check = createRegistryChecker(r,m);
    await assert.rejects(check(s.env), /STAGING_REGISTRY_MISMATCH/);
    await assert.rejects(check(s.env), /STAGING_REGISTRY_MISMATCH/);
  }
  // Even a self-consistent changed bundle cannot use the reviewed DB.
  const idsChanged = structuredClone(registry); idsChanged.cases[0].observation_ids.push("other-photo");
  const m = {...manifest, registry_sha256: await digest(canonical(idsChanged))};
  await assert.rejects(createRegistryChecker(idsChanged,m)(s.env), /STAGING_REGISTRY_MISMATCH/);
});

test("warm worker rejects metadata, case and alias tampering on the very next request", async t => {
  const mutations = [
    "UPDATE metadata SET value='2' WHERE key='schema_version'",
    "DELETE FROM metadata WHERE key='registry_sha256'",
    "UPDATE metadata SET value='wrong' WHERE key='installation_id'",
    "UPDATE metadata SET value='wrong' WHERE key='registry_sha256'",
    "DROP TRIGGER immutable_case_anchor; UPDATE cases SET identity_hash='"+"0".repeat(64)+"' WHERE id=(SELECT min(id) FROM cases)",
    "INSERT INTO cases VALUES('research-0000000000000000','synthetic','"+"0".repeat(64)+"')",
    "DROP TRIGGER retain_alias; DELETE FROM aliases WHERE case_id=(SELECT min(id) FROM cases); DELETE FROM cases WHERE id=(SELECT min(id) FROM cases)",
    "DROP TRIGGER immutable_alias; UPDATE aliases SET case_id=(SELECT max(id) FROM cases) WHERE alias=(SELECT min(alias) FROM aliases)",
    "DROP TRIGGER retain_alias; DELETE FROM aliases WHERE alias=(SELECT min(alias) FROM aliases)",
    "INSERT INTO aliases VALUES('research-0000000000000000',(SELECT min(id) FROM cases))",
  ];
  for (const mutation of mutations) {
    const s=await stagingFixture(); t.mock.method(globalThis,"fetch",s.certFetch);
    const token=await s.sign();
    assert.equal((await s.call('/',{token})).status,200);
    // Dropping a trigger here simulates storage corruption in this disposable
    // in-memory database; no deployed trigger or production schema is changed.
    s.db.sql.exec(mutation);
    for (const path of ['/',s.route,'/admin/cases'])
      assert.equal((await s.call(path,{token})).status,503,mutation);
    assert.equal(s.db.sql.prepare('SELECT count(*) n FROM comments').get().n,0);
    s.db.sql.close();
  }
});

test("warm JWT verification is never replaced by an authentication cache", async t => {
  const s=await stagingFixture(); t.mock.method(globalThis,"fetch",s.certFetch);
  const token=await s.sign();
  const verify=crypto.subtle.verify.bind(crypto.subtle); let count=0;
  t.mock.method(crypto.subtle,"verify",(...args)=>{count++;return verify(...args);});
  assert.equal((await s.call('/',{token})).status,200);
  assert.equal((await s.call('/',{token})).status,200);
  assert.equal(count,2,"RS256 verified on both requests despite warm JWKS and registry");
  for (const claims of [{exp:1},{iss:'https://wrong.cloudflareaccess.com'},
      {aud:'b'.repeat(64)},{iat:Math.floor(Date.now()/1000)+600}])
    assert.equal((await s.call('/',{token:await s.sign(claims)})).status,403);
  s.env.ACCESS_AUD='b'.repeat(64);
  assert.equal((await s.call('/',{token})).status,403);
});
