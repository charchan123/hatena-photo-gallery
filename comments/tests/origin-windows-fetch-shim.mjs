// Only test subprocesses import this. It is excluded from the Windows packet.
// There is deliberately no fallback to the native network implementation.
import {readFileSync,writeFileSync,appendFileSync} from 'node:fs';
const f=JSON.parse(readFileSync(process.env.ORIGIN_TEST_FIXTURE,'utf8'));
const state=process.env.ORIGIN_TEST_STATE,events=process.env.ORIGIN_TEST_EVENTS;
const RealDate=Date;
globalThis.Date=class extends RealDate{constructor(...a){super(...(a.length?a:[f.now]));}static now(){return f.now;}};
if(['parent-crash','close-fail','enable-response-lost'].includes(f.scenario)&&process.argv.includes('watchdog')){
  const timer=setTimeout;globalThis.setTimeout=(fn,ms,...a)=>timer(fn,ms===90000?1500:ms,...a);
}
const emit=v=>appendFileSync(events,JSON.stringify(v)+'\n');
let publicCount=0;
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
        if(!body.enabled&&(f.scenario==='no-close-permission'||f.scenario==='close-fail'&&current.enabled))
          return Response.json({success:false},{status:403});
        writeFileSync(state,JSON.stringify(body));
        if(body.enabled&&f.scenario==='enable-response-lost')throw Error('TEST_ENABLE_RESPONSE_LOST');
      }
      return Response.json({success:true,result:JSON.parse(readFileSync(state))});
    }
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
    if(f.scenario==='parent-crash'||f.scenario==='timeout')return new Promise(()=>{});
    const sequences={'404-302-404':[404,302,404],'root404':[302,302,302,404],'all404':[404,404,404]};
    if(sequences[f.scenario]?.[publicCount-1]===404)return new Response('synthetic offline missing',{status:404,headers:{'content-type':'text/html','cf-ray':'0123456789abcdef-NRT'}});
    if(f.scenario==='html')return new Response('<html>PRIVATE_SYNTHETIC_BODY</html>',{status:200});
    const location=f.scenario==='bad-redirect'?'https://evil.invalid/?token=PRIVATE_QUERY':f.C.team+'/cdn-cgi/access/login?email=PRIVATE_IDENTITY';
    return new Response('',{status:302,headers:{location,'set-cookie':'PRIVATE_SYNTHETIC_COOKIE','cf-ray':'0123456789abcdef-NRT'}});
  }
  throw Error('TEST_NETWORK_BLOCKED');
};
