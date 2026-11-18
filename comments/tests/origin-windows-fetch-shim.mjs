// Only test subprocesses import this. It is excluded from the Windows packet.
// There is deliberately no fallback to the native network implementation.
import {readFileSync,writeFileSync,appendFileSync} from 'node:fs';
import childProcess from 'node:child_process';
import {syncBuiltinESMExports} from 'node:module';
import {once} from 'node:events';
const f=JSON.parse(readFileSync(process.env.ORIGIN_TEST_FIXTURE,'utf8'));
const state=process.env.ORIGIN_TEST_STATE,events=process.env.ORIGIN_TEST_EVENTS;
const RealDate=Date, mode=process.argv.at(-3), isWatchdog=mode==='watchdog';
if(isWatchdog&&f.scenario==='watchdog-before-ready')process.exit(1);
if(isWatchdog&&f.scenario==='watchdog-heartbeat-missing'){
  const send=process.send.bind(process);
  process.send=(message,...args)=>message==='watchdog-alive'||send(message,...args);
}
globalThis.Date=class extends RealDate{constructor(...a){super(...(a.length?a:[f.now]));}static now(){return f.now;}};
if(isWatchdog&&['parent-crash','close-fail','enable-response-lost','watchdog-ipc-close-fail'].includes(f.scenario)){
  const timer=setTimeout;globalThis.setTimeout=(fn,ms,...a)=>timer(fn,ms===90000?1500:ms,...a);
}
const emit=v=>appendFileSync(events,JSON.stringify(v)+'\n');
let publicCount=0,watchdogChild,armed=false,faultInjected=false;
if(mode==='diagnose'&&f.scenario.startsWith('watchdog-')){
  const fork=childProcess.fork;
  childProcess.fork=(...args)=>{
    watchdogChild=fork(...args);
    watchdogChild.once('message',()=>{armed=true;});
    emit({type:'watchdog-spawn',pid:watchdogChild.pid});
    return watchdogChild;
  };
  syncBuiltinESMExports();
}
async function fault(kind='exit'){
  if(faultInjected)throw Error('TEST_DUPLICATE_FAULT');
  faultInjected=true;
  const event={error:'error',disconnect:'disconnect',exit:'exit'}[kind];
  let recorded=false;
  const record=()=>{
    if(recorded)return;
    recorded=true;
    emit({type:'watchdog-fault-observed'});
  };
  watchdogChild.prependOnceListener(event,record);
  if(kind==='exit')watchdogChild.prependOnceListener('disconnect',record);
  if(kind==='error'){
    watchdogChild.emit('error',Error('PRIVATE_SYNTHETIC_WATCHDOG_ERROR'));
  }else if(kind==='disconnect'){
    const disconnected=once(watchdogChild,'disconnect');
    watchdogChild.disconnect();
    await disconnected;
  }else{
    const exited=once(watchdogChild,'exit');
    process.kill(watchdogChild.pid,'SIGTERM');
    await exited;
  }
}
globalThis.fetch=async(input,o={})=>{
  const u=new URL(input),method=o.method||'GET';
  if(u.origin==='https://api.cloudflare.com'){
    const prefix='/client/v4/accounts/'+f.C.account;if(!u.pathname.startsWith(prefix))throw Error('TEST_WRONG_ACCOUNT');
    const key=u.pathname.slice(prefix.length),b='/workers/scripts/'+f.C.worker;
    emit({type:'control',key,method});
    if(key===b+'/subdomain'){
      if(method==='POST'){
        const body=JSON.parse(o.body);emit({type:'mutation',key,body});
        const current=JSON.parse(readFileSync(state));
        const closeDenied=['close-fail','watchdog-close-fail','watchdog-report-fail'].includes(f.scenario)||
          f.scenario==='watchdog-ipc-close-fail'&&!isWatchdog;
        if(!body.enabled&&(f.scenario==='no-close-permission'||current.enabled&&closeDenied))
          return Response.json({success:false},{status:403});
        if(body.enabled&&['watchdog-during-enable','watchdog-enable-ambiguous'].includes(f.scenario))await fault();
        writeFileSync(state,JSON.stringify(body));
        if(body.enabled&&['enable-response-lost','watchdog-enable-ambiguous'].includes(f.scenario))throw Error('TEST_ENABLE_RESPONSE_LOST');
        if(body.enabled&&f.scenario==='watchdog-during-enable')emit({type:'enable-response'});
      }else if(armed&&!faultInjected){
        const enabled=JSON.parse(readFileSync(state)).enabled;
        if(!enabled&&f.scenario==='watchdog-after-ready')await fault();
        if(enabled&&f.scenario==='watchdog-before-first-get')await fault();
      }
      return Response.json({success:true,result:JSON.parse(readFileSync(state))});
    }
    if(armed&&!faultInjected&&key===b+'/settings'&&f.scenario==='watchdog-before-enable')await fault();
    if(key===b+'/content/v2'&&method==='GET')return new Response(Buffer.from(f.code_base64,'base64'),{headers:{'content-type':'application/javascript'}});
    if(method==='GET'&&key in f.get)return Response.json({success:true,result:f.get[key]});
    if(method==='POST'&&key==='/d1/database/'+f.C.db+'/query'){
      const body=JSON.parse(o.body);if(!(body.sql in f.sql)||body.params.length)throw Error('TEST_SQL_MUTATION');
      return Response.json({success:true,result:[{success:true,results:f.sql[body.sql]}]});
    }
    throw Error('TEST_CONTROL_NOT_ALLOWED');
  }
  if(u.origin===f.C.origin){
    if(u.pathname!=='/'||method!=='GET'||Object.keys(o.headers).length||o.credentials!=='omit'||o.redirect!=='manual'||o.cache!=='no-store')throw Error('TEST_PUBLIC_SCOPE');
    publicCount++;emit({type:'public',number:publicCount,path:'/',method,authenticated:false});
    if(f.scenario==='watchdog-heartbeat-missing'){
      o.signal.addEventListener('abort',()=>emit({type:'public-aborted'}),{once:true});
      return new Promise(()=>{});
    }
    if(['parent-crash','timeout','watchdog-both-stopped'].includes(f.scenario))return new Promise(()=>{});
    const getFaults={
      'watchdog-during-get':'exit','watchdog-close-fail':'exit','watchdog-report-fail':'exit',
      'watchdog-disconnect':'disconnect','watchdog-ipc-close-fail':'disconnect','watchdog-error':'error',
    };
    if(publicCount===1&&getFaults[f.scenario]){
      if(f.scenario==='watchdog-report-fail')
        writeFileSync(process.argv.at(-5)+'/diagnostic-report.json','retained report bytes',{flag:'wx'});
      o.signal.addEventListener('abort',()=>emit({type:'public-aborted'}),{once:true});
      await fault(getFaults[f.scenario]);
      return new Promise(()=>{});
    }
    if(publicCount===1&&f.scenario==='watchdog-between-gets')setTimeout(()=>void fault(),30);
    const sequences={'404-302-404':[404,302,404],'root404':[302,302,302,404],'all404':[404,404,404]};
    if(sequences[f.scenario]?.[publicCount-1]===404)return new Response('synthetic offline missing',{status:404,headers:{'content-type':'text/html','cf-ray':'0123456789abcdef-NRT'}});
    if(f.scenario==='html')return new Response('<html>PRIVATE_SYNTHETIC_BODY</html>',{status:200});
    const location=f.scenario==='bad-redirect'?'https://evil.invalid/?token=PRIVATE_QUERY':f.C.team+'/cdn-cgi/access/login?email=PRIVATE_IDENTITY';
    return new Response('',{status:302,headers:{location,'set-cookie':'PRIVATE_SYNTHETIC_COOKIE','cf-ray':'0123456789abcdef-NRT'}});
  }
  throw Error('TEST_NETWORK_BLOCKED');
};
