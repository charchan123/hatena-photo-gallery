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
   const title=scope.querySelector('strong').getBoundingClientRect(),description=scope.querySelector('small').getBoundingClientRect(),label=scope.querySelector('.portal-eyebrow')?.getBoundingClientRect();
   const rect=card.getBoundingClientRect();result[name]={labelY:label?.y??null,titleY:title.y,descriptionY:description.y,cardHeight:rect.height,cardWidth:rect.width};
  }return result;
 })}
 async function geometry(){return page.locator('.portal-independent-links .portal-card').evaluateAll(cards=>cards.map(card=>{
  const content=card.querySelector('.portal-card__content'),copy=card.querySelector('.portal-card__copy'),visual=card.querySelector('.portal-card__visual'),label=card.querySelector('.portal-eyebrow'),title=card.querySelector('strong'),desc=card.querySelector('small'),details=card.querySelector('.portal-card__details'),note=card.querySelector('.portal-update-note');
  const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}},c=rect(card),l=rect(label),d=rect(desc),cs=getComputedStyle(content),ds=getComputedStyle(desc),ts=getComputedStyle(title),vs=getComputedStyle(visual);
  return {name:card.classList.contains('portal-card--research')?'research':'best-shots',card:c,label:l,title:rect(title),description:d,content:rect(content),details:rect(details),notice:note&&!note.hidden?rect(note):null,badge:note&&!note.hidden?rect(note.querySelector('.update-badge')):null,noticePosition:note?getComputedStyle(note).position:null,copyPosition:getComputedStyle(copy).position,paddingBottom:parseFloat(cs.paddingBottom),bottomBorder:parseFloat(getComputedStyle(card).borderBottomWidth),detailsReservation:rect(details).height-d.height,belowDescription:c.bottom-d.bottom,signature:{href:card.getAttribute('href'),background:vs.backgroundImage.replace(/url\("[^"]*\/assets\//g,'url("assets/'),backgroundPosition:vs.backgroundPosition,filter:vs.filter,shade:cs.backgroundImage,titleFont:ts.font,titleLineHeight:ts.lineHeight,descriptionFont:ds.font,descriptionLineHeight:ds.lineHeight}};
 }))}
 const effect=()=>page.locator('.update-badge--new').first().evaluate(el=>{
  const c=getComputedStyle(el,'::after');return {duration:c.animationDuration,delay:c.animationDelay,timing:c.animationTimingFunction,opacity:c.opacity,transform:c.transform,width:c.width,background:c.backgroundImage,overflow:getComputedStyle(el).overflow,borderRadius:getComputedStyle(el).borderRadius};
 });
 const comparisons=[];
 for(const width of [1280,768,390,320]){
  await page.setViewportSize({width,height:1000});let baseline;
  const comparison={width};
  for(const state of ['off','both','long']){
   await page.goto(base+'/before/'+state+'/new-top.html');await page.evaluate(()=>document.fonts.ready);
   if(state==='off')comparison.before=await geometry();
   await page.locator('.portal-independent-links').screenshot({path:path.join(shots,`${width}-before-${state}-cards.png`),animations:'disabled'});
  }
  await page.goto(base+'/published/off/new-top.html');comparison.published=await geometry();
  for(const state of fixture.states){
   await page.goto(base+'/'+state+'/new-top.html');await page.evaluate(()=>document.fonts.ready);
   const found=await positions(),boxes=await geometry();console.log('Layout',width,state,JSON.stringify(found));if(state==='off'){baseline=found;comparison.after=boxes;}
   for(const name of Object.keys(found)){
    for(const field of ['labelY','titleY','descriptionY','cardHeight','cardWidth'])check(found[name][field],baseline[name][field]);
   }
   for(let i=0;i<boxes.length;i++){
    const box=boxes[i],old=comparison.before[i];
    check(Math.abs(box.card.height-old.card.height)<=.02,true);check(box.card.width,old.card.width);
    check(Math.abs(box.content.height-old.content.height)<=.02,true);
    // Only these two intentional artwork replacements may differ from the
    // historical notice baseline; every layout, typography and effect field stays exact.
    const expectedSignature={...old.signature,background:old.signature.background
     .replace('assets/research-lab-cabin.webp','assets/ai-research-lab-20261031.webp')
     .replace('assets/new-top-best-shots-camera-mushrooms.webp','assets/ai-best-shots-20261031.webp')};
    check(box.signature,expectedSignature);
    check(Math.abs(box.detailsReservation)<.02,true);
    check(Math.abs(box.belowDescription-box.paddingBottom-box.bottomBorder)<.02,true);
    if(box.notice){
     check(box.noticePosition,'absolute');check(box.copyPosition,'relative');
     check(box.notice.bottom<=box.label.y-5.99,true);check(box.notice.y>=box.card.y,true);
     check(box.notice.x>=box.card.x&&box.notice.right<=box.card.right,true);
     check(box.badge.x>=box.card.x&&box.badge.right<=box.card.right&&box.badge.y>=box.card.y&&box.badge.bottom<=box.card.bottom,true);
    }
   }
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   check(await page.locator('.portal-update-note:not([hidden])').count(),fixture.notice_counts[state]);
   for(const badge of await page.locator('.portal-update-note:not([hidden]) .update-badge').all()){
    const style=await badge.evaluate(e=>({height:e.getBoundingClientRect().height,weight:getComputedStyle(e).fontWeight,transform:getComputedStyle(e).transform}));
    check(style.height,22);check(style.weight,'700');check(style.transform,'none');
   }
   if(state==='long'){const summaries=await page.locator('.portal-update-summary').evaluateAll(es=>es.map(e=>({overflow:getComputedStyle(e).textOverflow,scroll:e.scrollWidth,client:e.clientWidth})));check(summaries.every(e=>e.overflow==='ellipsis'&&e.scroll>e.client),true);}
   if(state==='new'){
    const recordBadges=page.locator('.record-preview-heading .update-badge--new:not([hidden])');check(await page.locator('.record-preview-heading').count()>0,true);
    for(const badge of await recordBadges.all())check(await badge.evaluate(e=>e.getBoundingClientRect().height),22);
    await page.locator('.portal-records-hero').screenshot({path:path.join(shots,`${width}-records-new.png`),animations:'disabled'});
   }
   if(['off','both','long','expired'].includes(state)){
    await page.locator('.portal-independent-links').screenshot({path:path.join(shots,`${width}-after-${state}-cards.png`),animations:'disabled'});
    await page.locator('.portal-guide-list').screenshot({path:path.join(shots,`${width}-${state}-guide.png`),animations:'disabled'});
   }
   metrics.push({width,state,positions:found,geometry:boxes});
  }
  comparisons.push(comparison);
  // Expiry and BFCache-style restoration exercise the unchanged production refresh script.
  await page.goto(base+'/new/new-top.html');const visible=await positions();
  await page.evaluate(()=>{document.querySelectorAll('.portal-update-note').forEach(e=>e.dataset.noticeEnd=String(Date.now()-1));window.dispatchEvent(new Event('pageshow'))});
  check(await page.locator('.portal-update-note:not([hidden])').count(),0);check(await positions(),visible);
  await page.locator('.portal-independent-links').screenshot({path:path.join(shots,`${width}-after-live-expiry-cards.png`),animations:'disabled'});
 }
 // Freeze the same real CSS animation at multiple points in its 5.4-second cycle.
 const samples={};
 for(const variant of ['before','after']){
  await page.goto(base+'/badges.html');await page.locator('#badge-css').evaluate((e,v)=>e.href=v+'.css',variant);
  await page.waitForFunction(v=>document.querySelector('#badge-css').sheet&&document.querySelector('#badge-css').sheet.href.endsWith(v+'.css'),variant);
  await page.locator('#label').evaluate((e,v)=>e.textContent=v==='before'?'Before · previous Draft':'After · Draft PR #123',variant);
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
 const result={assertions,fixture,widths:[1280,768,390,320],max_label_delta_px:0,max_title_delta_px:0,max_description_delta_px:0,metrics,comparisons,sheen_samples:samples,placement_delays:delays,issues};
 fs.writeFileSync(path.join(root,'result.json'),JSON.stringify(result,null,2));console.log(`PASS: ${assertions} Chromium notice layout / pill / sheen assertions`);
})().catch(e=>{console.error(e);server.close();process.exit(1)});
