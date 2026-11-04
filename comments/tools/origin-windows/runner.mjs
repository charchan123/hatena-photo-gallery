// Prepared only: live modes require a separately approved, hash-bound lease.
// No deployment, D1 mutation, Access mutation, Service Auth or authenticated root.
import {readFileSync,writeFileSync,readdirSync,lstatSync,mkdirSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {fork} from 'node:child_process';
import {C,SQL,canonical,checkSettings,checkDb,checkOtherApps,checkTokens} from './preflight.mjs';
import {codeReceipt,deployedVersion} from './code-receipt.mjs';
import {validateAccessSnapshot} from '../../staging/access-snapshot.mjs';
import {runOriginDiagnostic} from '../access-origin-diagnostic.mjs';

const DIR=dirname(fileURLToPath(import.meta.url)),SELF=fileURLToPath(import.meta.url),ROOT=resolve(DIR,'../../..');
export const VERSION='6ff1d822-8419-47e7-8c46-15c1d4282493';
export const PROTOCOL='origin-windows-v1';
export const WATCHDOG_MS=90000;
export const FILES=[
  'comments/tools/origin-windows/runner.mjs','comments/tools/origin-windows/preflight.mjs',
  'comments/tools/origin-windows/code-receipt.mjs','comments/tools/origin-windows/expected-seed.json',
  'comments/tools/origin-windows/approval.template.json','comments/tools/origin-windows/RUN_APPROVED.ps1',
  'comments/tools/origin-windows/CONFIRM_CLEANUP.ps1','comments/tools/origin-windows/VERIFY_OFFLINE.ps1',
  'comments/tools/origin-windows/README.md','comments/tools/access-origin-diagnostic.mjs',
  'comments/tools/access-readiness.mjs','comments/staging/access-snapshot.mjs',
];
export const sha=b=>createHash('sha256').update(b).digest('hex');
const need=(v,c)=>{if(!v)throw Error(c);};
const json=f=>JSON.parse(readFileSync(f,'utf8').replace(/^\uFEFF/,''));
const save=(dir,name,value)=>writeFileSync(join(dir,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
export const safe=e=>/^[A-Z0-9_]{1,100}$/.test(e?.message||'')?e.message:'UNEXPECTED_ERROR_REDACTED';

export function packageIntegrity(expected){
  need(/^[a-f0-9]{64}$/.test(expected||''),'PACKAGE_SHA_REQUIRED');
  const bytes=readFileSync(join(ROOT,'package-manifest.json'));need(sha(bytes)===expected,'PACKAGE_MANIFEST_CHANGED');
  const m=JSON.parse(bytes);need(m.protocol===PROTOCOL&&/^[a-f0-9]{40}$/.test(m.source_head||''),'PACKAGE_METADATA_INVALID');
  need(canonical(Object.keys(m.files).sort())===canonical([...FILES].sort()),'PACKAGE_FILE_SET_CHANGED');
  for(const [name,digest]of Object.entries(m.files)){
    need(lstatSync(join(ROOT,name)).isFile()&&!lstatSync(join(ROOT,name)).isSymbolicLink(),'PACKAGE_FILE_INVALID');
    need(sha(readFileSync(join(ROOT,name)))===digest,'PACKAGE_BYTES_CHANGED');
  }
  return m;
}
export function validateApproval(a,now=Date.now(),cleanup=false){
  need(a?.schema===1&&a.approved===true,'APPROVAL_NOT_GRANTED');
  const fields=['schema','approved','authorization_id','not_before_utc','expires_at_utc','api_token_id',
    'api_token_name','dashboard_checked_at_utc','dashboard_checks','github_pr_sha','github_main_sha','github_pages_sha','github_checked_at_utc'];
  need(canonical(Object.keys(a).sort())===canonical(fields.sort()),'APPROVAL_FIELDS_INVALID');
  need(/^[a-f0-9]{16,32}$/.test(a.authorization_id||'')&&/^[a-f0-9]{32}$/.test(a.api_token_id||''),'APPROVAL_IDS_INVALID');
  need(/^kinoko-comments-origin-diag-build-\d{8}$/.test(a.api_token_name||''),'TOKEN_NAME_INVALID');
  const date=s=>{
    if(typeof s!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(s))return NaN;
    const t=Date.parse(s);return Number.isFinite(t)&&new Date(t).toISOString()===s.replace('Z','.000Z')?t:NaN;
  };
  const start=date(a.not_before_utc),end=date(a.expires_at_utc);
  need(Number.isFinite(start)&&Number.isFinite(end)&&end>start&&end-start<=1800000,'LEASE_EXCEEDS_30_MINUTES');
  if(!cleanup)need(now>=start&&now<end-300000,'LEASE_NOT_ACTIVE_OR_TOO_CLOSE');
  const keys=['workers_free','teams_free','single_worker_token_scope','pr138_worker_pages_unchanged',
    'no_custom_domains_routes','production_comments_disabled'];
  need(canonical(Object.keys(a.dashboard_checks||{}).sort())===canonical([...keys].sort())&&
    keys.every(k=>a.dashboard_checks[k]===true),'DASHBOARD_CHECKS_NOT_CONFIRMED');
  need(['github_pr_sha','github_main_sha','github_pages_sha'].every(k=>/^[a-f0-9]{40}$/.test(a[k]||'')),'GITHUB_CHECK_MISSING');
  if(!cleanup)for(const k of ['dashboard_checked_at_utc','github_checked_at_utc']){
    const time=date(a[k]);need(Number.isFinite(time)&&now>=time&&now-time<=600000,'OPERATOR_CHECK_STALE');
  }
  return Object.freeze(a);
}
export function context(args){
  need(args.length===8,'EXPLICIT_ARGUMENTS_REQUIRED');
  const [approvalFile,approvalSha,manifestSha,runDir,evidenceDir,mode,unused1,unused2]=args;
  // Last two must be explicit fixed sentinels, never a shell command or header.
  need(unused1==='root-only'&&unused2==='no-service-auth','MODE_SENTINELS_REQUIRED');
  need(['validate','validate-close-only','read-only','diagnose','watchdog','close-only'].includes(mode),'MODE_INVALID');
  const manifest=packageIntegrity(manifestSha),bytes=readFileSync(approvalFile);
  need(sha(bytes)===approvalSha,'APPROVAL_BYTES_CHANGED');
  // Windows PowerShell5.1 Set-Content -Encoding UTF8 writes a BOM. The SHA
  // still binds the original bytes; only JSON decoding ignores that prefix.
  const approval=validateApproval(JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/,'')),Date.now(),['close-only','validate-close-only'].includes(mode));
  need(approval.github_pr_sha===manifest.source_head,'PR_HEAD_APPROVAL_MISMATCH');
  need(resolve(runDir)!==resolve(evidenceDir)&&resolve(runDir)!==ROOT,'RUN_DIRECTORY_UNSAFE');
  need(process.env.LOCALAPPDATA&&resolve(runDir)===resolve(process.env.LOCALAPPDATA,
    'KinokoCommentsStaging','origin-diag-'+approval.authorization_id),'AUTHORIZATION_DIRECTORY_MISMATCH');
  return {approvalFile,approvalSha,manifestSha,runDir:resolve(runDir),evidenceDir:resolve(evidenceDir),mode,approval,manifest};
}
const B='/workers/scripts/'+C.worker;
export function controlGuard(path,method='GET',body){
  if(method==='GET'&&body===undefined&&[B+'/settings',B+'/subdomain',B+'/deployments',B+'/content/v2',
    '/workers/workers/'+C.worker+'/versions/'+VERSION,'/d1/database/'+C.db,'/access/apps','/access/service_tokens'].includes(path))return;
  if(method==='GET'&&body===undefined&&/^\/access\/apps\/[a-f0-9-]{36}(?:\/policies)?$/.test(path))return;
  if(method==='POST'&&path===B+'/subdomain'&&body&&typeof body.enabled==='boolean'&&body.previews_enabled===false&&
    Object.keys(body).sort().join(',')==='enabled,previews_enabled')return;
  if(method==='POST'&&path==='/d1/database/'+C.db+'/query'&&body&&Object.keys(body).sort().join(',')==='params,sql'&&
    Array.isArray(body.params)&&!body.params.length&&Object.values(SQL).includes(body.sql))return;
  throw Error('CONTROL_SCOPE_BLOCKED');
}
async function bounded(operation,ms=8000){
  const c=new AbortController();let timer;
  try{return await Promise.race([operation(c.signal),new Promise((_,no)=>{timer=setTimeout(()=>{c.abort();no(Error('CONTROL_TIMEOUT'));},ms);})]);}
  finally{clearTimeout(timer);}
}
export function client(ctx){
  need(process.env.CLOUDFLARE_ACCOUNT_ID===C.account&&/^[A-Za-z0-9_-]{20,200}$/.test(process.env.CLOUDFLARE_API_TOKEN||''),'BUILD_TOKEN_INPUT_INVALID');
  need(!Object.keys(process.env).some(k=>/^(KINOKO_ACCESS_CLIENT_|KINOKO_STAGING_ADMIN_TOKEN)/.test(k)&&process.env[k]),'SERVICE_OR_ADMIN_CREDENTIALS_FORBIDDEN');
  const token=process.env.CLOUDFLARE_API_TOKEN;
  return async(path,method='GET',body,raw=false)=>{
    controlGuard(path,method,body);
    const closing=method==='POST'&&path===B+'/subdomain'&&body.enabled===false;
    // Cleanup always targets OFF; it must survive a changed approval file or
    // elapsed lease. The server may reject an expired token: Dashboard then wins.
    if(!closing){
      need(sha(readFileSync(ctx.approvalFile))===ctx.approvalSha,'APPROVAL_BYTES_CHANGED');
      need(Date.now()<Date.parse(ctx.approval.expires_at_utc),'ABSOLUTE_DEADLINE_REACHED');
    }
    return bounded(async signal=>{
      const r=await fetch('https://api.cloudflare.com/client/v4/accounts/'+C.account+path,{
        method,redirect:'error',signal,headers:{Authorization:'Bearer '+token,
          ...(raw?{Accept:'multipart/form-data'}:{}),...(body?{'Content-Type':'application/json'}:{})},
        ...(body?{body:JSON.stringify(body)}:{})});
      const bytes=Buffer.from(await r.arrayBuffer());need(bytes.length<=8388608,'CONTROL_BODY_LIMIT');
      if(raw)return new Response(bytes,{status:r.status,headers:r.headers});
      let d;try{d=JSON.parse(bytes);}catch{throw Error('CONTROL_JSON_INVALID');}
      need(r.ok&&d?.success===true,'CONTROL_HTTP_'+r.status);
      if(Array.isArray(d.result))need(d.result.length<100&&(!d.result_info?.total_pages||d.result_info.total_pages<=1),'CONTROL_LIST_INCOMPLETE');
      return d.result;
    });
  };
}
export function evidence(dir){
  const names=readdirSync(dir).filter(n=>/^nov4-(?:readonly-report-\d+|first-report-\d+|first-attempt\.local|watchdog-\d+)\.json$/.test(n)).sort();
  need(names.length>=3&&names.length<=40,'PRIOR_EVIDENCE_MISSING');
  const hashes={};for(const name of names){const p=join(dir,name);need(lstatSync(p).isFile()&&!lstatSync(p).isSymbolicLink(),'EVIDENCE_FILE_UNSAFE');
    const b=readFileSync(p);need(b.length<=5242880,'EVIDENCE_TOO_LARGE');hashes[name]=sha(b);}
  const stop=json(join(dir,names.filter(n=>n.startsWith('nov4-first-report-')).at(-1)||'missing'));
  need(/^nov4-readonly-report-\d+\.json$/.test(stop.baseline_file||'')&&
    hashes[stop.baseline_file]===stop.baseline_sha256,'PRIOR_BASELINE_BYTES_CHANGED');
  const prior=json(join(dir,stop.baseline_file));
  need(names.includes('nov4-first-attempt.local.json')&&prior.result==='NOV4_READONLY_OK'&&prior.urls_closed===true&&
    prior.version_id===VERSION&&prior.deployed_source_head===C.head&&prior.worker_first_verified===true&&
    prior.owner_exact===true&&prior.access_all_traffic===true&&stop.result==='NOV4_FIRST_STOP'&&stop.authenticated_requests===0&&stop.urls_closed===true&&
    stop.access_unchanged===true&&stop.d1_counts_unchanged===true&&stop.previous_proof_preserved===true,'PRIOR_STOP_PROOF_INVALID');
  for(const k of ['owner_sha256','service_sha256','app_sha256','other_access_sha256'])need(/^[a-f0-9]{64}$/.test(prior.baseline?.[k]||''),'PRIOR_BASELINE_MISSING');
  return {hashes,prior};
}
const config=p=>{const v={...p};for(const k of ['created_at','updated_at','app_count'])delete v[k];return v;};
const digest=v=>sha(canonical(v));
export async function closed(api){
  const u=await api(B+'/subdomain'),s=await api(B+'/settings');checkSettings(s,u);return s;
}
export async function turn(api,enabled){
  await api(B+'/subdomain','POST',{enabled,previews_enabled:false});
  const u=await api(B+'/subdomain');need(u.enabled===enabled&&u.previews_enabled===false,'URL_STATE_UNCONFIRMED');
}
export async function snapshot(api,owner,old){
  need(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(owner||''),'OWNER_INPUT_REQUIRED');
  const s=await closed(api),installation=checkSettings(s,{enabled:false,previews_enabled:false});
  need(s.compatibility_date==='2026-10-01'&&!(s.compatibility_flags||[]).length&&s.bindings.every(b=>['plain_text','secret_text','assets','d1'].includes(b.type)),'SETTINGS_CHANGED');
  need(s.bindings.filter(b=>b.type==='assets').length===1&&s.bindings.find(b=>b.type==='assets').name==='ASSETS','ASSET_BINDING_CHANGED');
  need(deployedVersion(await api(B+'/deployments'))===VERSION,'VERSION_CHANGED');
  const v=await api('/workers/workers/'+C.worker+'/versions/'+VERSION);
  need(v.id===VERSION&&v.assets?.config?.run_worker_first===true&&v.bindings?.filter(b=>b.type==='assets').length===1&&v.bindings.find(b=>b.type==='assets').name==='ASSETS','WORKER_FIRST_CHANGED');
  const receipt=await codeReceipt(await api(B+'/content/v2','GET',undefined,true));
  const db=await api('/d1/database/'+C.db);need(db.uuid===C.db&&db.name===C.worker,'D1_ID_NAME_CHANGED');
  const apps=[],policies={};for(const a of await api('/access/apps')){
    apps.push(await api('/access/apps/'+a.id));policies[a.id]=await api('/access/apps/'+a.id+'/policies');}
  checkOtherApps(apps);const app=apps.find(a=>a.id===C.app),p=policies[C.app];
  validateAccessSnapshot(app,p,{appId:C.app,workerTag:C.tag,aud:C.aud,ownerPolicyId:C.owner,servicePolicyId:C.service,tokenId:C.oldService,ownerEmail:owner});
  for(const a of apps.filter(x=>x.id!==C.app))for(const q of policies[a.id])need(q.id!==C.service,'DEDICATED_POLICY_SHARED');
  const a={...app};for(const k of ['created_at','updated_at','policies'])delete a[k];
  const hashes={owner_sha256:digest(config(p.find(x=>x.id===C.owner))),service_sha256:digest(config(p.find(x=>x.id===C.service))),
    app_sha256:digest(a),other_access_sha256:digest(apps.filter(x=>x.id!==C.app).sort((a,b)=>a.id.localeCompare(b.id)).map(a=>({app:a,policies:policies[a.id]})))};
  for(const k of Object.keys(hashes))need(hashes[k]===old.baseline[k],'ACCESS_BASELINE_CHANGED');
  const tokens=await api('/access/service_tokens');checkTokens(tokens);
  const state={};for(const [k,sql]of Object.entries(SQL)){const r=await api('/d1/database/'+C.db+'/query','POST',{sql,params:[]});
    need(r?.length===1&&r[0].success===true&&Array.isArray(r[0].results),'D1_READ_INVALID');state[k]=r[0].results;}
  checkDb(state,json(join(DIR,'expected-seed.json')),installation);
  need(canonical(state.counts[0])===canonical(old.business_counts),'PRIOR_D1_COUNTS_CHANGED');
  await closed(api);
  return {...receipt,version_id:VERSION,baseline:hashes,settings_sha256:digest(s),tokens_sha256:digest(tokens),
    d1_sha256:digest(state),business_counts:state.counts[0],old_services_disabled_expired:5,
    migrations:3,cases:66,aliases:66,urls_closed:true,read:false,write:false,release:'not-approved'};
}
async function startWatchdog(ctx){
  const env={...process.env};for(const k of Object.keys(env))if(k.startsWith('KINOKO_'))delete env[k];
  const args=[ctx.approvalFile,ctx.approvalSha,ctx.manifestSha,ctx.runDir,ctx.evidenceDir,'watchdog','root-only','no-service-auth'];
  const child=fork(SELF,args,{env,stdio:['ignore','ignore','ignore','ipc'],windowsHide:true});
  await new Promise((ok,no)=>{const t=setTimeout(()=>{child.kill();no(Error('WATCHDOG_NOT_READY'));},30000);
    child.once('message',v=>{clearTimeout(t);v==='closed-and-armed'?ok():no(Error('WATCHDOG_NOT_READY'));});
    child.once('error',()=>{clearTimeout(t);no(Error('WATCHDOG_START_FAILED'));});
    child.once('exit',()=>{clearTimeout(t);no(Error('WATCHDOG_EARLY_EXIT'));});});return child;
}
export async function watchdog(ctx){
  const api=client(ctx);need(existsSync(join(ctx.runDir,'host-attempt.json')),'HOST_MARKER_MISSING');
  // An idempotent OFF write proves the child has closure permission before any
  // URL is enabled. No public HTTP is sent by this child.
  await turn(api,false);await closed(api);
  save(ctx.runDir,'watchdog-armed.json',{protocol:PROTOCOL,closure_probe_verified:true,
    armed_at:new Date().toISOString(),fallback_after_ms:WATCHDOG_MS});
  process.send?.('closed-and-armed');
  await new Promise(resolve=>setTimeout(resolve,WATCHDOG_MS));
  const r={protocol:PROTOCOL,authorization_id:ctx.approval.authorization_id,result:'WATCHDOG_STOP',closure_verified:false};
  try{await turn(api,false);await closed(api);r.result='WATCHDOG_CLOSED';r.closure_verified=true;}catch(e){r.reason=safe(e);}
  save(ctx.runDir,'watchdog-report.json',r);if(process.connected)process.disconnect();
}
export async function main(ctx){
  const api=client(ctx),owner=process.env.KINOKO_RETEST_OWNER_EMAIL;
  mkdirSync(ctx.runDir,{recursive:true});
  need(lstatSync(ctx.runDir).isDirectory()&&!lstatSync(ctx.runDir).isSymbolicLink(),'RUN_DIRECTORY_UNSAFE');
  if(ctx.mode==='close-only'){
    const r={protocol:PROTOCOL,authorization_id:ctx.approval.authorization_id,result:'CLOSE_ONLY_STOP',urls_closed:false};
    try{await turn(api,false);await closed(api);r.result='CLOSE_ONLY_CLOSED';r.urls_closed=true;}
    catch(e){r.reason=safe(e);}
    save(ctx.runDir,'close-only-'+Date.now()+'.json',r);console.log(r.result+' URLs_closed='+r.urls_closed);
    if(!r.urls_closed)process.exitCode=1;return r;
  }
  const marker=ctx.mode==='read-only'?'read-only.attempt.json':'host-attempt.json';
  need(!existsSync(join(ctx.runDir,marker)),'ATTEMPT_EXISTS_NO_RETRY');
  if(ctx.mode==='diagnose')need(existsSync(join(ctx.runDir,'read-only-report.json')),'READ_ONLY_REPORT_REQUIRED');
  save(ctx.runDir,marker,{protocol:PROTOCOL,approval_sha256:ctx.approvalSha,phase:ctx.mode});
  const old=evidence(ctx.evidenceDir),r={protocol:PROTOCOL,source_head:ctx.manifest.source_head,mode:ctx.mode,
    authorization_id:ctx.approval.authorization_id,approval_sha256:ctx.approvalSha,started_at:new Date().toISOString(),
    authenticated_requests:0,public_requests:0,urls_closed:false,api_token_deletion:'pending-dashboard-confirmation',
    operator_checks:ctx.approval.dashboard_checks,github_main_sha:ctx.approval.github_main_sha,github_pages_sha:ctx.approval.github_pages_sha};
  let child,openAttempt=false,enableConfirmed=false,before;
  try{
    before=await snapshot(api,owner,old.prior);r.preflight=before;
    if(ctx.mode==='read-only'){r.result='ORIGIN_READ_ONLY_OK';r.urls_closed=true;return r;}
    const prior=json(join(ctx.runDir,'read-only-report.json'));
    need(prior.result==='ORIGIN_READ_ONLY_OK'&&prior.approval_sha256===ctx.approvalSha&&prior.source_head===ctx.manifest.source_head&&
      Date.now()-Date.parse(prior.completed_at)>=0&&Date.now()-Date.parse(prior.completed_at)<600000&&
      canonical(prior.preflight)===canonical(before),'FRESH_READ_ONLY_PROOF_MISMATCH');
    const sequenceDir=join(ctx.runDir,'root-observations');mkdirSync(sequenceDir);
    // Core reserves its exclusive marker BEFORE this callback may enable URLs.
    r.diagnostic=await runOriginDiagnostic({attemptDirectory:sequenceDir,
      preflight:async()=>{
        try{
          validateApproval(ctx.approval);need(sha(readFileSync(ctx.approvalFile))===ctx.approvalSha,'APPROVAL_BYTES_CHANGED');
          child=await startWatchdog(ctx);r.watchdog_closure_probe_verified=true;await closed(api);
          // This flag must precede the POST: a lost response may still enable it.
          openAttempt=true;await turn(api,true);enableConfirmed=true;return true;
        }catch(e){r.preflight_error=safe(e);throw e;}
      },
      request:async(url,options)=>{
        need(child&&child.exitCode===null&&!child.killed,'WATCHDOG_NOT_RUNNING');
        need(Date.now()<Date.parse(ctx.approval.expires_at_utc)-60000,'LEASE_TOO_CLOSE');
        need(++r.public_requests<=4&&url===C.origin+'/'&&options.method==='GET'&&Object.getPrototypeOf(options.headers)===Object.prototype&&Object.keys(options.headers).length===0&&
          options.credentials==='omit'&&options.redirect==='manual'&&options.cache==='no-store','PUBLIC_SCOPE_BLOCKED');
        return fetch(url,options);
      },
      close:async()=>{
        if(openAttempt)await turn(api,false);await closed(api);
        // A lost enable response may still have been applied remotely. Keep
        // the independent delayed OFF fallback rather than declaring closure.
        if(openAttempt&&!enableConfirmed){r.enable_outcome_ambiguous=true;r.close_readback=true;return false;}
        r.urls_closed=true;return true;
      },
    });
    if(r.urls_closed===true)child?.kill();
    r.result=r.diagnostic.result;
    if(r.diagnostic.reason)r.reason=r.diagnostic.reason;
  }catch(e){r.result='ORIGIN_STOP';r.reason=safe(e);}
  finally{
    // A failed close is not retried by re-running this diagnostic. The already
    // armed child remains alive for its single independent OFF fallback.
    if(!openAttempt)try{await closed(api);r.urls_closed=true;}catch{}
    if(child){
      if(r.urls_closed)child.kill();
      else {if(child.connected)child.disconnect();child.unref();}
    }
    if(openAttempt&&!r.urls_closed){r.phase_reason=r.reason||null;r.reason='CLOSURE_UNCONFIRMED_CHECK_DASHBOARD';r.result='ORIGIN_STOP';}
    if(r.urls_closed&&before)try{
      const after=await snapshot(api,owner,old.prior);
      need(canonical(after)===canonical(before),'POST_SNAPSHOT_CHANGED');r.post_checks_unchanged=true;
    }catch(e){r.result='ORIGIN_STOP';r.post_check_reason=safe(e);}
    try{need(canonical(evidence(ctx.evidenceDir).hashes)===canonical(old.hashes),'PRIOR_EVIDENCE_CHANGED');r.previous_evidence_preserved=true;r.evidence_sha256=old.hashes;}
    catch{r.result='ORIGIN_STOP';r.post_check_reason='PRIOR_EVIDENCE_CHANGED';}
    r.completed_at=new Date().toISOString();save(ctx.runDir,ctx.mode==='read-only'?'read-only-report.json':'diagnostic-report.json',r);
    console.log(r.result+' requests='+r.public_requests+' authenticated_requests=0 URLs_closed='+r.urls_closed+
      ' prior_evidence_preserved='+(r.previous_evidence_preserved===true)+(r.reason?' reason='+r.reason:''));
    if(!r.urls_closed||r.post_check_reason||r.result==='ORIGIN_STOP'||r.result==='STOP')process.exitCode=1;
    delete process.env.CLOUDFLARE_API_TOKEN;delete process.env.KINOKO_RETEST_OWNER_EMAIL;
  }
  return r;
}
if(process.argv[1]&&pathToFileURL(resolve(process.argv[1])).href===import.meta.url){
  (async()=>{
    if(process.argv[2]==='verify-package'){
      const m=packageIntegrity(process.argv[3]);console.log('PACKAGE_OK source_head='+m.source_head+' no_network=true');return;
    }
    const ctx=context(process.argv.slice(2));
    if(ctx.mode==='validate'||ctx.mode==='validate-close-only'){console.log('APPROVAL_AND_PACKAGE_VALID no_network=true');return;}
    if(ctx.mode==='watchdog')await watchdog(ctx);else await main(ctx);
  })().catch(e=>{console.log('ORIGIN_WINDOWS_STOP reason='+safe(e)+' no_retry=true');process.exitCode=1;});
}
