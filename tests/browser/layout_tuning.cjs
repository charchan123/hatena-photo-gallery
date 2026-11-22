'use strict';
// Production photographs and selections; external writes are blocked.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(process.argv[2]),fixture=JSON.parse(fs.readFileSync(path.join(root,'fixture.json')));
const out=path.resolve(process.argv[3]||path.join(root,'results'));fs.mkdirSync(out,{recursive:true});
const {standalonePortalCSS}=require('./standalone_portal_css.cjs');
const layoutCSS=s=>standalonePortalCSS(s).replace(/url\([^)]*\)/g,'url(artwork)');
const beforePortalCSS=fs.readFileSync(path.join(root,'before/assets/portal.css'),'utf8');
const afterPortalCSS=fs.readFileSync(path.join(root,'after/assets/portal.css'),'utf8');
const standaloneUnchanged=layoutCSS(beforePortalCSS)===layoutCSS(afterPortalCSS);
// The approved 2026-11-23 follow-up changes copy layout, not thumbnails.
// Pin the complete CSS delta so unrelated layout changes cannot be excused.
const approvedCSSChanges=[
 ['.portal-guide-note__details { display:grid; grid-template-columns:minmax(0,1fr); grid-template-rows:calc(2 * .88rem * 1.45) 24px; min-width:0; gap:3px; }',
  '.portal-guide-note__details { display:grid; grid-template-columns:minmax(0,1fr); grid-template-rows:calc(2 * .88rem * 1.45) 22px; min-width:0; gap:2px; }'],
 ['.portal-index .portal-guide-note { position:relative; top:0; }',
  "/* Keep the heading and description's first line at their pre-PR166 positions.\n   The two-line copy and 22px notice row increase the details height from 46px.\n   Offset the right note by half that growth plus its original top adjustment.\n   The stacked-mobile rule below remains top:0, matching its original anchor. */\n.portal-index .portal-guide-note { position:relative; top:calc(.638rem + 12px); }"],
 ["  :root:not([data-portal-columns=\"2\"]) .portal-index .portal-guide-row .portal-card { height:108px; min-height:108px; }\n}",
  "  :root:not([data-portal-columns=\"2\"]) .portal-index .portal-guide-row .portal-card { height:108px; min-height:108px; }\n  /* Only a visible update badge needs extra clearance at this compact width. */\n  :root:not([data-portal-columns=\"2\"]) .portal-index .portal-guide-row:has(.portal-update-note:not([hidden])) { padding-bottom:14px; }\n}"],
];
let expectedCopyOnly=beforePortalCSS,copyOnly=true;
for(const [from,to] of approvedCSSChanges){
 if(expectedCopyOnly.split(from).length!==2){copyOnly=false;break;}
 expectedCopyOnly=expectedCopyOnly.replace(from,to);
}
const approvedCopyOnly=copyOnly&&expectedCopyOnly===afterPortalCSS;
if(standaloneUnchanged||approvedCopyOnly)process.env.LAYOUT_EXPECT_UNCHANGED='1';
console.log(JSON.stringify({standalonePortalCSSUnchanged:standaloneUnchanged,expectUnchanged:process.env.LAYOUT_EXPECT_UNCHANGED}));
const server=http.createServer((req,res)=>{const f=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile()){res.writeHead(404);return res.end();}res.setHeader('Content-Type',({'.html':'text/html','.css':'text/css','.js':'text/javascript','.webp':'image/webp','.png':'image/png'})[path.extname(f)]||'application/octet-stream');res.end(fs.readFileSync(f));});
let browser,assertions=0;const check=(v,message)=>{assert.ok(v,message);assertions++};
(async()=>{await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-gpu']});
const context=await browser.newContext(),page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const externalCache=new Map();
await context.route('**/*',async route=>{const r=route.request(),u=new URL(r.url());if(r.method()!=='GET'||/(?:star\.add|star\.delete|\/stars?\/(?:add|delete|remove))/.test(u.pathname))return route.abort();if(u.hostname==='127.0.0.1')return route.continue();const photo=fixture.photos[u.href];if(photo)return route.fulfill({body:fs.readFileSync(path.join(root,photo.file)),contentType:'image/jpeg'});if(process.env.LAYOUT_LIVE_STARS&&['s.hatena.ne.jp','cdn.profile-image.st-hatena.com'].includes(u.hostname)){if(!externalCache.has(u.href))externalCache.set(u.href,(async()=>{const res=await route.fetch({timeout:30000});return {body:await res.body(),status:res.status(),contentType:res.headers()['content-type']||'application/octet-stream'};})());return route.fulfill(await externalCache.get(u.href));}return route.abort();});
const measurements=[];
for(const width of [1280,1024,900,899,768,680,390,320]){
 await page.setViewportSize({width,height:1000});
 for(const variant of ['before','after']){
  await page.goto(`${base}/${variant}/new-top.html`);await page.evaluate(()=>document.fonts.ready);
  if(process.env.LAYOUT_LIVE_STARS){await page.waitForFunction(()=>[...document.querySelectorAll('.record-stars-native')].every(e=>e.hasAttribute('data-ready')),null,{timeout:30000});check(await page.locator('.record-stars-native iframe').count()===3,'three official add frames');await page.waitForFunction(()=>[...document.querySelectorAll('[data-hatena-star]')].every(h=>[...h.shadowRoot.querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth>0)),null,{timeout:30000});}
  await page.locator('.record-preview-thumb img').evaluateAll(es=>Promise.all(es.map(i=>i.decode())));
  const metrics=await page.evaluate(()=>{const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom}};const rows=(sel,image)=>[...document.querySelectorAll(sel)].map(e=>{const r=rect(e),i=rect(e.querySelector(image)),n=e.querySelector('.portal-guide-note'),heading=n?.querySelector('strong'),small=n?.querySelector('small');const noteRect=n?rect(n):null;return {row:r,image:i,top:i.y-r.y,bottom:r.bottom-i.bottom,noteRect,visibleContentBottom:n?rect(n.querySelector('.portal-guide-note__details > .portal-update-note:not([hidden])')||small).bottom:null,textCenterOffset:noteRect?(noteRect.y+noteRect.bottom-i.y-i.bottom)/2:null}});return {records:rows('.record-preview-row','.record-preview-thumb'),guides:rows('.portal-guide-row','.portal-card'),panels:[...document.querySelectorAll('.portal-records-hero,.portal-explore')].map(rect),overflow:document.documentElement.scrollWidth>innerWidth};});
  check(!metrics.overflow,`${variant} top overflow ${width}`);check(metrics.records.length===3&&metrics.guides.length===3,'all six images');
  if(width>=900)check(Math.abs(metrics.panels[0].height-metrics.panels[1].height)<1,'equal PC panels');
  if(variant==='after'&&process.env.LAYOUT_ASSERT_FINAL){
   const rows=await page.locator('.portal-guide-row').evaluateAll(items=>items.map(row=>{
    const card=row.querySelector('.portal-card'),left=card.querySelector('.portal-card__copy');
    const lh=left.querySelector('strong'),ls=left.querySelector('small'),name=lh.querySelector('span');
    const note=row.querySelector('.portal-guide-note'),rh=note.querySelector('strong');
    const details=note.querySelector('.portal-guide-note__details'),rs=details.querySelector('small');
    const cr=card.getBoundingClientRect(),lr=lh.getBoundingClientRect(),sr=ls.getBoundingClientRect();
    const rr=row.getBoundingClientRect(),nr=note.getBoundingClientRect(),hr=rh.getBoundingClientRect(),dr=rs.getBoundingClientRect();
    const dcss=getComputedStyle(rs),lcss=getComputedStyle(ls);
    return {
      leftTitle:name.textContent,leftSubtitle:ls.textContent,
      leftCenterOffset:(lr.y+sr.bottom)/2-(cr.y+cr.height/2),
      leftTitleWhiteSpace:getComputedStyle(name).whiteSpace,leftSubtitleWhiteSpace:lcss.whiteSpace,
      leftTitleLineHeight:parseFloat(getComputedStyle(lh).lineHeight),leftTitleHeight:lr.height,
      leftSubtitleHeight:sr.height,leftSubtitleLineHeight:parseFloat(lcss.lineHeight),
      rightTitle:rh.textContent,rightSubtitle:rs.textContent,
      rightHeadingTop:hr.y-rr.y,rightFirstLineTop:dr.y-rr.y,
      rightDetailsHeight:details.getBoundingClientRect().height,
      rightDescHeight:dr.height,rightLineHeight:parseFloat(dcss.lineHeight),
      rightClamp:dcss.webkitLineClamp,rightWhiteSpace:dcss.whiteSpace,
      cardHeight:cr.height,noteCenterOffset:(nr.y+nr.height/2)-(cr.y+cr.height/2)
    };
   }));
   const historicAnchors=await page.evaluate(()=>{
     const elements=[...document.querySelectorAll('.portal-guide-row')];
     const take=()=>elements.map(row=>{
       const card=row.querySelector('.portal-card').getBoundingClientRect();
       const note=row.querySelector('.portal-guide-note');
       const h=note.querySelector('strong').getBoundingClientRect(),d=note.querySelector('.portal-guide-note__details > small').getBoundingClientRect();
       return {headingTop:h.y-card.y,firstLineTop:d.y-card.y};
     });
     const current=take(),style=document.createElement('style');
     // Reproduce the exact PR #165 right-note layout; only this temporary
     // reference style changes and it is removed before screenshots.
     style.textContent=`
       .portal-guide-note__details { display:flex; flex-wrap:wrap; align-content:flex-start; align-items:center; min-height:46px; gap:3px 8px; }
       .portal-guide-note__details > small { display:block; flex:1 1 100%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
       .portal-index .portal-guide-note { top:calc((46px - 1.276rem)/2); }
       @media(max-width:680px) { .portal-index .portal-guide-note { top:0; } }
     `;
     document.head.append(style);const original=take();style.remove();
     return {current,original};
   });
   for(let i=0;i<3;i++){
     check(Math.abs(historicAnchors.current[i].headingTop-historicAnchors.original[i].headingTop)<1,'right heading matches exact pre-PR166 vertical position');
     check(Math.abs(historicAnchors.current[i].firstLineTop-historicAnchors.original[i].firstLineTop)<1,'right copy first line matches exact pre-PR166 vertical position');
   }
   check(rows.length===3,'all three search cards have paired labels and right-hand explanations');
   const approved=[
     ['図鑑を見る','キノコの名前から探す','名前から探したい場合は','名前を検索したり、五十音順の一覧から探せます。'],
     ['季節から探す','季節ごとに写真を見る','季節ごとに写真を見たい場合は','このブログで撮影したキノコを、季節ごとにまとめています。'],
     ['特徴から探す','見た目の特徴から絞り込む','名前がわからない場合は','傘やヒダなど、見た目の特徴から絞り込めます。']
   ];
   for(let i=0;i<3;i++){
    const c=rows[i],e=approved[i];
    check(c.leftTitle===e[0]&&c.leftSubtitle===e[1]&&c.rightTitle===e[2]&&c.rightSubtitle===e[3],'approved left and right text unchanged');
    check(c.leftTitleWhiteSpace==='nowrap'&&c.leftSubtitleWhiteSpace==='nowrap','left image text remains exactly two lines total');
    check(Math.abs(c.leftSubtitleHeight-c.leftSubtitleLineHeight)<1.1,'left image subtitle reserves only one line');
    check(Math.abs(c.leftCenterOffset)<1.1,'left image title and subtitle visually centered together');
    check(c.rightClamp==='2'&&c.rightWhiteSpace==='normal','right explanations clamp to 2 lines');
    check(Math.abs(c.rightDescHeight-2*c.rightLineHeight)<1.1,'right explanation reserves exactly two lines');
    check(Math.abs(c.rightHeadingTop-rows[0].rightHeadingTop)<1.1,'right headings start at same vertical coordinate');
    check(Math.abs(c.rightFirstLineTop-rows[0].rightFirstLineTop)<1.1,'right explanation first lines start at same vertical coordinate');
    check(Math.abs(c.cardHeight-rows[0].cardHeight)<1,'search card thumbnail height unchanged');
    if(width>680)check(c.noteCenterOffset>0&&c.noteCenterOffset<27,'right note bottom extension stays within compact alignment');
   }
   const dynamic=await page.locator('.portal-guide-row').first().locator('.portal-guide-note').evaluate(note=>{
     const headline=note.querySelector('strong'),details=note.querySelector('.portal-guide-note__details'),desc=details.querySelector('small');
     const get=()=>({headingY:headline.getBoundingClientRect().y,descriptionY:desc.getBoundingClientRect().y,detailsHeight:details.getBoundingClientRect().height,descriptionHeight:desc.getBoundingClientRect().height,scrollHeight:desc.scrollHeight,clientHeight:desc.clientHeight,rowBottom:note.closest('.portal-guide-row').getBoundingClientRect().bottom,noticeBottom:details.querySelector('.portal-update-note')?.getBoundingClientRect().bottom});
     const initial=get(),original=desc.textContent;
     desc.textContent='短い説明';const short=get();
     desc.textContent='画像の特徴や名前から探せるいろいろなキノコの情報'.repeat(15);const long=get();
     const fresh=document.createElement('span');fresh.className='portal-update-note';
     const summary=document.createElement('span');summary.className='portal-update-summary';summary.textContent='新着';fresh.append(summary);details.append(fresh);
     const withNotice=get();
     fresh.remove();desc.textContent=original;
     return {initial,short,long,withNotice};
   });
   const approx=(a,b)=>Math.abs(a-b)<1.1;
   for(const variant of ['short','long','withNotice']){
     check(approx(dynamic[variant].headingY,dynamic.initial.headingY),'right heading does not jump on short/long copy or notice');
     check(approx(dynamic[variant].descriptionY,dynamic.initial.descriptionY),'right first line does not jump on short/long copy or notice');
     check(approx(dynamic[variant].descriptionHeight,dynamic.initial.descriptionHeight),'right two-line area remains fixed');
     check(approx(dynamic[variant].detailsHeight,dynamic.initial.detailsHeight),'new arrival notice keeps reserved height');
   }
   check(dynamic.long.scrollHeight>dynamic.long.clientHeight,'long right-hand description truncates after two lines');
   check(dynamic.withNotice.noticeBottom<=dynamic.withNotice.rowBottom+1,'visible new notice fits within its row even at compact desktop widths');
  }

  measurements.push({width,variant,page:'new-top',...metrics});
  await page.screenshot({path:path.join(out,`top-${width}-${variant}.png`),fullPage:true,animations:'disabled'});
  for(const name of ['best-shots','best-shots-2025','best-shots-2026']){
   await page.goto(`${base}/${variant}/${name}.html`);await page.evaluate(()=>document.fonts.ready);
   for(const img of await page.locator('.best-shot-photo img').all()){await img.scrollIntoViewIfNeeded();await img.evaluate(i=>i.decode());}
   const cards=await page.locator('.best-shot-grid .best-shot-card').evaluateAll(es=>es.map(e=>{const rect=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom}};const im=e.querySelector('img');return {id:e.dataset.selectionId,card:rect(e),frame:rect(e.querySelector('.best-shot-photo')),body:rect(e.querySelector('.best-shot-card__body')),name:rect(e.querySelector('h3')),image:rect(im),natural:[im.naturalWidth,im.naturalHeight],fit:getComputedStyle(im).objectFit,transform:getComputedStyle(im).transform};}));
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name} overflow ${width}`);
   if(variant==='after'&&process.env.LAYOUT_ASSERT_FINAL){for(const c of cards){check(c.fit==='contain','whole image contain');check(c.image.width>0&&c.image.height>0,'visible photo');}for(let i=1;i<cards.length;i++)if(Math.abs(cards[i].card.y-cards[i-1].card.y)<1){check(Math.abs(cards[i].body.y-cards[i-1].body.y)<1,'aligned body');check(Math.abs(cards[i].name.y-cards[i-1].name.y)<1,'aligned names including annual selection');}}
   if(variant==='after'){
    for(const card of await page.locator('.best-shot-grid .best-shot-card').all()){
     const im=card.locator('.best-shot-photo img'),natural=await im.evaluate(i=>({w:i.naturalWidth,h:i.naturalHeight})),box=await im.boundingBox();
     if(width<=680&&natural.h/natural.w<3)check(Math.abs(box.height/box.width-natural.h/natural.w)<.01,'one-column natural image ratio');
     const badge=card.locator('.best-shot-badge');
     if(await badge.count()){check(await card.locator('.best-shot-photo .best-shot-badge').count()===1,'monthly badge inside photo link');check(await badge.evaluate(e=>getComputedStyle(e).pointerEvents==='none'),'badge does not intercept clicks');const b=await badge.boundingBox(),f=await card.locator('.best-shot-photo').boundingBox();check(b.x>=f.x+9&&b.y>=f.y+9&&b.x+b.width<=f.x+f.width,'badge top-left within mount');}
    }
   }
   measurements.push({width,variant,page:name,cards});
   if([1280,390].includes(width)){await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,`${name}-${width}-${variant}.png`),fullPage:true,animations:'disabled'});}
  }
 }
}
if(process.env.LAYOUT_ASSERT_FINAL){for(const after of measurements.filter(m=>m.page==='new-top'&&m.variant==='after')){const before=measurements.find(m=>m.page==='new-top'&&m.variant==='before'&&m.width===after.width);check(Math.abs(after.panels[0].height-before.panels[0].height)<1,'observation panel height preserved');if(after.width>680)check(Math.abs(after.panels[1].height-before.panels[1].height)<1,'guide panel height preserved on side-by-side layouts');else check(Math.abs(after.panels[1].height-before.panels[1].height)<20,'only the compact mobile notice reserve changes total panel height');for(const kind of ['records','guides']){const heights=after[kind].map(r=>r.image.height);check(Math.max(...heights)-Math.min(...heights)<1,'equal thumbnail heights');for(let i=0;i<3;i++){if(process.env.LAYOUT_EXPECT_UNCHANGED==='1'){check(Math.abs(after[kind][i].image.height-before[kind][i].image.height)<1,'preserved image height');if(kind==='guides'&&after.width<=680){
  const newSpace=after[kind][i].top+after[kind][i].bottom,oldSpace=before[kind][i].top+before[kind][i].bottom;
  check(newSpace-oldSpace>=-5&&newSpace-oldSpace<=1,'mobile right-hand copy clearance changes only by the 3px notice reserve');
 }else check(Math.abs((after[kind][i].top+after[kind][i].bottom)-(before[kind][i].top+before[kind][i].bottom))<1,'preserved whitespace');}else{check(after[kind][i].image.height>before[kind][i].image.height,'increased image height');check(after[kind][i].top+after[kind][i].bottom<before[kind][i].top+before[kind][i].bottom,'reduced whitespace');}if(kind==='guides'&&after.width<=680){
  const change=after[kind][i].row.height-before[kind][i].row.height;
  check(change>=-5&&change<=1,'mobile row shrinks only by the 3px notice reserve');
 }else check(Math.abs(after[kind][i].row.height-before[kind][i].row.height)<1,'unchanged row height');if(kind==='guides'&&after.width>680)check(after[kind][i].visibleContentBottom<=after[kind][i].row.bottom+1,'visible right-side copy stays within its row');}}}}
// Compare three real CSS mounts using the same October photographs.
for(const width of [1280,390]){await page.setViewportSize({width,height:1000});for(const variant of ['before','after']){await page.goto(`${base}/${variant}/best-shots-2025.html`);const month=page.locator('.best-shot-month').filter({has:page.getByRole('heading',{name:/^10月(?:の展示)?$/})});for(const i of await month.locator('img').all()){await i.scrollIntoViewIfNeeded();await i.evaluate(i=>i.decode());}await month.screenshot({path:path.join(out,`mixed-${width}-${variant}.png`),animations:'disabled'});}
 for(const [name,css] of [['A',''],['B','.best-shots-index .best-shot-grid .best-shot-photo{aspect-ratio:1;padding:20px;background:#f4f1e9}'],['C','.best-shots-index .best-shot-grid .best-shot-photo{aspect-ratio:3/2}']]){await page.goto(`${base}/after/best-shots-2025.html`);if(css)await page.addStyleTag({content:css});const month=page.locator('.best-shot-month').filter({has:page.getByRole('heading',{name:/^10月(?:の展示)?$/})});for(const i of await month.locator('img').all()){await i.scrollIntoViewIfNeeded();await i.evaluate(i=>i.decode());}await month.screenshot({path:path.join(out,`option-${name}-${width}.png`),animations:'disabled'});}
 // Extreme aspect ratios and maximum-length comments live only in this DOM.
 await page.goto(`${base}/after/best-shots-2025.html`);await page.locator('.best-shot-grid').first().evaluate(grid=>{grid.replaceChildren(...[...grid.children].slice(0,2));[...grid.children].forEach((card,i)=>{const [w,h]=i?[200,3200]:[3200,200];card.querySelector('img').src=`data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="100%" height="100%" fill="#bfd7ae"/></svg>`)}`;card.querySelector('.best-shot-comment').textContent=i?'長いコメント'.repeat(30):'短いコメント';});});for(const i of await page.locator('.best-shot-grid').first().locator('img').all()){await i.scrollIntoViewIfNeeded();await i.evaluate(i=>i.decode());check(await i.evaluate(e=>getComputedStyle(e).objectFit==='contain'),'extreme image contain');}check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'extreme ratio and comments no overflow');await page.locator('.best-shot-grid').first().screenshot({path:path.join(out,`extreme-${width}.png`),animations:'disabled'});
}
check(errors.length===0,'no JS errors');fs.writeFileSync(path.join(out,'measurements.json'),JSON.stringify({assertions,live_stars:!!process.env.LAYOUT_LIVE_STARS,fixture,measurements,errors},null,2));console.log(`PASS: ${assertions} layout assertions; eight widths, three Best Shot pages`);await browser.close();server.close();})().catch(async e=>{console.error(e);if(browser)await browser.close();server.close();process.exitCode=1;});
