'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const root=path.resolve(process.argv[2]),CH='https://charchan123.github.io';
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../../audit/ai-image-refresh-20261031/artwork-manifest.json')));
const old=new Set(Object.keys(manifest.replacements)),fresh=new Map(manifest.assets.map(a=>[a.asset,a]));
const star=fs.readFileSync(path.join(__dirname,'record_stars.cjs'),'utf8');
const mock=vm.runInNewContext(star.slice(star.indexOf('const icons='),star.indexOf('const server='))+'\nmockSource');
let browser,checks=0;const rows=[],errors=[],missing=[];const check=(v,m)=>{assert.ok(v,m);checks++};
const svg='<svg xmlns="http://www.w3.org/2000/svg" width="900" height="600"><rect width="100%" height="100%" fill="#bbcbb5"/></svg>';
(async()=>{
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
 const pages=['new-top.html','index.html','records.html','season.html','features.html','research.html','best-shots.html','best-shots-2025.html','favorite.html','あ行.html','アイタケ.html'];
 for(const [width,height] of [[320,844],[360,844],[390,844],[430,844],[899,900],[900,900],[1280,900],[844,390]]){
  for(const file of pages){
   const measurements=[];
   for(const variant of ['before','after']){
    const c=await browser.newContext({viewport:{width,height},hasTouch:width<500,isMobile:width<500});
    await c.route('**/*',async route=>{
     const req=route.request(),u=new URL(req.url());check(req.method()==='GET','read only requests');
     if(['/js/widget/star.js','/js/HatenaStar.js'].includes(u.pathname))return route.fulfill({contentType:'text/javascript',body:u.pathname.endsWith('/widget/star.js')?mock('fourteen'):''});
     if(u.pathname==='/mock-control')return route.fulfill({contentType:'text/html',body:'<!doctype html><style>body{margin:0}button{width:32px;height:24px;padding:0}</style><button>☆</button>'});
     if(u.origin===CH&&u.pathname.startsWith('/hatena-photo-gallery/')){
      const f=path.resolve(root,variant,'.'+decodeURIComponent(u.pathname.replace('/hatena-photo-gallery','')));
      if(f.startsWith(path.join(root,variant)+path.sep)&&fs.existsSync(f)&&fs.statSync(f).isFile())return route.fulfill({path:f,contentType:({'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json','.webp':'image/webp','.png':'image/png','.woff2':'font/woff2','.woff':'font/woff'})[path.extname(f)]||'application/octet-stream'});
      missing.push({file,variant,path:u.pathname});return route.fulfill({status:404,body:'missing local file'});
     }
     const vendor=path.join(root,'vendor',u.pathname.split('/').pop());
     if(['cdn.jsdelivr.net','unpkg.com'].includes(u.hostname)&&fs.existsSync(vendor))return route.fulfill({path:vendor,contentType:u.pathname.endsWith('.css')?'text/css':u.pathname.endsWith('.js')?'text/javascript':'font/woff2'});
     if(req.resourceType()==='image')return route.fulfill({contentType:'image/svg+xml',body:svg});
     return route.abort();
    });
    const p=await c.newPage();p.on('pageerror',e=>errors.push({file,variant,message:e.message}));
    await p.goto(CH+'/hatena-photo-gallery/'+encodeURIComponent(file),{waitUntil:'load'});await p.waitForTimeout(200);
    await p.evaluate(()=>document.fonts.ready);
    const result=await p.evaluate(()=>{
     const selectors='.portal-records-visual,.portal-section-visual,.portal-card__visual,.guide-hero,.guide-way,.records-hero,.season-hero,.feature-hero,.research-hero,.best-shots-hero,.favorite-hero,.aiuo-hero,.detail-hero';
     const elements=[...document.querySelectorAll(selectors)];
     const geometry=elements.map(e=>{const r=e.getBoundingClientRect();return {class:e.className,x:r.x,y:r.y,w:r.width,h:r.height}});
     const backgrounds=elements.flatMap(e=>['','::before','::after'].flatMap(pseudo=>[...getComputedStyle(e,pseudo||null).backgroundImage.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map(m=>m[1])));
     return {geometry,backgrounds:[...new Set(backgrounds)],overflow:document.documentElement.scrollWidth>innerWidth+1};
    });
    check(!result.overflow,`${variant} ${file} ${width} overflow`);
    for(const url of result.backgrounds){
     const name=new URL(url).pathname.split('/').pop();
     if(variant==='after')check(!old.has(name),'no old background painted');
     if(variant==='after'&&fresh.has(name)){
      const actual=await p.evaluate(async url=>{const i=new Image();i.src=url;await i.decode();return [i.naturalWidth,i.naturalHeight]},url);
      const wanted=fresh.get(name);check(actual[0]===wanted.width&&actual[1]===wanted.height,'actual WebP decodes at original resolution');
     }
    }
    if(variant==='after'&&file==='new-top.html')check(new Set(result.backgrounds.map(u=>new URL(u).pathname.split('/').pop()).filter(n=>fresh.has(n))).size===7,'all seven portal artworks painted');
    measurements.push(result);
    if([390,1280].includes(width))await p.screenshot({path:path.join(root,'screenshots',`${variant}-${width}-${file.replace('.html','')}.png`),fullPage:file!=='records.html'});
    await c.close();
   }
   check(JSON.stringify(measurements[0].geometry)===JSON.stringify(measurements[1].geometry),`${file} ${width}: layout dimensions unchanged`);
   rows.push({file,width,height,before:measurements[0],after:measurements[1]});
  }
 }
 check(missing.length===0,'no internal image/resource 404: '+JSON.stringify(missing));
 check(errors.length===0,'no JS regressions: '+JSON.stringify(errors));await browser.close();
 fs.writeFileSync(path.join(root,'browser-result.json'),JSON.stringify({checks,rows,errors,missing,physicalAndroid:false,photoTransport:'SVG substitutes for unchanged photographs; AI WebP bytes are real'},null,2));console.log('PASS',checks,'artwork/reference/layout checks');
})().catch(async e=>{console.error(e);fs.writeFileSync(path.join(root,'browser-failure.json'),JSON.stringify({checks,rows,errors,missing,error:String(e)},null,2));await browser?.close();process.exitCode=1});
