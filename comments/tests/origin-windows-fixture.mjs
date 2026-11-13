// Test-only synthetic API state, with the preserved public-code receipt bytes.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {C,SQL,canonical} from '../tools/origin-windows/preflight.mjs';
import {VERSION} from '../tools/origin-windows/runner.mjs';
const DIR=dirname(fileURLToPath(import.meta.url));
export const NOW=Date.parse('2026-11-05T01:00:00Z');
export const TOKEN='synthetic-build-token-never-real-0000';
export const OWNER='synthetic-owner@example.invalid';
const digest=v=>createHash('sha256').update(canonical(v)).digest('hex');
export function fixture(root,scenario){
  const seed=JSON.parse(readFileSync(join(DIR,'../tools/origin-windows/expected-seed.json')));
  const code=gunzipSync(Buffer.from(readFileSync(join(DIR,'fixtures/staging-deployed-4fdb9bc.worker.gz.b64'),'utf8'),'base64'));
  if(createHash('sha256').update(code).digest('hex')!=='0f363c931bd791aaa92b1b89d513fa4709b0ce5504ab5c1c206043c6d847d68a')throw Error('fixture receipt changed');
  const owner={id:C.owner,decision:'allow',session_duration:'30m',include:[{email:{email:OWNER}}],require:[],exclude:[]};
  const service={id:C.service,decision:'non_identity',include:[{service_token:{token_id:C.oldService}}],require:[],exclude:[]};
  const app={id:C.app,type:'self_hosted',aud:C.aud,destinations:[{type:'worker',worker_id:C.tag}]};
  const other={id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',type:'self_hosted',domain:'existing.fixture.invalid'};
  const policies=[owner,service],otherPolicies=[];
  const baseline={owner_sha256:digest(owner),service_sha256:digest(service),app_sha256:digest(app),
    other_access_sha256:digest([{app:other,policies:otherPolicies}])};
  const values={ENVIRONMENT:'staging',STAGING_ORIGIN:C.origin,ALLOWED_ORIGINS:C.origin,TURNSTILE_HOSTNAME:new URL(C.origin).hostname,
    ACCESS_TEAM_DOMAIN:C.team,ACCESS_AUD:C.aud,REGISTRY_SHA256:C.registry,MANIFEST_URL:'staging:bundled',PUBLIC_READ_ENABLED:'false',
    PUBLIC_WRITE_ENABLED:'false',RELEASE_APPROVAL:'not-approved',STAGING_INSTALLATION_ID:'1'.repeat(32)};
  const bindings=Object.entries(values).map(([name,text])=>({type:'plain_text',name,text}));
  bindings.push({type:'assets',name:'ASSETS'},{type:'d1',name:'DB',id:C.db},...['ADMIN_TOKEN','RATE_SECRET','TURNSTILE_SECRET'].map(name=>({type:'secret_text',name})));
  const b='/workers/scripts/'+C.worker,counts={comments:0,requests:0,reports:0,audit:0,limits:0};
  const f={C,now:NOW,scenario,get:{},sql:{},code_base64:code.toString('base64')};
  f.get[b+'/settings']={bindings,compatibility_date:'2026-10-01',compatibility_flags:[]};
  f.get[b+'/deployments']={deployments:[{versions:[{version_id:VERSION,percentage:100}]}]};
  f.get['/workers/workers/'+C.worker+'/versions/'+VERSION]={id:VERSION,assets:{config:{run_worker_first:true}},bindings:[{type:'assets',name:'ASSETS'}]};
  f.get['/d1/database/'+C.db]={uuid:C.db,name:C.worker};
  f.get['/access/apps']=[app,other];f.get['/access/apps/'+C.app]=app;f.get['/access/apps/'+C.app+'/policies']=policies;
  f.get['/access/apps/'+other.id]=other;f.get['/access/apps/'+other.id+'/policies']=otherPolicies;
  f.get['/access/service_tokens']=['6c2bd5ec-d52c-4eb9-a121-380799869151','13ce816f-95fa-4000-b0d5-46a8290a8107',
    '047a6297-3b2c-4838-9a3d-76c53c4f9944','fee943c4-ccec-411a-b346-7883628d60a2','dd2770d9-9d67-4d86-b40d-1207232c5653']
    .map(id=>({id,enabled:false,expires_at:'2026-11-04T14:18:00Z'}));
  f.sql[SQL.metadata]=[{key:'installation_id',value:'1'.repeat(32)},{key:'registry_sha256',value:C.registry},{key:'schema_version',value:'1'}];
  f.sql[SQL.cases]=seed.cases;f.sql[SQL.aliases]=seed.aliases;
  f.sql[SQL.migrations]=['0001_comments.sql','0002_guards.sql','0003_reviewed_cases.sql'].map(name=>({name}));
  f.sql[SQL.triggers]=['immutable_alias','immutable_case_anchor','immutable_comment_identity','no_deleted_restore','official_reply_guard','retain_alias'].map(name=>({name}));
  f.sql[SQL.foreignKeys]=[];f.sql[SQL.counts]=[counts];
  const prior={result:'NOV4_READONLY_OK',urls_closed:true,version_id:VERSION,deployed_source_head:C.head,
    worker_first_verified:true,owner_exact:true,access_all_traffic:true,business_counts:counts,baseline};
  const evidence=join(root,'old-evidence');mkdirSync(evidence);
  const priorBytes=JSON.stringify(prior);writeFileSync(join(evidence,'nov4-readonly-report-1.json'),priorBytes);
  writeFileSync(join(evidence,'nov4-first-report-1.json'),JSON.stringify({result:'NOV4_FIRST_STOP',urls_closed:true,
    access_unchanged:true,d1_counts_unchanged:true,previous_proof_preserved:true,authenticated_requests:0,
    baseline_file:'nov4-readonly-report-1.json',baseline_sha256:createHash('sha256').update(priorBytes).digest('hex')}));
  writeFileSync(join(evidence,'nov4-first-attempt.local.json'),'retained old marker bytes');
  const approval={schema:1,approved:true,authorization_id:'0123456789abcdef',not_before_utc:'2026-11-05T00:59:00Z',
    expires_at_utc:'2026-11-05T01:29:00Z',api_token_id:'a'.repeat(32),api_token_name:'kinoko-comments-origin-diag-build-20261105',
    dashboard_checked_at_utc:'2026-11-05T00:59:30Z',github_pr_sha:'d'.repeat(40),github_main_sha:'b'.repeat(40),github_pages_sha:'c'.repeat(40),github_checked_at_utc:'2026-11-05T00:59:30Z',
    dashboard_checks:{workers_free:true,teams_free:true,single_worker_token_scope:true,pr138_worker_pages_unchanged:true,no_custom_domains_routes:true,production_comments_disabled:true}};
  return {f,approval,evidence};
}
