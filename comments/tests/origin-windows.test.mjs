import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,readdirSync,rmSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,dirname,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {execFile,execFileSync,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {setTimeout as pause} from 'node:timers/promises';
import {fixture,NOW,TOKEN,OWNER} from './origin-windows-fixture.mjs';
import {controlGuard,validateApproval,sha} from '../tools/origin-windows/runner.mjs';
import {C,SQL} from '../tools/origin-windows/preflight.mjs';
const DIR=dirname(fileURLToPath(import.meta.url)),ROOT=resolve(DIR,'../..'),run=promisify(execFile);
function prepare(t,scenario){
  const root=mkdtempSync(join(tmpdir(),'kinoko-origin-packet-'));
  t.after(()=>rmSync(root,{recursive:true,force:true}));
  const packet=join(root,'packet');
  const receipt=JSON.parse(execFileSync('python',[join(ROOT,'comments/tools/build_origin_windows.py'),packet],{encoding:'utf8'}));
  const {f,approval,evidence}=fixture(root,scenario);
  approval.github_pr_sha=receipt.source_head;
  const paths={f:join(root,'fixture.json'),s:join(root,'state.json'),e:join(root,'events.ndjson'),a:join(root,'approval.json')};
  writeFileSync(paths.f,JSON.stringify(f));writeFileSync(paths.s,JSON.stringify({enabled:false,previews_enabled:false}));
  writeFileSync(paths.e,'');writeFileSync(paths.a,JSON.stringify(approval));
  const runDir=join(root,'local-data','KinokoCommentsStaging','origin-diag-'+approval.authorization_id),script=join(packet,'comments/tools/origin-windows/runner.mjs');
  const base=[paths.a,sha(readFileSync(paths.a)),receipt.manifest_sha256,runDir,evidence];
  const env={...process.env,CLOUDFLARE_ACCOUNT_ID:C.account,CLOUDFLARE_API_TOKEN:TOKEN,KINOKO_RETEST_OWNER_EMAIL:OWNER,
    LOCALAPPDATA:join(root,'local-data'),
    ORIGIN_TEST_FIXTURE:paths.f,ORIGIN_TEST_STATE:paths.s,ORIGIN_TEST_EVENTS:paths.e};
  for(const k of ['NODE_OPTIONS','KINOKO_ACCESS_CLIENT_ID','KINOKO_ACCESS_CLIENT_SECRET','KINOKO_STAGING_ADMIN_TOKEN'])delete env[k];
  const args=mode=>['--import',pathToFileURL(join(DIR,'origin-windows-fetch-shim.mjs')).href,script,...base,mode,'root-only','no-service-auth'];
  const invoke=async mode=>{try{return await run(process.execPath,args(mode),{env,timeout:30000,windowsHide:true});}catch(e){return e;}};
  return {root,packet,receipt,paths,runDir,base,script,env,args,invoke,f,approval,evidence};
}
function events(x){return readFileSync(x.paths.e,'utf8').trim().split('\n').filter(Boolean).map(s=>JSON.parse(s));}
async function waitFile(file){for(let n=0;n<120;n++){if(existsSync(file))return JSON.parse(readFileSync(file));await pause(50);}throw Error('offline file wait expired');}

for(const scenario of ['success','404-302-404','root404','all404','timeout','bad-redirect','html','no-close-permission','access-mismatch'])
test('packaged Windows host with real watchdog child, all HTTP mocked: '+scenario,async t=>{
  const x=prepare(t,scenario);
  const oldBytes=readdirSync(x.evidence).map(n=>[n,readFileSync(join(x.evidence,n),'utf8')]);
  const pre=await x.invoke('read-only');assert.equal(pre.code,undefined,pre.stdout||pre.message);
  assert.equal(JSON.parse(readFileSync(join(x.runDir,'read-only-report.json'))).result,'ORIGIN_READ_ONLY_OK');
  assert.equal(events(x).filter(v=>v.type==='mutation'||v.type==='public').length,0);
  if(scenario==='access-mismatch'){
    x.f.get['/access/apps/'+C.app+'/policies'][0].include=[{everyone:{}}];writeFileSync(x.paths.f,JSON.stringify(x.f));
  }
  const result=await x.invoke('diagnose');
  const report=JSON.parse(readFileSync(join(x.runDir,'diagnostic-report.json')));
  const calls=events(x),publics=calls.filter(v=>v.type==='public'),writes=calls.filter(v=>v.type==='mutation');
  assert.equal(report.authenticated_requests,0);assert.equal(report.urls_closed,true);
  assert.equal(report.previous_evidence_preserved,true);
  assert.deepEqual(readdirSync(x.evidence).map(n=>[n,readFileSync(join(x.evidence,n),'utf8')]),oldBytes);
  assert.ok(publics.length<=4);assert.ok(publics.every(v=>v.path==='/'&&v.method==='GET'&&v.authenticated===false));
  assert.ok(writes.every(v=>v.key==='/workers/scripts/'+C.worker+'/subdomain'&&v.body.previews_enabled===false));
  assert.deepEqual(JSON.parse(readFileSync(x.paths.s)),{enabled:false,previews_enabled:false});
  if(scenario==='success'){
    assert.equal(result.code,undefined,result.stdout);assert.equal(publics.length,4);
    assert.equal(report.result,'UNAUTHENTICATED_ROOT_WINDOW_COMPLETE');
    assert.deepEqual(writes.map(v=>v.body.enabled),[false,true,false]);
  }else{
    assert.notEqual(result.code,undefined,result.stdout);
    assert.notEqual(report.result,'UNAUTHENTICATED_ROOT_WINDOW_COMPLETE');
    if(scenario==='access-mismatch'||scenario==='no-close-permission')assert.equal(publics.length,0);
    if(scenario==='404-302-404')assert.equal(report.reason,'ACCESS_REDIRECT_REGRESSED_TO_404');
    if(scenario==='root404')assert.equal(report.diagnostic.tests[0].status,404);
  }
  assert.equal(JSON.stringify(report).includes(TOKEN),false);assert.equal(JSON.stringify(report).includes(OWNER),false);
  assert.equal(JSON.stringify(report).includes('PRIVATE_'),false);
  const before=readFileSync(x.paths.e,'utf8'),retry=await x.invoke('diagnose');
  assert.match(retry.stdout,/ATTEMPT_EXISTS_NO_RETRY/);assert.equal(readFileSync(x.paths.e,'utf8'),before);
});

test('parent killed while URL open: independent child closes, marker prevents restart',async t=>{
  const x=prepare(t,'parent-crash');await x.invoke('read-only');
  const child=spawn(process.execPath,x.args('diagnose'),{env:x.env,stdio:'ignore',windowsHide:true});
  for(let i=0;i<100;i++){if(events(x).some(v=>v.type==='public'))break;await pause(50);}
  assert.equal(JSON.parse(readFileSync(x.paths.s)).enabled,true);
  const exit=new Promise(resolve=>child.once('exit',resolve));child.kill();await exit;
  const r=await waitFile(join(x.runDir,'watchdog-report.json'));
  assert.equal(r.result,'WATCHDOG_CLOSED');assert.equal(r.closure_verified,true);
  assert.equal(JSON.parse(readFileSync(x.paths.s)).enabled,false);
  const before=readFileSync(x.paths.e,'utf8'),retry=await x.invoke('diagnose');
  assert.match(retry.stdout,/ATTEMPT_EXISTS_NO_RETRY/);assert.equal(readFileSync(x.paths.e,'utf8'),before);
});
test('main and independent closure failures are both visible, never reported as closed',async t=>{
  const x=prepare(t,'close-fail');await x.invoke('read-only');
  const result=await x.invoke('diagnose');assert.notEqual(result.code,undefined);
  const r=JSON.parse(readFileSync(join(x.runDir,'diagnostic-report.json')));
  assert.equal(r.urls_closed,false);assert.equal(r.reason,'CLOSURE_UNCONFIRMED_CHECK_DASHBOARD');
  const w=await waitFile(join(x.runDir,'watchdog-report.json'));
  assert.equal(w.closure_verified,false);assert.equal(w.result,'WATCHDOG_STOP');
});
test('lost enable response keeps the delayed OFF fallback and reports uncertainty',async t=>{
  const x=prepare(t,'enable-response-lost');await x.invoke('read-only');
  const result=await x.invoke('diagnose');assert.notEqual(result.code,undefined);
  const r=JSON.parse(readFileSync(join(x.runDir,'diagnostic-report.json')));
  assert.equal(r.enable_outcome_ambiguous,true);assert.equal(r.close_readback,true);assert.equal(r.urls_closed,false);
  assert.equal(events(x).filter(v=>v.type==='public').length,0);
  const w=await waitFile(join(x.runDir,'watchdog-report.json'));
  assert.equal(w.closure_verified,true);assert.equal(JSON.parse(readFileSync(x.paths.s)).enabled,false);
});
test('close-only uses no public request, cannot enable URLs and preserves old markers',async t=>{
  const x=prepare(t,'success');await x.invoke('read-only');
  writeFileSync(x.paths.s,JSON.stringify({enabled:true,previews_enabled:false}));
  const before=events(x).length,result=await x.invoke('close-only');assert.equal(result.code,undefined,result.stdout);
  const calls=events(x).slice(before);assert.equal(calls.filter(v=>v.type==='public').length,0);
  assert.deepEqual(calls.filter(v=>v.type==='mutation').map(v=>v.body),[{enabled:false,previews_enabled:false}]);
  assert.equal(JSON.parse(readFileSync(x.paths.s)).enabled,false);
  assert.equal(readFileSync(join(x.evidence,'nov4-first-attempt.local.json'),'utf8'),'retained old marker bytes');
});
test('approval/deadline/hash gate is inert before any credential or network use',async t=>{
  const x=prepare(t,'success');const template=join(x.packet,'comments/tools/origin-windows/approval.template.json');
  x.base[0]=template;x.base[1]=sha(readFileSync(template));
  const r=await x.invoke('diagnose');assert.match(r.stdout,/APPROVAL_NOT_GRANTED/);
  assert.equal(readFileSync(x.paths.e,'utf8'),'');assert.equal(existsSync(x.runDir),false);
  const a=x.approval;assert.equal(validateApproval(a,NOW),a);
  for(const mutate of [a=>a.approved=false,a=>a.expires_at_utc='2026-11-05T01:29:01Z',
    a=>a.dashboard_checks.workers_free=false,a=>a.not_before_utc='',a=>a.github_main_sha='',a=>a.extra='PRIVATE']){
    const v=structuredClone(a);mutate(v);assert.throws(()=>validateApproval(v,NOW));
  }
  assert.throws(()=>validateApproval(a,Date.parse(a.expires_at_utc)));assert.throws(()=>validateApproval(a,NOW-120000));
});
test('API scope disallows deploy, seed, tokens, Access edits and other Worker changes',()=>{
  for(const [path,method,body]of [
    ['/workers/scripts/pr138-ah-private-20261026/subdomain','POST',{enabled:false,previews_enabled:false}],
    ['/workers/scripts/'+C.worker,'PUT',{}],['/access/apps/'+C.app,'PUT',{}],['/tokens/abc','DELETE'],
    ['/d1/database/'+C.db+'/query','POST',{sql:'DROP TABLE comments',params:[]}],
    ['/workers/scripts/'+C.worker+'/subdomain','POST',{enabled:true,previews_enabled:true}],
  ])assert.throws(()=>controlGuard(path,method,body),/CONTROL_SCOPE_BLOCKED/);
  for(const sql of Object.values(SQL))assert.doesNotThrow(()=>controlGuard('/d1/database/'+C.db+'/query','POST',{sql,params:[]}));
});
test('PowerShell5.1 UTF8-BOM approval is hash-bound and validates without a network call',async t=>{
  const x=prepare(t,'success');writeFileSync(x.paths.a,'\uFEFF'+JSON.stringify(x.approval));
  x.base[1]=sha(readFileSync(x.paths.a));
  const r=await x.invoke('validate');assert.equal(r.code,undefined,r.stdout||r.message);
  assert.match(r.stdout,/APPROVAL_AND_PACKAGE_VALID/);assert.equal(readFileSync(x.paths.e,'utf8'),'');
});
test('packet SHA and old proof guard reject tampering, with no requests',async t=>{
  const x=prepare(t,'success');writeFileSync(join(x.packet,'comments/tools/access-readiness.mjs'),readFileSync(join(x.packet,'comments/tools/access-readiness.mjs'),'utf8')+'\n// tampered valid module\n');
  const r=await x.invoke('read-only');assert.match(r.stdout,/PACKAGE_BYTES_CHANGED/);assert.equal(readFileSync(x.paths.e,'utf8'),'');
});

for(const [scenario,enabled,gets,closed] of [
  ['watchdog-before-ready',false,0,true],
  ['watchdog-after-ready',false,0,true],
  ['watchdog-before-enable',false,0,true],
  ['watchdog-during-enable',true,0,true],
  ['watchdog-enable-ambiguous',true,0,false],
  ['watchdog-before-first-get',true,0,true],
  ['watchdog-during-get',true,1,true],
  ['watchdog-between-gets',true,1,true],
  ['watchdog-disconnect',true,1,true],
  ['watchdog-error',true,1,true],
  ['watchdog-heartbeat-missing',true,1,true],
  ['watchdog-close-fail',true,1,false],
  ['watchdog-ipc-close-fail',true,1,false],
  ['watchdog-normal-retirement',true,4,true],
])test('packaged watchdog lifecycle: '+scenario,async t=>{
  const x=prepare(t,scenario);
  const oldBytes=readdirSync(x.evidence).map(n=>[n,readFileSync(join(x.evidence,n),'utf8')]);
  assert.equal((await x.invoke('read-only')).code,undefined);
  const start=events(x).length,result=await x.invoke('diagnose');
  const reportFile=join(x.runDir,'diagnostic-report.json'),reportBytes=readFileSync(reportFile,'utf8');
  const report=JSON.parse(reportBytes),calls=events(x).slice(start);
  const writes=calls.filter(v=>v.type==='mutation').map(v=>v.body.enabled);
  const faultEvent=scenario==='watchdog-heartbeat-missing'?'public-aborted':'watchdog-fault-observed';
  const fault=calls.findIndex(v=>v.type===faultEvent);
  const getsAfterFault=calls.slice(fault+1).filter(v=>v.type==='public').length;
  const normal=scenario==='watchdog-normal-retirement';
  assert.equal(writes.includes(true),enabled);
  assert.equal(calls.filter(v=>v.type==='public').length,gets);
  assert.equal(report.public_requests,gets);
  assert.equal(report.authenticated_requests,0);
  assert.equal(report.urls_closed,closed);
  assert.equal(report.previous_evidence_preserved,true);
  assert.deepEqual(readdirSync(x.evidence).map(n=>[n,readFileSync(join(x.evidence,n),'utf8')]),oldBytes);
  if(normal){
    assert.equal(result.code,undefined);
    assert.equal(report.watchdog_failure,undefined);
    assert.equal(report.result,'UNAUTHENTICATED_ROOT_WINDOW_COMPLETE');
    assert.deepEqual(writes,[false,true,false]);
  }else{
    assert.notEqual(result.code,undefined);
    assert.match(report.watchdog_failure,/^WATCHDOG_/);
    assert.equal(report.result,'ORIGIN_STOP');
    assert.notEqual(report.diagnostic.result,'UNAUTHENTICATED_ROOT_WINDOW_COMPLETE');
    assert.equal(getsAfterFault,0);
    assert.equal(report.post_checks_unchanged,undefined);
    if(scenario==='watchdog-disconnect'||scenario==='watchdog-ipc-close-fail')assert.equal(report.watchdog_failure,'WATCHDOG_IPC_DISCONNECTED');
    if(scenario==='watchdog-error')assert.equal(report.watchdog_failure,'WATCHDOG_PROCESS_ERROR');
    if(scenario==='watchdog-heartbeat-missing')assert.equal(report.watchdog_failure,'WATCHDOG_HEARTBEAT_MISSING');
    if(scenario!=='watchdog-before-ready'){
      assert.notEqual(fault,-1);
      for(const call of calls.slice(fault+1).filter(v=>v.type==='control')){
        assert.ok(call.key.endsWith('/subdomain')||call.key.endsWith('/settings'),JSON.stringify(call));
      }
    }
    if(!closed){
      assert.equal(report.reason,'CLOSURE_UNCONFIRMED_CHECK_DASHBOARD');
      assert.equal(report.phase_reason,report.watchdog_failure);
      if(scenario==='watchdog-enable-ambiguous'){
        assert.equal(report.closure_reason,'ENABLE_OUTCOME_AMBIGUOUS');
        assert.equal(report.close_readback,true);
      }else assert.equal(report.closure_reason,'CONTROL_HTTP_403');
    }
    if(scenario==='watchdog-during-enable'){
      const ack=calls.findIndex(v=>v.type==='enable-response');
      assert.ok(fault<ack&&ack<calls.findLastIndex(v=>v.type==='mutation'&&!v.body.enabled));
    }
    if(gets&&scenario!=='watchdog-between-gets')assert.ok(calls.some(v=>v.type==='public-aborted'));
    assert.deepEqual(writes,enabled?[false,true,false]:scenario==='watchdog-before-ready'?[]:[false]);
  }
  if(scenario==='watchdog-ipc-close-fail'){
    const fallback=await waitFile(join(x.runDir,'watchdog-report.json'));
    assert.equal(fallback.closure_verified,true);
  }else assert.equal(JSON.parse(readFileSync(x.paths.s)).enabled,!closed&&scenario!=='watchdog-enable-ambiguous');
  for(const secret of [TOKEN,OWNER,'PRIVATE_']){
    assert.ok(!reportBytes.includes(secret));
    assert.ok(!result.stdout.includes(secret));
  }
  const marker=join(x.runDir,'host-attempt.json'),markerBytes=readFileSync(marker,'utf8');
  const before=readFileSync(x.paths.e,'utf8'),retry=await x.invoke('diagnose');
  assert.match(retry.stdout,/ATTEMPT_EXISTS_NO_RETRY/);
  assert.equal(readFileSync(x.paths.e,'utf8'),before);
  assert.equal(readFileSync(reportFile,'utf8'),reportBytes);
  assert.equal(readFileSync(marker,'utf8'),markerBytes);
  t.diagnostic(JSON.stringify({scenario,enabled,gets,getsAfterFault:normal?null:getsAfterFault,
    offWrites:writes.filter(v=>!v).length,closureConfirmed:report.urls_closed,result:report.result,
    reason:report.reason??null,watchdogFailure:report.watchdog_failure??null}));
});

test('closure failure remains visible if the report cannot be saved',async t=>{
  const x=prepare(t,'watchdog-report-fail');
  assert.equal((await x.invoke('read-only')).code,undefined);
  const result=await x.invoke('diagnose');
  assert.notEqual(result.code,undefined);
  assert.match(result.stdout,/URLs_closed=false.*CLOSURE_UNCONFIRMED_CHECK_DASHBOARD.*report_save_failed=true/);
  assert.match(result.stdout,/REPORT_SAVE_FAILED/);
  assert.equal(readFileSync(join(x.runDir,'diagnostic-report.json'),'utf8'),'retained report bytes');
  const calls=events(x);
  assert.deepEqual(calls.filter(v=>v.type==='mutation').map(v=>v.body.enabled),[false,true,false]);
  assert.equal(calls.filter(v=>v.type==='public').length,1);
  t.diagnostic(JSON.stringify({scenario:'watchdog-report-fail',enabled:true,gets:1,getsAfterFault:0,
    offWrites:2,closureConfirmed:false,result:'CLOSURE_UNCONFIRMED_CHECK_DASHBOARD',reportSaveFailed:true}));
});

test('both processes stopped while open: requires external closure and blocks a retry',async t=>{
  const x=prepare(t,'watchdog-both-stopped');
  assert.equal((await x.invoke('read-only')).code,undefined);
  const parent=spawn(process.execPath,x.args('diagnose'),{env:x.env,stdio:'ignore',windowsHide:true});
  for(let n=0;n<100&&!events(x).some(v=>v.type==='public');n++)await pause(50);
  const calls=events(x),child=calls.find(v=>v.type==='watchdog-spawn');
  const parentExit=new Promise(resolve=>parent.once('exit',resolve));
  try{
    assert.ok(child&&calls.some(v=>v.type==='public'));
    assert.equal(JSON.parse(readFileSync(x.paths.s)).enabled,true);
  }finally{
    if(parent.exitCode===null&&parent.signalCode===null){parent.kill();await parentExit;}
    if(child)process.kill(child.pid,'SIGTERM');
  }
  assert.equal(existsSync(join(x.runDir,'diagnostic-report.json')),false);
  assert.equal(existsSync(join(x.runDir,'watchdog-report.json')),false);
  assert.equal(JSON.parse(readFileSync(x.paths.s)).enabled,true);
  const before=readFileSync(x.paths.e,'utf8'),retry=await x.invoke('diagnose');
  assert.match(retry.stdout,/ATTEMPT_EXISTS_NO_RETRY/);
  assert.equal(readFileSync(x.paths.e,'utf8'),before);
  t.diagnostic(JSON.stringify({scenario:'watchdog-both-stopped',enabled:true,gets:1,getsAfterFault:0,
    offWrites:1,closureConfirmed:false,result:'EXTERNAL_CLOSURE_REQUIRED'}));
});
