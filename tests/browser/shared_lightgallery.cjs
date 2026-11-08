'use strict';
// Real generated pages and vendor code; all origins intercepted, no production writes.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),vm=require('vm');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const root=path.resolve(process.argv[2]);
const fixture=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
const PH='https://exsudoporus-ruber.hatenablog.jp',CH='https://charchan123.github.io';
const starTest=fs.readFileSync(path.join(__dirname,'record_stars.cjs'),'utf8');
const mockSource=vm.runInNewContext(starTest.slice(starTest.indexOf('const icons='),starTest.indexOf('const server='))+'\nmockSource');
let browser,checks=0;const metrics=[],errors=[];
const check=(v,m)=>{assert.ok(v,m);checks++};
const svg=(w,h,label)=>`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="100%" height="100%" fill="#45634d"/><text x="20" y="100" fill="white" font-size="40">${label}</text><rect x="5" y="5" width="${w-10}" height="${h-10}" fill="none" stroke="orange" stroke-width="10"/></svg>`;
const mime=f=>({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.webp':'image/webp','.png':'image/png','.woff':'font/woff','.woff2':'font/woff2','.ttf':'font/ttf','.svg':'image/svg+xml'})[path.extname(f)]||'application/octet-stream';
(async()=>{
 browser=await chromium.launch({headless:true,ignoreDefaultArgs:['--hide-scrollbars'],executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
 async function setup(variant,width,height,touch=false,blockedVendor=false){
  const c=await browser.newContext({viewport:{width,height},hasTouch:touch,isMobile:touch}),requested=[];
  await c.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());check(req.method()==='GET','read only request');requested.push(u.pathname);
   if(u.origin===PH){
    const template=variant==='before'?'parent-before-template.html':'parent-template.html';
    let html=fs.readFileSync(path.join(root,template),'utf8').replace('CHILD_URL',CH+'/hatena-photo-gallery/'+(u.searchParams.get('child')||'best-shots-2025.html'));
    if(u.searchParams.get('host')==='body')html=html.replace('id="kinoko-home-portal"','id="galleryWrapper"')
     .replace('<!-- HOST_SCROLL_STYLE -->','<style>html{overflow:hidden}body{height:100vh;overflow-y:scroll}</style>');
    return route.fulfill({contentType:'text/html',body:html});
   }
   if(['/js/widget/star.js','/js/HatenaStar.js'].includes(u.pathname))return route.fulfill({contentType:'text/javascript',body:u.pathname.endsWith('/widget/star.js')?mockSource('fourteen'):''});
   if(u.pathname.endsWith('/mock-control'))return route.fulfill({contentType:'text/html',body:'<!doctype html><meta charset=utf-8><style>body{margin:0}button{width:32px;height:24px;padding:0}</style><button aria-label="isolated add">☆</button><script>document.querySelector("button").onclick=()=>parent.postMessage({type:"ISOLATED_ADD"},location.origin)</script>'});
   const vendor=path.join(root,'vendor',u.pathname.split('/').pop());
   if(['cdn.jsdelivr.net','unpkg.com'].includes(u.hostname)){
    if(!blockedVendor&&fs.existsSync(vendor))return route.fulfill({path:vendor,contentType:mime(vendor)});
    return route.abort();
   }
   if(req.resourceType()==='image'&&!u.pathname.endsWith('.webp')){
    const portrait=[...u.pathname].reduce((sum,c)=>sum+c.charCodeAt(0),0)%2===0;
    return route.fulfill({contentType:'image/svg+xml',body:svg(portrait?600:1200,portrait?900:600,portrait?'Portrait':'Landscape')});
   }
   if(u.origin===CH&&blockedVendor&&u.pathname.includes('/lightgallery/'))return route.abort();
   if(u.origin===CH){const file=path.resolve(root,variant,'.'+decodeURIComponent(u.pathname.replace('/hatena-photo-gallery','')));if(file.startsWith(path.join(root,variant)+path.sep)&&fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({path:file,contentType:mime(file)});}
   return route.abort();
  });
  await c.addInitScript(()=>{
   window.__openingPositions=[];window.__photoClickPositions=[];
   addEventListener('click',e=>{if(e.isTrusted&&e.target.closest?.('a.best-shot-photo'))window.__photoClickPositions.push(scrollY);},true);
   addEventListener('message',e=>{if(e.source===document.querySelector('#photoGallery')?.contentWindow&&e.origin==='https://charchan123.github.io'&&e.data?.type==='photoOpening')window.__openingPositions.push(scrollY||document.body.scrollTop);});
  });
  const p=await c.newPage();p.on('pageerror',e=>errors.push(e.message));return {c,p,requested};
 }
 const settle=f=>f.waitForFunction(()=>document.querySelector('[data-best-shot-gallery-ready],.gallery-item[data-lg-id]'));
 async function bounds(f){
  await f.waitForFunction(()=>{const e=document.querySelector('.lg-current img.lg-object');return e?.complete&&e.naturalWidth>0});await f.waitForTimeout(800);
  return f.locator('.lg-current img.lg-object').evaluate(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height,vw:innerWidth,vh:innerHeight,ratio:e.naturalWidth/e.naturalHeight}});
 }
 function fits(r){check(r.x>=-1&&r.right<=r.vw+1&&r.y>=-1&&r.bottom<=r.vh+1,'image within viewport '+JSON.stringify(r));check(Math.abs(r.width/r.height-r.ratio)<.02,'natural aspect ratio');}
 async function close(f,p,key=false){if(key)await p.keyboard.press('Escape');else await f.locator('.lg-close').click();await f.waitForSelector('.lg-show',{state:'detached'});await p.waitForTimeout(500);}
 async function scrollState(frame){
  return frame.evaluate(()=>{
   const root=document.documentElement,body=document.body,iframe=document.querySelector('#photoGallery');
   const rect=iframe?.getBoundingClientRect();
   return {rootOverflow:getComputedStyle(root).overflowY,bodyOverflow:getComputedStyle(body).overflowY,
    rootGutter:innerWidth-root.clientWidth,bodyGutter:body.offsetWidth-body.clientWidth,
    rootRange:root.scrollHeight-root.clientHeight,bodyRange:body.scrollHeight-body.clientHeight,
    y:scrollY,bodyY:body.scrollTop,frameX:rect?.left,frameWidth:rect?.width,
    overlay:iframe?.parentElement.matches(':popover-open')??false,
    overlayOverflow:iframe?getComputedStyle(iframe.parentElement).overflowY:null};
  });
 }
 async function toolbarGeometry(frame,expectedWidth,expectedGap){
  const geometry=await frame.locator('.lg-toolbar').evaluate(toolbar=>{
   const close=toolbar.querySelector('.lg-close').getBoundingClientRect();
   const zoom=toolbar.querySelector('.lg-zoom-in').getBoundingClientRect();
   const buttons=[...toolbar.querySelectorAll(':scope > button.lg-icon')].filter(button=>button.offsetWidth);
   return {edge:innerWidth-close.right,gap:close.left-zoom.right,
    centerDistance:(close.left+close.right-zoom.left-zoom.right)/2,
    widths:buttons.map(button=>button.offsetWidth),
    shareIconWidths:[...toolbar.querySelectorAll('.lg-dropdown .lg-icon')].map(icon=>icon.offsetWidth)};
  });
  check(Math.abs(geometry.edge-expectedGap)<=1,'close right gutter '+JSON.stringify(geometry));
  check(geometry.widths.length>=3&&geometry.widths.every(w=>Math.abs(w-expectedWidth)<=1),'primary button widths '+JSON.stringify(geometry));
  check(Math.abs(geometry.gap)<=1&&Math.abs(geometry.centerDistance-expectedWidth)<=1,'close and zoom spacing '+JSON.stringify(geometry));
  check(geometry.shareIconWidths.length>0&&geometry.shareIconWidths.every(w=>w===20),'nested share icon width preserved');
  return geometry;
 }
 if (!process.argv.includes('--interactions-only')) {
 for(const variant of ['before','after']){
  const {c,p}=await setup(variant,390,844,true);await p.goto(PH+'/?child=best-shots-2025.html');const f=p.frames().find(x=>x.url().startsWith(CH));await f.waitForSelector('a.best-shot-photo');await p.waitForTimeout(1000);
  const link=f.locator('a.best-shot-photo').last();await link.scrollIntoViewIfNeeded();await p.waitForTimeout(300);await link.click();
  if(variant==='before'){
   // Published gh-pages may already contain the accepted shared LightGallery.
   // Preserve the historical-dialog check only if that baseline actually uses it.
   await f.waitForFunction(()=>Boolean(document.querySelector('dialog[open], .lg-show')));
   if(await f.locator('dialog[open]').count()){
    await f.waitForFunction(()=>document.querySelector('dialog img')?.naturalWidth>0);
    const r=await f.locator('dialog img').evaluate(e=>({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,viewport:innerWidth,viewportHeight:innerHeight,maxHeight:getComputedStyle(e).maxHeight,dialogBorder:getComputedStyle(e.closest('dialog')).borderTopWidth}));
    check(r.maxHeight==='none'&&parseFloat(r.dialogBorder)>0,'historical unbounded native dialog baseline');metrics.push({case:'before-dialog',...r});
   }else{const r=await bounds(f);fits(r);metrics.push({case:'already-shared-published-baseline',...r});}
  }else{const r=await bounds(f);fits(r);check(await f.locator('.best-shot-dialog').count()===0,'no Best Shot-specific dialog');metrics.push({case:'after-gallery',...r});}
  await p.screenshot({path:path.join(root,'screenshots',`best-shot-${variant}-390.png`)});await c.close();
 }
 for(const [width,height,touch] of [[320,740,true],[360,800,true],[390,844,true],[430,900,true],[844,390,true],[960,900,false],[1280,900,false],[1440,900,false]]){
  const {c,p,requested}=await setup('after',width,height,touch);await p.goto(PH+'/?child=best-shots-2025.html');const f=p.frames().find(x=>x.url().startsWith(CH));await settle(f);await p.waitForTimeout(1000);
  const links=f.locator('a.best-shot-photo'),hrefs=await links.evaluateAll(es=>es.map(e=>e.href)),ids=await f.locator('.best-shot-card').evaluateAll(es=>es.map(e=>e.dataset.selectionId));
  const link=links.last();await link.scrollIntoViewIfNeeded();await p.waitForTimeout(300);const y=await p.evaluate(()=>scrollY);
  const before=await scrollState(p);
  await link.click();const r=await bounds(f),openingY=await p.evaluate(()=>window.__openingPositions.at(-1));check(Number.isFinite(openingY),'authenticated opening observed');fits(r);check(await f.locator('.lg-close').isVisible(),'close visible');check(await f.locator('.lg-thumb-item').count()===hrefs.length,'same photo count');check(await f.locator('.lg-current img.lg-object').getAttribute('src')===hrefs.at(-1),'selected photo matches');
  const host=await scrollState(p),child=await scrollState(f);
  check(host.overlay&&host.rootOverflow==='hidden'&&host.bodyOverflow==='hidden','open parent popover locks both scroll owners');
  check(host.rootGutter<=1&&child.rootGutter<=1&&host.overlayOverflow==='hidden','no host, iframe or wrapper scrollbar');
  if(!touch)metrics.push({case:'embedded-toolbar',width,toolbar:await toolbarGeometry(f,46,18),before,host,child});
  if([320,390,960,1280,1440].includes(width))await p.screenshot({path:path.join(root,'screenshots',`embedded-after-${width}.png`)});
  await close(f,p);metrics.push({case:'close-position',width,beforePointerAction:y,atOpening:openingY,after:await p.evaluate(()=>scrollY)});check(Math.abs(await p.evaluate(()=>scrollY)-openingY)<=1,'close restores parent '+JSON.stringify(metrics.at(-1)));
  const restored=await scrollState(p);
  check(restored.rootOverflow===before.rootOverflow&&restored.bodyOverflow===before.bodyOverflow&&restored.rootGutter===before.rootGutter&&!restored.overlay,'host scrollbar restored after close');
  check(restored.frameWidth===before.frameWidth&&restored.frameX===before.frameX,'embedded layout restored without horizontal jump');
  await link.click();await bounds(f);await p.keyboard.press('ArrowLeft');await p.waitForTimeout(700);check(await f.locator('.lg-current img.lg-object').getAttribute('src')===hrefs.at(-2),'previous photo');fits(await bounds(f));
  const escapeOpeningY=await p.evaluate(()=>window.__openingPositions.at(-1));await close(f,p,true);check(Math.abs(await p.evaluate(()=>scrollY)-escapeOpeningY)<=1,'Esc restores parent');
  check(JSON.stringify(await f.locator('.best-shot-card').evaluateAll(es=>es.map(e=>e.dataset.selectionId)))===JSON.stringify(ids),'selection/order unchanged');
  const stable=await p.evaluate(()=>({y:scrollY,h:document.documentElement.scrollHeight}));await p.waitForTimeout(800);check(JSON.stringify(await p.evaluate(()=>({y:scrollY,h:document.documentElement.scrollHeight})))===JSON.stringify(stable),'no delayed jump/blank');
  for(const file of ['lightgallery.min.js','lightgallery-bundle.min.css'])check(requested.filter(x=>x.endsWith('/'+file)).length===1,'single vendor load');
  metrics.push({case:'parent-close',width,height,touch,y,...r});await c.close();
 }
 for(const host of ['root','body']){
  for(const [variant,width] of [['before',1280],['after',1280],...(host==='body'?[['after',390],['after',320]]:[])]){
   const {c,p}=await setup(variant,width,844,width<500);
   await p.goto(PH+'/?host='+host);
   const f=p.frames().find(frame=>frame.url().startsWith(CH));
   await settle(f);
   const link=f.locator('a.best-shot-photo').last();
   await link.scrollIntoViewIfNeeded();
   const before=await scrollState(p);
   await link.click();fits(await bounds(f));
   const openingY=await p.evaluate(()=>window.__openingPositions.at(-1));
   const open=await scrollState(p),child=await scrollState(f);
   const owner=host==='body'?'body':'root';
   check(open.overlay&&open.overlayOverflow==='hidden'&&child.rootGutter<=1,'popover wrapper and iframe do not own the scrollbar');
   if(width===1280)check(before[owner+'Gutter']>=10,'classic '+host+' scrollbar reproduced before opening');
   if(variant==='before'){
    check(open[owner+'Gutter']>=10&&open[owner+'Overflow']==='scroll','published replay preserves scrollbar on '+host);
    if(host==='root')metrics.push({case:'published-toolbar',toolbar:await toolbarGeometry(f,50,0)});
   }else{
    check(open[owner+'Gutter']<=1&&open[owner+'Overflow']==='hidden','candidate hides scrollbar on '+host);
   }
   if(width===1280)await p.screenshot({path:path.join(root,'screenshots',`host-${host}-${variant}-1280.png`)});
   await close(f,p,host==='body');
   const after=await scrollState(p);
   check(Math.abs(after[host==='body'?'bodyY':'y']-openingY)<=1,'restore '+host+' scrollTop');
   check(after.frameX===before.frameX&&after.frameWidth===before.frameWidth&&after[owner+'Gutter']===before[owner+'Gutter']&&after[owner+'Overflow']===before[owner+'Overflow'],'restore '+host+' scrollbar and geometry');
   metrics.push({case:'scrollbar-owner',host,variant,width,before,openingY,open,child,after});
   if(host==='body'&&variant==='after'&&width===1280){
    await link.click();await bounds(f);
    await f.goto(CH+'/hatena-photo-gallery/best-shots.html');
    await p.waitForFunction(()=>!document.querySelector('#galleryWrapper').matches(':popover-open'));
    const navigated=await scrollState(p);
    check(navigated.bodyOverflow===before.bodyOverflow&&!navigated.overlay,'iframe navigation releases BODY scroll lock');
   }
   await c.close();
  }
 }
 {
  const {c,p}=await setup('after',900,900);await p.goto(PH+'/?child=new-top.html');await p.addStyleTag({content:'html{scrollbar-gutter:stable}::-webkit-scrollbar{width:15px}'});const f=p.frames().find(x=>x.url().startsWith(CH));
  for(const width of [900,899,915,914,900,899]){
   await p.setViewportSize({width,height:900});await f.waitForFunction(w=>document.documentElement.dataset.portalColumns===(w>=900?'2':'1'),width);
   const columns=await f.locator('.portal-shell').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length);check(columns===(width>=900?2:1),'parent column boundary');
   metrics.push({case:'boundary',parent:width,iframe:(await p.locator('#photoGallery').boundingBox()).width,columns});check(await f.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'portal no overflow');
  }await c.close();
 }
 for(const [variant,width] of [['before',1280],...([320,390,960,1280,1440].map(width=>['after',width]))]){
  const {c,p}=await setup(variant,width,844,width<500);await p.goto(CH+'/hatena-photo-gallery/best-shots.html');await settle(p);await p.getByRole('link',{name:'2025年',exact:true}).click();await settle(p);const url=p.url();
  const link=p.locator('a.best-shot-photo').last();await link.scrollIntoViewIfNeeded();await p.waitForTimeout(300);
  const before=await scrollState(p);
  await link.click();fits(await bounds(p));
  const open=await scrollState(p);
  check(await p.locator('.lg-close').isVisible(),'standalone close visible');
  if(variant==='before'){
   check(open.rootGutter>=10&&open.rootOverflow==='auto','standalone published HTML owns visible scrollbar');
  }else{
   check(open.rootGutter<=1&&open.rootOverflow==='hidden','standalone HTML scrollbar locked');
   if(width>=769)metrics.push({case:'standalone-toolbar',width,toolbar:await toolbarGeometry(p,46,18)});
  }
  await p.screenshot({path:path.join(root,'screenshots',`standalone-${variant}-${width}.png`)});
  await close(p,p);
  const after=await scrollState(p);
  const atClick=await p.evaluate(()=>window.__photoClickPositions.at(-1));
  metrics.push({case:'standalone-close',variant,width,before,open,atClick,after});
  check(after.rootGutter===before.rootGutter&&after.rootOverflow===before.rootOverflow,'standalone scrollbar restored');
  check(p.url()===url,'opening does not alter history');check(Number.isFinite(atClick),'trusted photo activation observed');check(Math.abs(await p.evaluate(()=>scrollY)-atClick)<=1,'standalone restores scroll '+JSON.stringify(metrics.at(-1)));await p.goBack();await settle(p);check(new URL(p.url()).pathname.endsWith('/best-shots.html'),'Back');await p.goForward();await settle(p);check(p.url()===url,'Forward');await c.close();
 }
 const names=fs.readdirSync(path.join(root,'after')).filter(x=>x.endsWith('.html'));
 const guide=names.find(name=>{
  const html=fs.readFileSync(path.join(root,'after',name),'utf8');
  return (html.match(/class="gallery-item"/g)||[]).length>=3&&html.includes('exif-bottom-row');
 });check(Boolean(guide),'real generated guide with EXIF and thumbnails');
 for(const width of [390,1280]){
  const {c,p}=await setup('after',width,844,width===390);
  await p.goto(CH+'/hatena-photo-gallery/'+encodeURIComponent(guide));await settle(p);
  const link=p.locator('a.gallery-item:not([data-favorite-eligible="false"])[data-sub-html*="exif-bottom-row"]').first();
  await link.click();fits(await bounds(p));
  check((await p.locator('.lg-sub-html .exif-bottom-row').first().innerText()).trim().length>0,'EXIF caption is painted');
  const favorite=p.locator('.lg-toolbar > .lg-fav-btn');
  await favorite.click();await p.waitForFunction(()=>document.querySelector('.lg-fav-btn')?.classList.contains('is-fav'));
  await favorite.click();await p.waitForFunction(()=>!document.querySelector('.lg-fav-btn')?.classList.contains('is-fav'));
  check(true,'favorite toggles on and off in isolated storage');
  await p.locator('.lg-toolbar > .lg-share').click();
  await p.waitForSelector('.lg-dropdown-active .lg-dropdown',{state:'visible'});
  await p.waitForFunction(()=>[...document.querySelectorAll('.lg-dropdown a')].every(link=>link.hasAttribute('href')));
  const destinations=await p.locator('.lg-dropdown a').evaluateAll(links=>links.map(link=>new URL(link.href).hostname));
  check(JSON.stringify(destinations)===JSON.stringify(['www.facebook.com','twitter.com','www.pinterest.com']),
   'share menu preserves its three destinations');
  await p.locator('.lg-dropdown-overlay').click();
  await p.waitForSelector('.lg-dropdown-active',{state:'detached'});
  // The responsive mosaic reorders DOM nodes independently of the vendor's slides.
  const thumbnails=p.locator('.lg-thumb-item');
  const selected=Number(await p.locator('.lg-thumb-item.active').getAttribute('data-lg-item-id'));
  const next=(selected+1)%await thumbnails.count();
  const thumbnail=thumbnails.nth(next).locator('img');
  const expectedPhoto=await thumbnail.getAttribute('src');
  check(expectedPhoto!==await p.locator('.lg-current img.lg-object').getAttribute('src'),'thumbnail is a different photo');
  if(width<500)await thumbnail.tap();else await thumbnail.click();
  await p.waitForFunction(src=>document.querySelector('.lg-current img.lg-object')?.getAttribute('src')===src,expectedPhoto);
  check(true,'clicking a thumbnail selects the correct photo');
  await close(p,p);await c.close();
 }
 for(const width of [320,360,390,430,1280]){
  const results=[];
  for(const variant of ['before','after']){
   const {c,p}=await setup(variant,width,844,width<500);await p.goto(CH+'/hatena-photo-gallery/new-top.html');await p.waitForFunction(()=>document.querySelector('.record-stars')?.dataset.total==='14');
   const r=await p.locator('.record-stars').first().evaluate(e=>{const s=e.querySelector('[data-hatena-star]').shadowRoot,items=[...s.querySelectorAll('a[data-record-star-profile]:not([data-record-star-hidden])')];return {group:e.getBoundingClientRect().width,native:e.querySelector('.record-stars-native').getBoundingClientRect().width,control:s.querySelector('[part~=star-button-container]').getBoundingClientRect().width,targets:items.map(a=>({w:a.getBoundingClientRect().width,h:a.getBoundingClientRect().height})),avatar:items[0]?.querySelector('picture img').getBoundingClientRect().width,total:e.dataset.total,ellipsis:!e.querySelector('.record-stars-ellipsis').hidden,overflow:document.documentElement.scrollWidth>innerWidth};});
   check(!r.overflow,'stars no overflow');check(r.total==='14'&&r.ellipsis,'count and ellipsis retained');if(width<500)check(r.targets.every(t=>t.w>=28&&t.h>=28),'28px touch targets');results.push(r);
   await p.screenshot({path:path.join(root,'screenshots',`stars-${variant}-${width}.png`)});
   if(variant==='after'&&width===390){await p.frameLocator('iframe').first().getByRole('button',{name:'isolated add'}).click();await p.waitForFunction(()=>document.querySelector('.record-stars')?.dataset.total==='15');check(true,'isolated native add control');}
   await c.close();
  }
  if(width<500&&!fixture.published_star_styles_match_candidate){check(results[1].control<results[0].control,'smaller add gap');check(results[1].avatar>results[0].avatar,'less internal whitespace');}else check(JSON.stringify(results[0])===JSON.stringify(results[1]),'accepted star layout unchanged');metrics.push({case:'stars',width,before:results[0],after:results[1]});
 }
 {
  const {c,p}=await setup('after',390,844,true,true);await p.goto(CH+'/hatena-photo-gallery/best-shots-2025.html');await p.waitForTimeout(500);
  check(await p.locator('a.best-shot-photo[href]').count()>0,'native links survive blocked CDN');check(await p.locator('dialog,.lg-outer').count()===0,'no broken overlay without dependencies');await c.close();
 }
 }
 // Additional touch/zoom/rotation coverage; may be run alone after the main suite.
 {
  const {c,p}=await setup('after',390,844,true);
  await p.goto(PH+'/?child=best-shots-2025.html');
  const f=p.frames().find(x=>x.url().startsWith(CH));await settle(f);
  await f.locator('a.best-shot-photo').last().click();fits(await bounds(f));
  const original=await f.locator('.lg-current img.lg-object').getAttribute('src');
  const session=await c.newCDPSession(p);
  // A real browser touch stream across the current image, not a fabricated slide event.
  const box=await f.locator('.lg-current img.lg-object').boundingBox();
  const x=box.x+box.width*.75,y=box.y+box.height*.5;
  await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});
  for(let i=1;i<=8;i++)await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-i*20,y}]});
  await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await f.waitForFunction(src=>document.querySelector('.lg-current img.lg-object')?.getAttribute('src')!==src,original);
  fits(await bounds(f));check(true,'browser touch swipe changes photograph');
  await f.locator('.lg-zoom-in').click();
  await f.waitForFunction(()=>document.querySelector('.lg-outer')?.classList.contains('lg-zoomed'));
  check(true,'user zoom enabled');await f.waitForTimeout(800);await f.locator('.lg-zoom-out').click();
  await f.waitForFunction(()=>!document.querySelector('.lg-outer')?.classList.contains('lg-zoomed'));await f.waitForTimeout(800);
  await p.setViewportSize({width:844,height:390});fits(await bounds(f));
  check((await scrollState(p)).rootOverflow==='hidden','rotation preserves parent scroll lock');
  await p.setViewportSize({width:768,height:844});fits(await bounds(f));
  check(await f.locator('.lg-close').evaluate(button=>getComputedStyle(button).width==='50px'),
   'desktop toolbar widths do not apply at the 768px mobile boundary');
  await p.setViewportSize({width:390,height:844});fits(await bounds(f));
  check(await f.locator('.lg-close').evaluate(button=>{
   const css=getComputedStyle(button);
   return css.opacity==='1'&&css.pointerEvents==='auto';
  }),'mobile close remains visible and clickable after rotation');
  await p.screenshot({path:path.join(root,'screenshots','best-shot-after-390.png')});
  await close(f,p);check(await p.locator('#photoGallery').evaluate(e=>e.getBoundingClientRect().height>844),'height restored after rotation');
  check((await scrollState(p)).rootOverflow==='scroll','rotation close releases scroll lock');
  await c.close();
 }
 for(const variant of ['before','after']){
  const {c,p}=await setup(variant,390,844,true);await p.goto(CH+'/hatena-photo-gallery/new-top.html');
  await p.waitForFunction(()=>document.querySelector('.record-stars')?.dataset.total==='14');
  await p.screenshot({path:path.join(root,'screenshots',`stars-${variant}-390.png`)});await c.close();
 }
 check(errors.length===0,'no browser exceptions: '+errors.join(';'));await browser.close();fs.writeFileSync(path.join(root,process.argv.includes('--interactions-only')?'interactions-result.json':'result.json'),JSON.stringify({checks,metrics,errors,physicalAndroid:false,photoTransport:'synthetic SVG; original URLs and ordering retained'},null,2));console.log('PASS',checks,'isolated browser assertions');
})().catch(async e=>{console.error(e);fs.writeFileSync(path.join(root,'failure.json'),JSON.stringify({checks,metrics,errors,error:String(e)},null,2));if(browser)await browser.close();process.exitCode=1});
