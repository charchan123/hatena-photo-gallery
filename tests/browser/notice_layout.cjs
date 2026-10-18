'use strict';
// Render actual generated portal HTML; synthetic notices exist only in the output fixture.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(process.argv[2]),fixture=JSON.parse(fs.readFileSync(path.join(root,'fixture.json')));
const shots=path.join(root,'screenshots');fs.mkdirSync(shots,{recursive:true});
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return}
 const type={'.css':'text/css','.js':'text/javascript','.html':'text/html','.webp':'image/webp','.json':'application/json'}[path.extname(file)];
 res.setHeader('Content-Type',type||'application/octet-stream');res.end(fs.readFileSync(file));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:1000}}),page=await context.newPage();
 page.setDefaultTimeout(10000);
 await page.clock.install({time:new Date(fixture.now)});
 await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
 let assertions=0;const check=(a,b)=>{assert.deepEqual(a,b);assertions++};const metrics=[],issues=[];
 page.on('pageerror',e=>issues.push(e.message));
 async function positions(){return page.evaluate(()=>{
  const result={};for(const name of ['research','best-shots','guide','season','features']){
   const card=document.querySelector('.portal-card--'+name),scope=name==='research'||name==='best-shots'?card:card.closest('.portal-guide-row').querySelector('.portal-guide-note');
   const title=scope.querySelector('strong').getBoundingClientRect(),description=scope.querySelector('small').getBoundingClientRect();
   const rect=card.getBoundingClientRect();result[name]={titleY:title.y,descriptionY:description.y,cardHeight:rect.height};
  }return result;
 })}
 const effect=()=>page.locator('.update-badge--new').first().evaluate(el=>{
  const c=getComputedStyle(el,'::after');return {duration:c.animationDuration,delay:c.animationDelay,timing:c.animationTimingFunction,opacity:c.opacity,transform:c.transform,width:c.width,background:c.backgroundImage,overflow:getComputedStyle(el).overflow,borderRadius:getComputedStyle(el).borderRadius};
 });
 for(const width of [1280,768,390]){
  await page.setViewportSize({width,height:1000});let baseline;
  for(const state of fixture.states){
   await page.goto(base+'/'+state+'/new-top.html');await page.evaluate(()=>document.fonts.ready);
   const found=await positions();console.log('Layout',width,state,JSON.stringify(found));if(state==='off')baseline=found;
   for(const name of Object.keys(found)){
    check(found[name].titleY,baseline[name].titleY);check(found[name].descriptionY,baseline[name].descriptionY);check(found[name].cardHeight,baseline[name].cardHeight);
   }
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   check(await page.locator('.portal-update-note:not([hidden])').count(),fixture.notice_counts[state]);
   for(const badge of await page.locator('.portal-update-note:not([hidden]) .update-badge').all()){
    const style=await badge.evaluate(e=>({height:e.getBoundingClientRect().height,weight:getComputedStyle(e).fontWeight,transform:getComputedStyle(e).transform}));
    check(style.height,22);check(style.weight,'700');check(style.transform,'none');
   }
   if(state==='long'){const summaries=await page.locator('.portal-update-summary').evaluateAll(es=>es.map(e=>({overflow:getComputedStyle(e).textOverflow,scroll:e.scrollWidth,client:e.clientWidth,visible:!!e.getClientRects().length})));console.log('Long summaries',JSON.stringify(summaries));check(summaries.filter(e=>e.visible).every(e=>e.overflow==='ellipsis'&&e.scroll>e.client),true);}
   if(state==='new'){
    const recordBadges=page.locator('.record-preview-heading .update-badge--new:not([hidden])');check(await recordBadges.count()>0,true);
    for(const badge of await recordBadges.all())check(await badge.evaluate(e=>e.getBoundingClientRect().height),22);
    await page.locator('.portal-records-hero').screenshot({path:path.join(shots,`${width}-records-new.png`),animations:'disabled'});
   }
   if(['off','both','long'].includes(state)){
    await page.locator('.portal-independent-links').screenshot({path:path.join(shots,`${width}-${state}-cards.png`),animations:'disabled'});
    await page.locator('.portal-guide-list').screenshot({path:path.join(shots,`${width}-${state}-guide.png`),animations:'disabled'});
   }
   metrics.push({width,state,positions:found});
  }
  // Expiry and BFCache-style restoration exercise the unchanged production refresh script.
  await page.goto(base+'/new/new-top.html');const visible=await positions();
  await page.evaluate(()=>{document.querySelectorAll('.portal-update-note').forEach(e=>e.dataset.noticeEnd=String(Date.now()-1));window.dispatchEvent(new Event('pageshow'))});
  check(await page.locator('.portal-update-note:not([hidden])').count(),0);check(await positions(),visible);
 }
 // Freeze the same real CSS animation at multiple points in its 5.4-second cycle.
 const samples={};
 for(const variant of ['before','after']){
  await page.goto(base+'/badges.html');await page.locator('#badge-css').evaluate((e,v)=>e.href=v+'.css',variant);
  await page.waitForFunction(v=>document.querySelector('#badge-css').sheet&&document.querySelector('#badge-css').sheet.href.endsWith(v+'.css'),variant);
  await page.locator('#label').evaluate((e,v)=>e.textContent=v==='before'?'Before · published main':'After · Draft PR #123',variant);
  samples[variant]=[];
  for(const time of [0,3942,3996,4320,4752,4860,5400]){
   await page.evaluate(t=>document.getAnimations().forEach(a=>{a.pause();a.currentTime=t}),time);
   const value=await effect();check(value.duration,'5.4s');check(value.timing,'linear');check(value.overflow,'hidden');
   samples[variant].push({time,...value});
  }
  await page.screenshot({path:path.join(shots,`badges-${variant}.png`)});
  // Captured live keyframe phases, without disabling or replacing the CSS animation.
  for(const time of [3942,4320,4752]){
   await page.evaluate(t=>document.getAnimations().forEach(a=>a.currentTime=t),time);
   await page.locator('.samples').screenshot({path:path.join(shots,`sheen-${variant}-${time}.png`)});
  }
 }
 for(let i=0;i<samples.before.length;i++){
  for(const key of ['duration','delay','timing','opacity','background'])check(samples.before[i][key],samples.after[i][key]);
  // Relative width/travel stay exactly 38% / 480%; the pill's width is intentionally redesigned.
  const normalize=v=>{const m=v.transform.match(/matrix\(([^)]+)\)/)[1].split(',').map(Number);return [m[0],m[1],m[2],m[3],Number((m[4]/parseFloat(v.width)).toFixed(4)),m[5]]};
  const a=normalize(samples.before[i]),b=normalize(samples.after[i]);for(let j=0;j<a.length;j++)check(Math.abs(a[j]-b[j])<.002,true);
 }
 await page.goto(base+'/new/new-top.html');
 const delays=await page.locator('.portal-update-note .update-badge--new').evaluateAll(es=>es.map(e=>({card:e.closest('.portal-card')?.className||'guide',delay:getComputedStyle(e,'::after').animationDelay})));
 check(delays.find(d=>d.card.includes('best-shots')).delay,'-2.7s');
 await page.emulateMedia({reducedMotion:'reduce'});check((await effect()).duration,'0s');
 check(await page.locator('.update-badge--new').first().evaluate(e=>getComputedStyle(e,'::after').display),'none');
 check(issues,[]);await browser.close();server.close();
 const result={assertions,fixture,widths:[1280,768,390],max_title_delta_px:0,max_description_delta_px:0,metrics,sheen_samples:samples,placement_delays:delays,issues};
 fs.writeFileSync(path.join(root,'result.json'),JSON.stringify(result,null,2));console.log(`PASS: ${assertions} Chromium notice layout / pill / sheen assertions`);
})().catch(e=>{console.error(e);server.close();process.exit(1)});
