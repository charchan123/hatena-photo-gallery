// Test-only authority and in-memory DB. No real cookies, credentials or CF calls.
import { generateKeyPair, exportJWK, SignJWT } from "jose";
import { LocalD1 } from "./d1.mjs";
import { createStagingWorker } from "../staging/worker.mjs";
export const ORIGIN = "https://kinoko-comments-staging-test.fixture.workers.dev";
export const ISSUER = "https://synthetic-test.cloudflareaccess.com";
export const AUD = "a".repeat(64);
export const ADMIN = "synthetic-admin-secret-".repeat(3);
export const ACCESS_ID = "synthetic-test-id.access";
export const ACCESS_SECRET = "synthetic-service-key-".repeat(3);
export async function stagingFixture() {
  const db = new LocalD1();
  const { publicKey, privateKey } = await generateKeyPair("RS256", { extractable: true });
  const jwk = { ...await exportJWK(publicKey), kid: "synthetic-rsa", alg: "RS256", use: "sig" };
  let human = true, outage = false;
  const certCalls = [], outbound = [];
  const env = {
    DB: db, ENVIRONMENT: "staging", STAGING_ORIGIN: ORIGIN,
    STAGING_INSTALLATION_ID: db.sql.prepare("SELECT value FROM metadata WHERE key='installation_id'").get().value,
    REGISTRY_SHA256: db.sql.prepare("SELECT value FROM metadata WHERE key='registry_sha256'").get().value,
    ACCESS_TEAM_DOMAIN: ISSUER, ACCESS_AUD: AUD,
    ALLOWED_ORIGINS: ORIGIN, TURNSTILE_HOSTNAME: new URL(ORIGIN).hostname,
    TURNSTILE_SECRET: "synthetic-turnstile-secret-".repeat(3), TURNSTILE_SITE_KEY: "synthetic-site-key",
    ADMIN_TOKEN: ADMIN, RATE_SECRET: "synthetic-rate-secret-".repeat(3),
    PUBLIC_READ_ENABLED: "true", PUBLIC_WRITE_ENABLED: "true", RELEASE_APPROVAL: "approved",
    MANIFEST_URL: "staging:bundled",
    ASSETS: { fetch: async () => new Response("synthetic asset") },
  };
  const worker = createStagingWorker({fetcher: async (url) => {
    outbound.push(String(url));
    if (outage) throw Error("synthetic unavailable");
    if (String(url)!=="https://challenges.cloudflare.com/turnstile/v0/siteverify") throw Error("external manifest forbidden");
    return Response.json({success:human,hostname:env.TURNSTILE_HOSTNAME,action:"research_comment",challenge_ts:new Date().toISOString()});
  }});
  const certFetch = async (url, options) => {
    certCalls.push(String(url));
    if (outage || String(url)!==ISSUER+"/cdn-cgi/access/certs" || options.redirect!=="manual") throw Error("unexpected authority fetch");
    return Response.json({keys:[jwk]});
  };
  const sign = (claims={}, key=privateKey, header={}) => new SignJWT({
    iss:ISSUER,aud:[AUD],sub:"synthetic",iat:Math.floor(Date.now()/1000),exp:Math.floor(Date.now()/1000)+300,...claims,
  }).setProtectedHeader({alg:"RS256",kid:jwk.kid,...header}).sign(key);
  const id = db.sql.prepare("SELECT id FROM cases ORDER BY id").get().id;
  const route = "/v1/cases/"+id+"/comments";
  const call = async (path, {token,body,method=body ? "POST":"GET",headers={}}={}) => {
    const h=new Headers(headers);
    h.set("CF-Connecting-IP","198.51.100.24");
    if (token) h.set("Cf-Access-Jwt-Assertion",token);
    if (body) {h.set("Content-Type","application/json");if(!path.startsWith('/admin/')) h.set("Origin",ORIGIN);}
    return worker.fetch(new Request(ORIGIN+path,{method,headers:h,body:body?JSON.stringify(body):undefined}),env);
  };
  const packet = () => ({request_id:crypto.randomUUID(),nickname:"森の試験参加者",body:"合成コメント",delete_token:"e".repeat(64),turnstile_token:"synthetic-human"});
  return {db, env, worker, certFetch, certCalls, outbound, sign, id, route, call, packet,
    human:v=>human=v,outage:v=>outage=v};
}
