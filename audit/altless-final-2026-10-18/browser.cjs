'use strict';
// Exercise actual generated public HTML; no API decisions or publication writes.
// node browser.cjs /path/to/acceptance-artifact
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(process.argv[2]),site=path.join(root,'site');
const photos=JSON.parse(fs.readFileSync(path.join(root,'recent-public-photos.json')));
const portal=JSON.parse(fs.readFileSync(path.join(site,'portal-data.json')));
const config=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../data/best-shots.json')));
const pairs=photos.filter(r=>r.last_rejected_boundary_reason==='multiple_subject_separator');
let assertions=0;function check(a,b){assert.deepEqual(a,b);assertions++}
const server=http.createServer((req,res)=>{
 const file=path.resolve(site,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
 if(!file.startsWith(site+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return}
 res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/html');res.end(fs.readFileSync(file));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox',...(process.env.CHROMIUM_SINGLE_PROCESS?['--single-process','--no-zygote','--disable-gpu']:[])]});
 const context=await browser.newContext({viewport:{width:1280,height:1000},reducedMotion:'reduce'});const page=await context.newPage();
 const issues=[],writes=[];page.on('pageerror',e=>issues.push(e.message));
 page.on('request',r=>{if(r.method()!=='GET')writes.push(r.method()+' '+r.url())});
 check(pairs.length,3);check(portal.observations.length,933);check(new Set(portal.observations.map(r=>r.src)).size,933);
 const screenshots=path.join(root,'screenshots');fs.mkdirSync(screenshots,{recursive:true});
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:width===390?844:1000});
  for(const name of ['ニガイグチモドキ','ヤマドリタケモドキ','ムラサキヤマドリタケ','アカヤマドリ']){
   await page.goto(base+'/'+encodeURIComponent(name)+'.html',{waitUntil:'domcontentloaded'});
   await page.locator('.shared-subject-note').waitFor();
   await page.waitForFunction(()=>getComputedStyle(document.querySelector('.gallery')).visibility==='visible',null,{timeout:60000});
   for(const row of pairs.filter(r=>r.last_rejected_boundary_text.split(/[&＆]/).includes(name))){
    const anchor=page.locator('a.gallery-item').filter({has:page.locator('img[src='+JSON.stringify(row.src)+']')});
    check(await anchor.count(),1);check(await anchor.locator('.shared-subject-indicator').innerText(),'複数種が写る写真');
    if(!portal.observations.some(r=>r.src===row.src))check(await anchor.locator('.thumb-fav').count(),0);
    check(portal.observations.filter(r=>r.src===row.src).length<=1,true);
    await anchor.scrollIntoViewIfNeeded();
    // Natural image decoding exercises the real public CDN, not a substituted fixture.
    await page.waitForFunction(src=>{const i=[...document.images].find(i=>i.getAttribute('src')===src);return i&&i.complete&&i.naturalWidth>0},row.src,{timeout:30000});
    check(await anchor.locator('img').evaluate(i=>i.naturalWidth>0),true);
    await anchor.click();await page.waitForSelector('.lg-current .lg-object');
    await page.waitForSelector('.lg-fav-btn',{state:'attached'});
    if(!portal.observations.some(r=>r.src===row.src)){
     await page.waitForFunction(()=>document.querySelector('.lg-fav-btn').disabled);
     check(await page.locator('.lg-fav-btn').isVisible(),false);
     check(await page.locator('.lg-fav-btn').isDisabled(),true);
    }
    await page.locator('.lg-close').click();await page.waitForSelector('.lg-outer',{state:'hidden'});
   }
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await page.locator('#detail-title').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(screenshots,width+'-'+name+'.png')});
  }
  const seen=new Set();
  for(const filename of fs.readdirSync(site).filter(f=>/^best-shots(?:-\d{4})?\.html$/.test(f))){
   await page.goto(base+'/'+filename,{waitUntil:'domcontentloaded'});
   for(const id of await page.locator('[data-selection-id]').evaluateAll(es=>es.map(e=>e.dataset.selectionId)))seen.add(id);
   for(const img of await page.locator('.best-shot-photo img').all()){
    await img.scrollIntoViewIfNeeded();
    await img.evaluate(i=>i.decode());
    check(await img.evaluate(i=>i.complete&&i.naturalWidth>0),true);
   }
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  }
  check([...seen].sort(),config.entries.map(e=>e.selection_id).sort());
  await page.goto(base+'/best-shots-2025.html',{waitUntil:'domcontentloaded'});
  await page.locator('.annual-best img').evaluate(i=>i.decode());
  await page.screenshot({path:path.join(screenshots,width+'-best-shots.png')});
  await page.goto(base+'/'+encodeURIComponent('ブドウニガイグチ')+'.html',{waitUntil:'domcontentloaded'});
  check((await page.locator('body').innerText()).includes('図鑑情報は現在整理中です'),true);
 }
 await page.goto(base+'/index.html',{waitUntil:'domcontentloaded'});
 for(const name of ['ニガイグチモドキ','ヤマドリタケモドキ','ムラサキヤマドリタケ','アカヤマドリ']){
  await page.fill('.index-search-input',name);
  await page.waitForFunction(name=>document.querySelector('.index-search-results').textContent.includes(name),name);
  check(await page.locator('.index-search-results a').evaluateAll((links,n)=>links.filter(a=>decodeURIComponent(a.getAttribute('href').split('?')[0])===n+'.html').length,name),1);
 }
 await page.goto(base+'/records.html',{waitUntil:'domcontentloaded'});
 const counts=new Map();for(const row of portal.observations){const url=row.article.url;const c=counts.get(url)||{photos:0,names:new Set()};c.photos++;c.names.add(row.gallery_name);counts.set(url,c)}
 for(const card of await page.locator('a.record-card').all()){
  const c=counts.get(await card.getAttribute('href'));check(!!c,true);
  const text=await card.locator('.record-card-meta').innerText();check(text.includes(c.photos+'枚')&&text.includes(c.names.size+'種類'),true);
 }
 // Actual read-only management rows from the same authenticated capture; route
 // only GET endpoints. Any accidental decision/save request fails this audit.
 const admin=JSON.parse(fs.readFileSync(path.join(root,'admin-readonly.json')));
 await page.setViewportSize({width:1280,height:1000});
 const app={csrf:'readonly-audit',observations:portal.observations,best_shots:config,cases:[],identified:[],notices:[],master:[],knowledge:[],preview:{},repo:{gh_authenticated:false},feature_facets:{},counts:{best_shots:12,annual_years:2,research_open:66,research_identified:0,active_notices:0,master:141,sources:419,knowledge_batches:0},portal_source:'actual published-only acceptance capture',portal_observation_count:933};
 await page.route('http://admin-audit.test/**',route=>{
  const req=route.request(),url=new URL(req.url());
  if(req.method()!=='GET')return route.abort();
  if(url.pathname==='/api/state')return route.fulfill({json:app});
  if(url.pathname==='/api/sync/state')return route.fulfill({json:admin.dashboard});
  if(url.pathname==='/api/sync/candidates'){
   const q=url.searchParams.get('q')||'',group=url.searchParams.get('group')||'';
   const rows=admin.rows.filter(r=>(!group||r.group===group)&&(!q||JSON.stringify(r).includes(q)));
   return route.fulfill({json:{rows:rows.slice(0,30),total:rows.length,page:1,page_size:30,bundle_id:admin.dashboard.bundle_id}});
  }
  const filename={'/':'index.html','/admin.js':'admin.js','/admin.css':'admin.css','/deletions.js':'deletions.js'}[url.pathname];
  if(filename)return route.fulfill({body:fs.readFileSync(path.resolve(__dirname,'../../admin/static',filename)),contentType:filename.endsWith('.js')?'text/javascript':filename.endsWith('.css')?'text/css':'text/html'});
  return route.fulfill({status:404,body:''});
 });
 await page.goto('http://admin-audit.test/');await page.waitForSelector('#cards .card');await page.click('[data-page=sync]');await page.waitForSelector('#sync-list .item');
 await page.selectOption('#sync-group','unlisted');
 for(const name of ['オオジョウゴタケ？','フモトニガイグチ','アブラシメジモドキ','フジアザミ']){
  await page.fill('#sync-search',name);await page.click('#sync-search-button');
  await page.waitForFunction(name=>document.querySelector('#sync-list').textContent.includes(name),name);
  const text=await page.locator('#sync-list').innerText();check(text.includes(name),true);
  if(name==='フジアザミ')check(text.includes('キノコ以外')||text.includes('キノコではない'),true);
 }
 await page.fill('#sync-search','');await page.click('#sync-search-button');
 await page.screenshot({path:path.join(screenshots,'1280-admin-unlisted.png')});
 check(issues,[]);check(writes,[]);
 fs.writeFileSync(path.join(root,'browser-result.json'),JSON.stringify({result:'PASS',assertions,viewports:[1280,390],actual_cdn_decoding:true,publication:'NOT_ATTEMPTED'},null,2)+'\n');
 await browser.close();server.close();console.log('PASS: '+assertions+' real generated-page Chromium assertions');
})().catch(e=>{console.error(e);server.close();process.exitCode=1;process.exit(1)});
