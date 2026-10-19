'use strict';
// Live native widgets are READ ONLY. All clicks that add stars use an in-memory local mock.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(process.argv[2]),fixture=JSON.parse(fs.readFileSync(path.join(root,'fixture.json'))),shots=path.join(root,'screenshots');
let assertions=0,activeBrowser;const check=(a,b)=>{assert.deepEqual(a,b);assertions++};
const icons={yellow:'b308fc4da238502b2ae1',green:'939cc2e2c1ead7ca78bb',red:'db39383641aa4d682cf1',blue:'92c936f0e7c2130ee0e5',purple:'4256283b0392d6aff7a0'};
function mockSource(mode){return `(${function(mode,icons){
 const makeStar=color=>{const a=document.createElement('a');a.href='https://profile.hatena.ne.jp/fixture-user/';a.style.cssText='display:inline-flex;align-items:center;position:relative;width:11px;height:16px;margin:0 .5px';const im=document.createElement('img');im.src='https://s.hatena.ne.jp/js/widget/'+icons[color]+'.svg';im.width=11;im.height=10;im.title='★('+color+')';im.alt='fixture-user';a.append(im);return a};
 document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{
  for(const row of document.querySelectorAll('article.record-star-entry')){
   const uri=row.querySelector('a.record-star-permalink').href,mount=row.querySelector('.record-stars-native'),host=document.createElement('span');host.dataset.hatenaStar='';mount.append(host);const s=host.attachShadow({mode:'open'});
   const control=document.createElement('span');control.setAttribute('part','star-button-container');control.style.cssText='display:inline-flex;position:relative;width:32px;height:16px;margin:0 -4px';const frame=document.createElement('iframe');frame.src='/mock-control?uri='+encodeURIComponent(uri)+'&anonymous='+(mode==='anonymous');frame.style.cssText='border:0;width:32px;height:24px';control.append(frame);s.append(control);
   const count={zero:0,few:5,many:130,collapsed:4,anonymous:3,unknown:0}[mode]??1;
   for(let i=0;i<count;i++)s.append(makeStar(['green','red','blue','purple','yellow'][i%5]));
   if(mode==='collapsed'){const b=document.createElement('button');b.type='button';b.textContent='126';s.append(b);}
   if(mode==='unknown')s.append(document.createElement('aside'));
   window.addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==frame.contentWindow||e.data?.type!=='ISOLATED_ADD')return;s.append(makeStar('yellow'))});
  }
 },80));
}.toString()})(${JSON.stringify(mode)},${JSON.stringify(icons)});`;}
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://localhost');
 if(url.pathname==='/mock-control'){
  const anonymous=url.searchParams.get('anonymous')==='true';res.setHeader('Content-Type','text/html');res.end('<!doctype html><meta charset=utf-8><style>body{margin:0}button{width:32px;height:24px;padding:0}</style><button aria-label="'+(anonymous?'ログイン（隔離）':'スター追加（隔離）')+'">☆</button><script>document.querySelector("button").onclick=()=>'+(anonymous?'document.querySelector("button").textContent="ログイン"':'parent.postMessage({type:"ISOLATED_ADD"},location.origin)')+'</script>');return;
 }
 const file=path.resolve(root,'.'+decodeURIComponent(url.pathname));
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return}
 res.setHeader('Content-Type',({'.html':'text/html','.css':'text/css','.js':'text/javascript','.webp':'image/webp','.png':'image/png','.json':'application/json'})[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const browser=activeBrowser=await chromium.launch({headless:true,args:['--no-sandbox']}),network=[],writes=[],errors=[],metrics=[],assetCache=new Map();let liveTemplate;
 async function context(mode='live',options={}){
  const c=await browser.newContext(options);await c.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());
   if(req.method()!=='GET'||/(?:star\.add|star\.delete|\/stars?\/(?:add|delete|remove))/.test(u.pathname)){writes.push({method:req.method(),host:u.host,path:u.pathname});return route.abort()}
   if(u.hostname==='127.0.0.1')return route.continue();
   if(u.origin==='https://charchan123.github.io'&&u.pathname.startsWith('/hatena-photo-gallery/')){
    const relative=u.pathname.slice('/hatena-photo-gallery/'.length),file=path.resolve(root,'after',relative);
    if(!file.startsWith(path.join(root,'after')+path.sep)||!fs.existsSync(file))return route.abort();
    return route.fulfill({body:fs.readFileSync(file),contentType:({'.html':'text/html','.js':'text/javascript','.css':'text/css','.webp':'image/webp','.png':'image/png'})[path.extname(file)]||'application/octet-stream'});
   }
   if(u.href==='https://s.hatena.ne.jp/js/HatenaStar.js'&&mode!=='live')return mode==='error'?route.abort():route.fulfill({body:mockSource(mode),contentType:'text/javascript'});
   if(fixture.photos[u.href]){const p=fixture.photos[u.href];return route.fulfill({body:fs.readFileSync(path.join(root,p.file)),contentType:p.mime});}
   if(u.hostname==='s.hatena.ne.jp'){
    if(u.pathname.startsWith('/js/')&&/\.(?:js|css|svg)$/.test(u.pathname)){
     if(!assetCache.has(u.href))assetCache.set(u.href,(async()=>{const r=await route.fetch({timeout:20000});return {body:await r.body(),status:r.status(),contentType:r.headers()['content-type']||'application/octet-stream'}})());
     return route.fulfill(await assetCache.get(u.href));
    }
    return route.continue();
   }
   // Public original articles may be read, but no unrelated trackers/images are needed.
   if(u.hostname==='exsudoporus-ruber.hatenablog.jp'&&req.resourceType()==='document')return route.continue();
   if(req.resourceType()==='script'&&(/\.hatena\.ne\.jp$|\.st-hatena\.com$|\.hatenablog\.com$/.test(u.hostname)))return route.continue();
   return route.abort();
  });
  c.on('response',r=>{const u=new URL(r.url());if(u.hostname==='s.hatena.ne.jp')network.push({mode,path:u.pathname,status:r.status()})});
  return c;
 }
 async function dates(p){return p.locator('.record-preview-date').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {y:r.y,text:e.textContent}}));}
 async function bounds(p){
  check(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  for(const row of await p.locator('.record-preview-row').all())check(await row.evaluate(e=>{const r=e.getBoundingClientRect();return Array.from(e.querySelectorAll('.record-preview-date,.record-stars,.record-stars-total')).every(n=>{const x=n.getBoundingClientRect();return x.left>=r.left-.5&&x.right<=r.right+.5})}),true);
  check(await p.locator('a a, a .record-stars, a iframe').count(),0);
 }
 const nativeButtons=[];
 for(const width of [1280,768,390,320]){
  const live=await context('live',{hasTouch:width<=768,isMobile:width<=390}),p=await live.newPage();p.on('pageerror',e=>errors.push(e.message));p.setDefaultTimeout(20000);
  await p.setViewportSize({width,height:1000});await p.goto(base+'/before/new-top.html',{waitUntil:'domcontentloaded'});await p.evaluate(()=>document.fonts.ready);await p.locator('.record-preview-list').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(shots,`${width}-before.png`),animations:'disabled'});
  await p.goto(base+'/after/new-top.html',{waitUntil:'domcontentloaded'});await p.evaluate(()=>document.fonts.ready);const initial=await dates(p);
  await p.waitForFunction(expected=>{const rows=[...document.querySelectorAll('.record-star-entry')];return rows.length===expected.length&&rows.every((r,i)=>r.querySelector('.record-stars-native[data-ready]')&&(expected[i]===0||r.querySelector('.record-stars').dataset.total===String(expected[i])))},fixture.records.map(r=>r.total));
  for(let i=0;i<fixture.records.length;i++){
   const row=p.locator('.record-star-entry').nth(i),f=fixture.records[i];check(await row.locator('a.record-star-permalink').getAttribute('href'),f.uri);
   const iframe=row.locator('iframe');check(new URL(await iframe.getAttribute('src')).searchParams.get('url'),f.uri);
   const native=await row.locator('[data-hatena-star]').evaluate(e=>Array.from(e.shadowRoot.children).filter(c=>!c.matches('style,[part~=star-button-container]')).map(c=>({kind:c.tagName==='A'?'star':c.tagName==='BUTTON'?'count':'unknown',count:c.tagName==='BUTTON'?Number(c.textContent):1,color:c.querySelector('img')?.title})));
   check(native.reduce((n,e)=>n+e.count,0),f.total);check(await row.locator('.record-stars-ellipsis').isVisible(),await row.locator('[data-record-star-hidden]').count()>0);
   if(f.total>0){check(await row.locator('.record-stars-total').innerText(),'（'+f.total+'）');liveTemplate=await row.locator('[data-hatena-star]').evaluate(e=>e.shadowRoot.innerHTML);}
   else check(await row.locator('.record-stars-total').innerText(),'スター'); // Do not invent an empty-DOM count.
  }
  const after=await dates(p);check(after.map((r,i)=>Math.abs(r.y-initial[i].y)),[0,0,0]);await bounds(p);
  await p.locator('.record-preview-list').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(shots,`${width}-after.png`),animations:'disabled'});metrics.push({phase:'live',width,totals:fixture.records.map(r=>r.total),date_shift:after.map((r,i)=>r.y-initial[i].y),no_overflow:true});
  // Inspect native controls, never click real add buttons.
  if(width===390)for(const frame of p.frames().filter(f=>f.url().includes('/add_star_iframe.html')))nativeButtons.push({uri:new URL(frame.url()).searchParams.get('url'),controls:await frame.locator('button,a').evaluateAll(es=>es.map(e=>({tag:e.tagName,label:e.getAttribute('aria-label')||e.getAttribute('title')||e.textContent})).slice(0,8))});
  await live.close();
 }
 // A real Pages origin and a cross-origin blog embed are simulated by browser-only fulfilment.
 // Real Star endpoints remain read-only; third-party cookies are explicitly restricted when CDP supports it.
 const embedContext=await context('live',{viewport:{width:390,height:1000},hasTouch:true,isMobile:true}),embed=await embedContext.newPage();
 let cookieRestriction=false;
 try{const cdp=await embedContext.newCDPSession(embed);await cdp.send('Network.enable');await cdp.send('Network.setCookieControls',{enableThirdPartyCookieRestriction:true,disableThirdPartyCookieMetadata:true,disableThirdPartyCookieHeuristics:true});cookieRestriction=true;}catch{}
 const publicURL=fixture.live_site.new_top_url;
 await embed.goto(publicURL,{waitUntil:'domcontentloaded'});await embed.waitForFunction(n=>document.querySelector('.record-stars')?.dataset.total===String(n),fixture.records[0].total);await bounds(embed);
 const parentURL='https://exsudoporus-ruber.hatenablog.jp/__isolated_record_star_preview__';
 await embed.route(parentURL,r=>r.fulfill({contentType:'text/html',body:'<!doctype html><meta name="viewport" content="width=device-width"><style>body{margin:0}iframe{width:100%;height:1200px;border:0}</style><script>window.Hatena={Star:{SiteConfig:{parentUnchanged:true}}}</script><iframe title="隔離した新トップページ" src="'+publicURL+'"></iframe>'}));
 await embed.goto(parentURL,{waitUntil:'domcontentloaded'});await embed.locator('iframe').waitFor({state:'attached'});
 let pageFrame;for(let i=0;i<100;i++){pageFrame=embed.frames().find(f=>f.url()===publicURL);if(pageFrame)break;await embed.waitForTimeout(50)}
 assert.ok(pageFrame);await pageFrame.waitForFunction(n=>document.querySelector('.record-stars')?.dataset.total===String(n),fixture.records[0].total);
 check(await embed.evaluate(()=>window.Hatena.Star.SiteConfig),{parentUnchanged:true});
 const embeddedURIs=await pageFrame.locator('.record-star-permalink').evaluateAll(es=>es.map(e=>e.href));check(embeddedURIs,fixture.records.map(r=>r.uri));
 check(await pageFrame.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 metrics.push({phase:'Pages-origin-and-cross-origin-embed',width:390,third_party_cookies_restricted:cookieRestriction,uris:embeddedURIs,read_only:true});await embedContext.close();
 for(const mode of ['zero','few','many','collapsed','anonymous','unknown','error']){
  const c=await context(mode),q=await c.newPage();q.on('pageerror',e=>errors.push(e.message));
  for(const width of [1280,768,390,320,1024,640]){
   await q.setViewportSize({width,height:1000});await q.goto(base+'/after/new-top.html',{waitUntil:'domcontentloaded'});await q.evaluate(()=>{document.querySelectorAll('.record-preview-title').forEach(e=>e.textContent+=' 長い記事タイトル'.repeat(35));});
   if(mode==='error')await q.waitForTimeout(150);else await q.waitForSelector('.record-stars-native [data-hatena-star]',{state:'attached'});
   const expected={zero:null,few:5,many:130,collapsed:130,anonymous:3,unknown:null,error:null}[mode];
   if(expected!==null)await q.waitForFunction(n=>[...document.querySelectorAll('.record-stars')].every(e=>e.dataset.total===String(n)),expected);
   else await q.waitForFunction(()=>[...document.querySelectorAll('.record-stars-total')].every(e=>e.textContent==='スター'));
   await bounds(q);const rows=q.locator('.record-star-entry');check(await rows.count(),3);
   if(['many','collapsed'].includes(mode))check(await rows.first().locator('.record-stars-ellipsis').isVisible(),true);
   if(mode==='unknown'||mode==='error')check(await q.locator('.record-stars-native[data-ready]').count(),0);
   if(width===390&&mode==='many'){await q.locator('.record-preview-list').scrollIntoViewIfNeeded();await q.screenshot({path:path.join(shots,'390-many-130.png'),animations:'disabled'});}
   metrics.push({phase:mode,width,total:expected,no_overflow:true});
  }
  if(mode==='few'){
   const row=q.locator('.record-star-entry').first(),frame=q.frameLocator('iframe').first();
   const start=q.url();await frame.getByRole('button',{name:'スター追加（隔離）'}).click();await q.waitForFunction(()=>document.querySelector('.record-stars').dataset.total==='6');check(q.url(),start);
   await frame.getByRole('button',{name:'スター追加（隔離）'}).focus(); // Keyboard handled below by locator.press.
   await frame.getByRole('button',{name:'スター追加（隔離）'}).press('Space');await q.waitForFunction(()=>document.querySelector('.record-stars').dataset.total==='7');check(q.url(),start);
   // The distinct title link remains keyboard-operable; fulfil only this navigation.
   await q.route(fixture.records[0].uri,r=>r.fulfill({body:'<!doctype html><title>Isolated article destination</title>',contentType:'text/html'}));
   await row.locator('a.record-star-permalink').press('Enter');await q.waitForURL(fixture.records[0].uri);check(q.url(),fixture.records[0].uri);
  }
  await c.close();
 }
 for(const mode of ['few','many']){
  const c=await context(mode,{viewport:{width:390,height:844},hasTouch:true,isMobile:true}),q=await c.newPage();
  await q.goto(base+'/after/new-top.html');await q.waitForFunction(n=>document.querySelector('.record-stars').dataset.total===String(n),mode==='few'?5:130);await bounds(q);
  if(mode==='few'){const url=q.url();await q.frameLocator('iframe').first().getByRole('button',{name:'スター追加（隔離）'}).tap();await q.waitForFunction(()=>document.querySelector('.record-stars').dataset.total==='6');check(q.url(),url);}
  metrics.push({phase:'touch-'+mode,width:390,no_overflow:true});await c.close();
 }
 check(writes,[]);check(errors,[]);await browser.close();server.close();
 fs.writeFileSync(path.join(root,'result.json'),JSON.stringify({assertions,fixture,metrics,nativeButtons,network,writes,errors,real_star_addition:'NOT_ATTEMPTED',authenticated_addition:'UNVERIFIED',zero_total:'Empty native DOM has no ready marker: no inferred zero is displayed',native_template_sha256:crypto.createHash('sha256').update(liveTemplate||'').digest('hex')},null,2));
 console.log(`PASS: ${assertions} Hatena Star assertions; original permalinks, native colours/counts, four widths and zoom-equivalent widths; no live star writes`);
})().catch(async e=>{console.error(e);if(activeBrowser){for(const c of activeBrowser.contexts())for(const p of c.pages())try{await p.screenshot({path:path.join(shots,'failure-'+p.viewportSize().width+'.png')});console.error('Failure geometry',await p.locator('.record-preview-row').evaluateAll(es=>es.map(e=>({width:e.getBoundingClientRect().width,meta:e.querySelector('.record-preview-meta')?.getBoundingClientRect().width,stars:e.querySelector('.record-stars')?.getBoundingClientRect().width,html:e.querySelector('.record-stars')?.innerHTML}))));}catch{}await activeBrowser.close()}server.close();process.exit(1)});
