// Reused Nov4 pure guards only. No old CLI or expired deadline; five old services must remain disabled.
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {dirname, join, resolve} from 'node:path';
import {validateAccessSnapshot} from '../../staging/access-snapshot.mjs';

export const C=Object.freeze({
  account:'8b3955654c3eeda9f2679f594202a758',
  worker:'kinoko-comments-staging-20261031',
  tag:'b941a9738a4648af8ab9cb6eea9d149a',
  db:'d72f0156-30a9-45fb-ac6a-10720e6538fd',
  app:'1538aa3c-a7bf-4726-9b87-9c00f9de18e2',
  owner:'1f5bcb70-8c53-41ec-ae4f-d112e0bdafb2',
  service:'cd9418aa-6ac5-4e81-ad51-3a949539a997',
  oldService:'047a6297-3b2c-4838-9a3d-76c53c4f9944',
  aud:'3de669c3b9f16fa74e308a724aae8d1a92f404beccf5c02af330c66d25dd0a4f',
  origin:'https://kinoko-comments-staging-20261031.sasama-bb.workers.dev',
  team:'https://floral-silence-7565.cloudflareaccess.com',
  registry:'240e897c1edfddcef4d658f774885373be254c704c7f03b7535ac4f606bb10c5',
  head:'4fdb9bc70359c22f448cec02a864535984d41333',
});
const oldTokenIds=['6c2bd5ec-d52c-4eb9-a121-380799869151',
  '13ce816f-95fa-4000-b0d5-46a8290a8107','fee943c4-ccec-411a-b346-7883628d60a2',C.oldService,'dd2770d9-9d67-4d86-b40d-1207232c5653'].sort();
export const canonical=v=>v===null||typeof v!=='object'?JSON.stringify(v):
  Array.isArray(v)?'['+v.map(canonical).join(',')+']':
  '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';
const sha=v=>createHash('sha256').update(v).digest('hex');
const need=(ok,code)=>{if(!ok)throw Error(code);};
const same=(a,b,code)=>need(canonical(a)===canonical(b),code);
const ROOT=dirname(fileURLToPath(import.meta.url));
export const SQL=Object.freeze({
  metadata:'SELECT key,value FROM metadata ORDER BY key',
  cases:'SELECT id,identity_hash FROM cases ORDER BY id',
  aliases:'SELECT alias,case_id FROM aliases ORDER BY alias',
  migrations:'SELECT name FROM d1_migrations ORDER BY id',
  triggers:"SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name",
  foreignKeys:'PRAGMA foreign_key_check',
  counts:'SELECT (SELECT count(*) FROM comments) AS comments, (SELECT count(*) FROM requests) AS requests, (SELECT count(*) FROM reports) AS reports, (SELECT count(*) FROM audit) AS audit, (SELECT count(*) FROM limits) AS limits',
});
const allowGet=new Set([
  `/workers/scripts/${C.worker}/settings`, `/workers/scripts/${C.worker}/subdomain`,
  `/d1/database/${C.db}`, '/access/apps', '/access/service_tokens',
]);
export function requestGuard(path,method='GET',body){
  if(method==='GET'&&body===undefined&&allowGet.has(path))return;
  if(method==='GET'&&body===undefined&&/^\/access\/apps\/[a-f0-9-]{36}(?:\/policies)?$/.test(path))return;
  if(method==='POST'&&path===`/d1/database/${C.db}/query`&&body&&
    Object.keys(body).sort().join(',')==='params,sql'&&Array.isArray(body.params)&&
    body.params.length===0&&Object.values(SQL).includes(body.sql))return;
  throw Error('READ_ONLY_SCOPE_BLOCKED');
}
export function checkSettings(s,u){
  need(u.enabled===false&&u.previews_enabled===false,'URL_NOT_CLOSED');
  need(Array.isArray(s.bindings),'BINDINGS_INVALID');
  const b=s.bindings,v=Object.fromEntries(b.filter(x=>x.type==='plain_text').map(x=>[x.name,x.text]));
  need(new Set(b.map(x=>x.name)).size===b.length,'DUPLICATE_BINDING');
  for(const [k,want]of Object.entries({ENVIRONMENT:'staging',STAGING_ORIGIN:C.origin,
    ALLOWED_ORIGINS:C.origin,TURNSTILE_HOSTNAME:new URL(C.origin).hostname,
    ACCESS_TEAM_DOMAIN:C.team,ACCESS_AUD:C.aud,REGISTRY_SHA256:C.registry,
    MANIFEST_URL:'staging:bundled',PUBLIC_READ_ENABLED:'false',PUBLIC_WRITE_ENABLED:'false',
    RELEASE_APPROVAL:'not-approved'}))need(v[k]===want,'SETTING_'+k+'_MISMATCH');
  need(/^[a-f0-9]{32}$/.test(v.STAGING_INSTALLATION_ID||''),'INSTALLATION_INVALID');
  need(b.filter(x=>x.type==='d1').length===1&&b.find(x=>x.name==='DB')?.id===C.db,'DB_BINDING_MISMATCH');
  same(b.filter(x=>x.type==='secret_text').map(x=>x.name).sort(),
    ['ADMIN_TOKEN','RATE_SECRET','TURNSTILE_SECRET'],'SECRET_NAMES_MISMATCH');
  return v.STAGING_INSTALLATION_ID;
}
export function checkDb(s,expected,installation){
  same(s.metadata.map(x=>x.key),['installation_id','registry_sha256','schema_version'],'DB_METADATA_KEYS_MISMATCH');
  const m=Object.fromEntries(s.metadata.map(x=>[x.key,x.value]));
  need(m.installation_id===installation&&m.registry_sha256===C.registry&&m.schema_version==='1','DB_METADATA_MISMATCH');
  same(s.cases,expected.cases,'CASE_IDENTITY_MISMATCH');
  same(s.aliases,expected.aliases,'ALIAS_MISMATCH');
  same(s.migrations.map(x=>x.name),['0001_comments.sql','0002_guards.sql','0003_reviewed_cases.sql'],'MIGRATION_HISTORY_MISMATCH');
  same(s.triggers.map(x=>x.name),['immutable_alias','immutable_case_anchor','immutable_comment_identity','no_deleted_restore','official_reply_guard','retain_alias'],'GUARD_TRIGGERS_MISMATCH');
  same(s.foreignKeys,[],'FOREIGN_KEY_MISMATCH');
  need(s.counts.length===1,'COUNTS_INVALID');
  for(const k of ['comments','requests','reports','audit'])need(s.counts[0][k]===0,'BUSINESS_DATA_NOT_EMPTY');
  need(Number.isSafeInteger(s.counts[0].limits)&&s.counts[0].limits>=0,'LIMIT_COUNT_INVALID');
}
function domainMatches(value){
  if(typeof value!=='string'||!value)return false;
  let host=value.replace(/^https?:\/\//,'').split('/')[0].toLowerCase();
  const pattern='^'+host.replace(/[.+?^${}()|[\]\\]/g,'\\$&').replaceAll('*','.*')+'$';
  const exact=new URL(C.origin).hostname, preview='probe-'+exact;
  return new RegExp(pattern).test(exact)||new RegExp(pattern).test(preview);
}
export function checkOtherApps(apps){
  need(Array.isArray(apps)&&apps.filter(a=>a.id===C.app).length===1,'APP_INVENTORY_MISMATCH');
  for(const a of apps.filter(x=>x.id!==C.app)){
    need(!(a.destinations||[]).some(d=>d.type==='worker'&&[C.tag,'*'].includes(d.worker_id)),'OTHER_APP_TARGETS_WORKER');
    const domains=[a.domain,...(a.self_hosted_domains||[]),...(a.destinations||[]).filter(d=>d.type==='public').map(d=>d.uri||d.hostname)];
    need(!domains.some(domainMatches),'OVERRIDING_HOSTNAME_POLICY');
  }
}
export function checkTokens(tokens,now=Date.now()){
  same(tokens.map(t=>t.id).sort(),oldTokenIds,'TOKEN_INVENTORY_CHANGED');
  for(const t of tokens)need(t.enabled===false&&Number.isFinite(Date.parse(t.expires_at))&&Date.parse(t.expires_at)<now,'OLD_SERVICE_NOT_DISABLED_EXPIRED');
}
