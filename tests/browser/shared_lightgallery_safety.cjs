'use strict';
// Adversarial read-only transport. The production parent handler is changed ONLY
// inside this fixture to delay/drop/reject its messages. No production writes.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const root=path.resolve(process.argv[2]),probe=process.argv.includes('--probe');
const PH='https://exsudoporus-ruber.hatenablog.jp',CH='https://charchan123.github.io';
const report={cases:[],errors:[],physicalAndroid:false,transport:'isolated SVG / fault-injected messages; no real star writes'};
let browser,checks=0;const check=(v,m)=>{assert.ok(v,m);checks++};
const picture='<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900"><rect width="100%" height="100%" fill="green"/></svg>';
(async()=>{
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
 async function setup(width,fault={}){
  const context=await browser.newContext({viewport:{width,height:844},hasTouch:width<500,isMobile:width<500});
  const externalScripts=[];let releaseImages,releaseScripts;const images=new Promise(r=>releaseImages=r),scripts=new Promise(r=>releaseScripts=r),held=[];
  await context.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());check(req.method()==='GET','GET only');
   if(u.origin===PH){
    let html=fs.readFileSync(path.join(root,'parent-template.html'),'utf8');
    html=html.replaceAll('CHILD_URL',CH+'/hatena-photo-gallery/best-shots-2025.html');
    html=html.replaceAll('iframe.contentWindow?.postMessage(', 'sendToChild(').replaceAll('iframe.contentWindow.postMessage(', 'sendToChild(');
    html=html.replace('  const iframe =',`  const fault=${JSON.stringify(fault)};
  function sendToChild(data,target){
   if(data.type==='requestHeight'){
    if(fault.noHost)return;
    if(fault.legacy)delete data.photoOpeningProtocol;
    if(fault.hostDelay){setTimeout(()=>iframe.contentWindow.postMessage(data,target),fault.hostDelay);return;}
   }
   if(data.type==='photoOpeningAck'&&fault.ackTimeout)return;
   iframe.contentWindow.postMessage(data,target);
  }
  const iframe =`);
    if(fault.ackReject)html=html.replace("} else if (data.type === 'photoOpening') {", "} else if (data.type === 'photoOpening') { sendToChild({type:'photoOpeningAck',id:data.id,ok:false},galleryOrigin); return;");
    return route.fulfill({contentType:'text/html',body:html});
   }
   const isScript=req.resourceType()==='script',isStyle=req.resourceType()==='stylesheet';
   if(isScript&&u.origin!==CH){externalScripts.push(u.href);if(fault.cdnDelay)await new Promise(r=>setTimeout(r,fault.cdnDelay));}
   if(isScript&&(fault.holdScripts||fault.slowScripts)){held.push(u.href);if(fault.holdScripts)await scripts;else await new Promise(r=>setTimeout(r,fault.slowScripts));}
   if(isScript&&fault.missingJS&&u.pathname.endsWith(fault.missingJS))return route.abort();
   if(isStyle&&fault.missingCSS&&u.pathname.endsWith('lightgallery-bundle.min.css'))return route.abort();
   if(req.resourceType()==='image'||(![PH,CH].includes(u.origin)&&!isScript&&!isStyle&&!u.pathname.endsWith('.woff2'))){
    if(u.pathname.includes('held-photo')){held.push(u.href);if(fault.imageFail)return route.abort();if(fault.holdImages)await images;}
    return route.fulfill({contentType:'image/svg+xml',body:picture});
   }
   let file;
   if(u.origin===CH)file=path.resolve(root,'after','.'+decodeURIComponent(u.pathname.replace('/hatena-photo-gallery','')));
   else file=path.join(root,'vendor',u.pathname.split('/').pop());
   if(!file.startsWith(root+path.sep)||!fs.existsSync(file))return route.abort();
   if(file.endsWith('.html')){
    let html=fs.readFileSync(file,'utf8');
    if(fault.many)html=html.replace('</main>',Array.from({length:180},(_,i)=>`<article class="best-shot-card" style="min-height:500px"><a class="best-shot-photo" href="https://images.test/held-photo-${i}.jpg" data-sub-html="fixture ${i}"><img loading="lazy" width="600" height="900" src="https://images.test/held-photo-${i}.jpg" alt="fixture ${i}"></a></article>`).join('')+'</main>');
    return route.fulfill({contentType:'text/html',body:html});
   }
   const mime={'.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.json':'application/json','.webp':'image/webp','.png':'image/png'}[path.extname(file)];
   return route.fulfill({path:file,contentType:mime||'application/octet-stream'});
  });
  await context.addInitScript(()=>{window.__openYs=[];window.__openIds=[];addEventListener('message',e=>{if(e.source===document.querySelector('#photoGallery')?.contentWindow&&e.origin==='https://charchan123.github.io'&&e.data?.type==='photoOpening'){window.__openYs.push(scrollY);window.__openIds.push(e.data.id);}});});
  const p=await context.newPage();p.on('pageerror',e=>report.errors.push(e.message));
  return {p,context,held,externalScripts,finish:async()=>{releaseImages();releaseScripts();await context.close();}};
 }
 const child=async p=>{await p.frameLocator('#photoGallery').locator('.best-shot-photo').first().waitFor({state:'attached'});return p.frames().find(f=>f.url().startsWith(CH));};
 const initialized=f=>f.waitForFunction(()=>document.querySelector('[data-best-shot-gallery-ready]'),{},{timeout:3000});
 async function open(f,index=0){await f.locator('.best-shot-photo').nth(index).click();await f.waitForSelector('.lg-show',{state:'attached',timeout:3000});}
 async function close(f,p,esc=false){if(esc)await p.keyboard.press('Escape');else await f.locator('.lg-close').click();await f.waitForSelector('.lg-show',{state:'detached'});await p.waitForTimeout(500);}
 if(probe){
  for(const kind of ['image-wait','pre-host','cdn-wait']){
   const s=await setup(390,kind==='image-wait'?{many:true,holdImages:true}:kind==='pre-host'?{noHost:true}:{holdScripts:true});
   await s.p.goto(kind==='cdn-wait'?CH+'/hatena-photo-gallery/best-shots-2025.html':PH+'/',{waitUntil:'commit'});await s.p.waitForTimeout(1000);
   const f=kind==='cdn-wait'?s.p:await child(s.p);
   const observed=await f.evaluate(()=>({cards:document.querySelectorAll('.best-shot-photo').length,initialized:!!document.querySelector('.best-shot-photo[data-lg-id]'),readyState:document.readyState}));
   if(kind==='pre-host'){await open(f);observed.openWithoutAuthenticatedRequest=(await s.p.evaluate(()=>window.__openYs.length))===0;}
   report.cases.push({kind,...observed});await s.finish();
  }
 }else{
  if(!process.argv.includes('--timing-only')){
  for(const width of [320,360,390,430,1280]){
   for(const failed of [false,true]){
    const s=await setup(width,{many:true,holdImages:!failed,imageFail:failed});await s.p.goto(CH+'/hatena-photo-gallery/best-shots-2025.html',{waitUntil:'domcontentloaded'});await initialized(s.p);
    check(await s.p.locator('.best-shot-photo').count()>180,'large gallery fixture');
    const preOpenRequests=s.held.length;check(preOpenRequests<180,'initialization does not force all lazy image requests');
    await open(s.p);await s.p.waitForFunction(()=>document.querySelector('.lg-current img')?.naturalWidth>0);await close(s.p,s.p);
    check(await s.p.locator('.best-shot-photo img[loading=lazy]').count()>180,'lazy attributes retained');
    report.cases.push({case:'uncompleted-or-failed-images',width,failed,preOpenRequests,heldRequests:s.held.length});await s.finish();
   }
  }
  for(const width of [390,1280]){
   for(const mode of ['noHost','hostDelay','legacy','ackReject','ackTimeout']){
    const fault={};fault[mode]=mode==='hostDelay'?4000:true;
    const s=await setup(width,fault);await s.p.goto(PH+'/',{waitUntil:'domcontentloaded'});const f=await child(s.p);await initialized(f);
    if(['noHost','hostDelay','legacy'].includes(mode)){
     const href=await f.locator('.best-shot-photo').first().getAttribute('href');
     await f.locator('.best-shot-photo').first().click();await s.p.waitForURL(href);
     check(new URL(s.p.url()).origin!==PH,'unprepared host keeps native photograph link');
    }else{
     await f.locator('.best-shot-photo').first().evaluate(a=>{a.click();a.click();});
     if(mode==='ackTimeout'){
      await s.p.waitForTimeout(80);const id=await s.p.evaluate(()=>window.__openIds[0]);
      await s.p.evaluate(target=>document.querySelector('iframe').contentWindow.postMessage({type:'photoOpeningAck',id:'stale',ok:true},target),CH);
      await f.evaluate(id=>window.postMessage({type:'photoOpeningAck',id,ok:true},location.origin),id);
      await s.p.waitForTimeout(80);check(await f.locator('.lg-show').count()===0,'wrong-source and stale ACK cannot open Best Shot');
     }
     await s.p.waitForTimeout(mode==='ackTimeout'?2200:200);
     check(await f.locator('.lg-show').count()===0,'failed ACK cannot open gallery');
     check((await s.p.evaluate(()=>window.__openYs.length))===1,'no duplicate pending request');
     const href=await f.locator('.best-shot-photo').first().getAttribute('href');await f.locator('.best-shot-photo').first().click();await s.p.waitForURL(href);
     check(new URL(s.p.url()).origin!==PH,'retry is native fallback');
    }
    report.cases.push({case:'parent-fallback',width,mode});await s.finish();
   }
   const s=await setup(width);await s.p.goto(PH+'/');const f=await child(s.p);await initialized(f);
   for(const esc of [false,true]){
    await open(f,5);const y=await s.p.evaluate(()=>window.__openYs.at(-1));check(Number.isFinite(y),'authenticated position saved');await s.p.keyboard.press('ArrowRight');await s.p.waitForTimeout(600);await close(f,s.p,esc);
    check(Math.abs(await s.p.evaluate(()=>scrollY)-y)<=1,'ACK close restores exact parent position');
   }
   report.cases.push({case:'normal-ACK-both-close-paths',width});await s.finish();
   for(const fault of [{missingCSS:true},{missingJS:'lg-zoom.min.js'},{missingJS:'lightgallery.min.js'}]){
    const s=await setup(width,fault);await s.p.goto(CH+'/hatena-photo-gallery/best-shots-2025.html');
    check(await s.p.locator('[data-best-shot-gallery-ready]').count()===0,'incomplete dependencies do not arm interception');
    const href=await s.p.locator('.best-shot-photo').first().getAttribute('href');await s.p.locator('.best-shot-photo').first().click();await s.p.waitForURL(href);check(true,'dependency failure preserves native link');
    report.cases.push({case:'dependency-fallback',width,...fault});await s.finish();
   }
   const s2=await setup(width,{holdScripts:true});await s2.p.goto(CH+'/hatena-photo-gallery/best-shots-2025.html',{waitUntil:'commit'});
   await s2.p.waitForSelector('.best-shot-photo',{timeout:2500});check(await s2.p.locator('.best-shot-photo').first().isVisible(),'deferred scripts do not block visible cards');
   const href=await s2.p.locator('.best-shot-photo').first().getAttribute('href');await s2.p.locator('.best-shot-photo').first().click();await s2.p.waitForURL(href);check(true,'uncompleted scripts retain native link');report.cases.push({case:'uncompleted-scripts',width});await s2.finish();
  }
  }
  for(const width of [390,1280]){
   const s=await setup(width,{hostDelay:600,slowScripts:120,cdnDelay:5000});
   await s.p.goto(PH+'/',{waitUntil:'domcontentloaded'});const f=await child(s.p);await initialized(f);
   await s.p.waitForTimeout(850);await open(f,5);await f.waitForFunction(()=>document.querySelector('.lg-current img')?.naturalWidth>0);
   const y=await s.p.evaluate(()=>window.__openYs.at(-1));await close(f,s.p);
   check(Math.abs(await s.p.evaluate(()=>scrollY)-y)<=1,'delayed handshake and script order restore exact position');
   check(s.externalScripts.length===0,'Best Shot has no external CDN scripts to delay');
   report.cases.push({case:'delayed-host-and-slow-script-order',width,externalScripts:s.externalScripts});await s.finish();
  }
  check(report.errors.length===0,'no browser errors: '+report.errors.join(';'));
 }
 await browser.close();report.checks=checks;fs.writeFileSync(path.join(root,probe?'safety-before.json':process.argv.includes('--timing-only')?'safety-timing.json':'safety-result.json'),JSON.stringify(report,null,2));console.log(probe?report.cases:'PASS '+checks+' safety assertions');
})().catch(async e=>{console.error(e);report.failure=String(e);report.checks=checks;fs.writeFileSync(path.join(root,'safety-failure.json'),JSON.stringify(report,null,2));await browser?.close();process.exitCode=1});
