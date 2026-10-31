// Local emulation of the Access edge. Never bundled or deployed.
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { stagingFixture, ORIGIN, ADMIN, ACCESS_ID, ACCESS_SECRET } from '../../comments/tests/staging-fixture.mjs';
const s=await stagingFixture();globalThis.fetch=s.certFetch;
const token=await s.sign(),generated=fileURLToPath(new URL('../../comments/staging/generated/',import.meta.url));
s.env.ASSETS={fetch:async request=>{
  const path=new URL(request.url).pathname;
  try{return new Response(await readFile(generated+path));}catch{return new Response('',{status:404});}
}};
for(let i=0;i<23;i++)s.db.sql.prepare("INSERT INTO comments(id,case_id,role,nickname,body,created_at,delete_hash) VALUES(?,?,'visitor',?,?,?,?)")
  .run(crypto.randomUUID(),s.id,'森の試験参加者',i===0?'<img src=x onerror=alert(1)> 合成コメント':'合成コメント '+i,Date.now()-86400000+i,'f'.repeat(64));
let publicCalls=0,adminCalls=0,cookieCalls=0,serviceCalls=0,adminDenied=false,fail=false;
const server=http.createServer(async(req,res)=>{
  try{
    let raw='';for await(const c of req)raw+=c;
    if(req.url==='/__test/stats'){
      res.setHeader('Content-Type','application/json');res.end(JSON.stringify({id:s.id,publicCalls,adminCalls,cookieCalls,serviceCalls,
        comments:s.db.sql.prepare('SELECT id,state,role FROM comments ORDER BY seq').all()}));return;
    }
    if(req.url==='/__test/control'){
      const v=JSON.parse(raw);if('adminDenied'in v)adminDenied=v.adminDenied;if('fail'in v)fail=v.fail;
      res.end('{}');return;
    }
    const cookie=(req.headers.cookie||'').split(';').some(x=>x.trim()==='CF_Authorization=synthetic-access-session');
    const service=req.headers['cf-access-client-id']===ACCESS_ID&&req.headers['cf-access-client-secret']===ACCESS_SECRET;
    if(!cookie&&!service || adminDenied&&req.url.startsWith('/admin/')){
      res.writeHead(403,{'Content-Type':'application/json'});res.end('{"error":"ACCESS_DENIED"}');return;
    }
    if(cookie)cookieCalls++;if(service)serviceCalls++;
    if(req.url.startsWith('/v1/'))publicCalls++;
    if(req.url.startsWith('/admin/'))adminCalls++;
    if(fail&&req.url.startsWith('/v1/')){res.writeHead(503,{'Content-Type':'application/json'});res.end('{"error":"SERVICE_UNAVAILABLE"}');return;}
    const headers=new Headers();for(const[k,v]of Object.entries(req.headers))if(v)headers.set(k,Array.isArray(v)?v.join(','):v);
    // Emulated edge overwrites any caller-supplied identity header.
    headers.set('Cf-Access-Jwt-Assertion',token);headers.set('CF-Connecting-IP','198.51.100.24');
    const r=await s.worker.fetch(new Request(ORIGIN+req.url,{method:req.method,headers,body:['GET','HEAD'].includes(req.method)?undefined:raw}),s.env);
    res.writeHead(r.status,Object.fromEntries(r.headers));res.end(await r.text());
  }catch{res.writeHead(500);res.end('{}');}
});
server.listen(0,'127.0.0.1',()=>console.log(JSON.stringify({port:server.address().port})));
