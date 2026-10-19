'use strict';
// Real generated HTML, public baseline thumbnails fetched by GET, isolated stress photographs.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(process.argv[2]),summary=JSON.parse(fs.readFileSync(path.join(root,'summary.json'))),photos=JSON.parse(fs.readFileSync(path.join(root,'photo-map.json'))),shots=path.join(root,'screenshots');
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return}
 res.setHeader('Content-Type',({'.html':'text/html','.css':'text/css','.js':'text/javascript','.webp':'image/webp'})[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']}),context=await browser.newContext(),page=await context.newPage();page.setDefaultTimeout(15000);
 const issues=[],metrics=[];page.on('pageerror',e=>issues.push(e.message));let assertions=0;const check=(a,b)=>{assert.deepEqual(a,b);assertions++};
 await page.route('**/*',route=>{
  const url=new URL(route.request().url());
  if(url.hostname==='127.0.0.1')return route.continue();
  if(photos[url.href]){const p=photos[url.href];return route.fulfill({body:fs.readFileSync(path.join(root,p.file)),contentType:p.mime});}
  if(url.hostname==='fixture-photos.example.test')return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="800" height="${parseInt(url.pathname.slice(1))%2?600:900}"><rect width="800" height="900" fill="#dcebd4"/><text x="35" y="160" font-size="45">Isolated photo ${url.pathname.slice(1)}</text></svg>`});
  return route.abort();
 });
 async function ready(){await page.evaluate(()=>document.fonts.ready);for(const img of await page.locator('.best-shot-photo img').all()){await img.scrollIntoViewIfNeeded();await img.evaluate(i=>i.decode());check(await img.evaluate(i=>i.naturalWidth>0),true);}await page.waitForFunction(()=>parseFloat(getComputedStyle(document.body).opacity)>.99);}
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:1000});let original;
  for(const variant of ['before','after']){
   await page.goto(`${base}/${variant}-public/best-shots.html`);await ready();
   const ids=await page.locator('.best-shot-month .best-shot-card').evaluateAll(es=>es.map(e=>e.dataset.selectionId));
   const hrefs=await page.locator('.best-shot-photo').evaluateAll(es=>es.map(e=>e.getAttribute('href')));
   if(variant==='before')original={ids,hrefs};else check({ids,hrefs},original);
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(shots,`${width}-${variant}-public.png`),animations:'disabled'});
  }
  for(const c of summary.cases){
   await page.goto(`${base}/month-${c.count}/best-shots.html`);await ready();
   const month=page.locator('.best-shot-month').first(),cards=month.locator('.best-shot-card');
   check(await month.locator('h2').innerText(),'10月');check(await cards.count(),c.count);check(await cards.evaluateAll(es=>es.map(e=>e.dataset.selectionId)),c.ordered_ids);
   check(await page.locator('.best-shot-month').nth(1).locator('h2').innerText(),'9月');
   check(await page.locator('.annual-best [data-selection-id]').getAttribute('data-selection-id'),c.annual);
   check(await month.locator('.best-shot-grid').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length),width===1280?2:1);
   const rects=await cards.evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom}}));
   check(rects.every(r=>r.x>=0&&r.right<=width),true);
   for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++)check(!(rects[i].x<rects[j].right&&rects[j].x<rects[i].right&&rects[i].y<rects[j].bottom&&rects[j].y<rects[i].bottom),true);
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   if([3,35].includes(c.count)){
    await cards.first().scrollIntoViewIfNeeded();await page.screenshot({path:path.join(shots,`${width}-month-${c.count}-first.png`),animations:'disabled'});
    await cards.last().scrollIntoViewIfNeeded();await page.screenshot({path:path.join(shots,`${width}-month-${c.count}-last.png`),animations:'disabled'});
   }
   await page.getByRole('link',{name:'2025年',exact:true}).click();await ready();check(await page.locator('.best-shot-month .best-shot-card').count(),1);check(await page.locator('.annual-best [data-selection-id]').getAttribute('data-selection-id'),'older');
   metrics.push({width,count:c.count,monthly_ids:c.ordered_ids,columns:width===1280?2:1,no_overflow:true,no_overlap:true,annual:c.annual});
  }
 }
 check(issues,[]);await browser.close();server.close();fs.writeFileSync(path.join(root,'result.json'),JSON.stringify({assertions,summary,metrics,issues},null,2));console.log(`PASS: ${assertions} Chromium Best Shot public-page assertions (1/3/4/10/30/35; desktop and mobile)`);
})().catch(e=>{console.error(e);server.close();process.exit(1)});
