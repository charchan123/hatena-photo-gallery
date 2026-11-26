const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");
const http = require("node:http");
const fs = require("node:fs/promises");
const path = require("node:path");
const assert = require("node:assert/strict");
const modules = process.env.BROWSER_MODULES || "node_modules";
const root = process.argv[2] ?? "public";
const label = process.argv[3] ?? "base";
const type = {".html":"text/html; charset=utf-8",".js":"text/javascript",".css":"text/css", ".woff2":"font/woff2"};
const cdn = {
 "lightgallery.min.js":"lightgallery/lightgallery.min.js",
 "lightgallery-bundle.min.css":"lightgallery/css/lightgallery-bundle.min.css",
 "lg-zoom.min.js":"lightgallery/plugins/zoom/lg-zoom.min.js",
 "lg-thumbnail.min.js":"lightgallery/plugins/thumbnail/lg-thumbnail.min.js",
 "lg-autoplay.min.js":"lightgallery/plugins/autoplay/lg-autoplay.min.js",
 "lg-share.min.js":"lightgallery/plugins/share/lg-share.min.js",
 "imagesloaded.pkgd.min.js":"imagesloaded/imagesloaded.pkgd.min.js",
};
const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="600"><rect width="900" height="600" fill="#cbc8ac"/></svg>';
(async () => {
 const original=JSON.parse(await fs.readFile("published-85.json"));
 const pending=JSON.parse(await fs.readFile("pending-guide-pages.json"));
 const pages=label==="draft" ? JSON.parse(await fs.readFile("draft-guide-pages.json")) : {...original,...pending};
 const site=http.createServer(async (req,res)=>{
   try{
    const filename=decodeURIComponent(new URL(req.url,"http://localhost").pathname).replace(/^\//,"");
    const bytes=await fs.readFile(path.join(root,filename));
    res.setHeader("Content-Type",type[path.extname(filename)]||"application/octet-stream");res.end(bytes);
   } catch {res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>site.listen(0,"127.0.0.1",resolve));
 const local="http://127.0.0.1:"+site.address().port;
 const browser=await chromium.launch({args:["--no-sandbox"]});
 try {
 const result={}, flow={};
 for(const [viewport,width,height] of [["PC",1440,1000],["スマホ",390,844],["狭幅スマホ",320,720]]){
  const ctx=await browser.newContext({viewport:{width,height},isMobile:width<600,hasTouch:width<600,deviceScaleFactor:1});
  await ctx.route("**/*",async (route)=>{
    const req=route.request(); if(req.url().startsWith(local)&&req.resourceType()!=="image")return route.continue();
    const name=new URL(req.url()).pathname.split("/").at(-1);
    if(cdn[name])return route.fulfill({
      contentType:type[path.extname(name)],
      body:await fs.readFile(path.join(modules,cdn[name])),
    });
    if(req.resourceType()==="image")return route.fulfill({contentType:"image/svg+xml",body:svg});
    return route.abort();
  });
  const workers=await Promise.all(Array.from({length:5},()=>ctx.newPage()));
  const jobs=Object.entries(pages);
  let index=0;
  await Promise.all(workers.map(async(page)=>{
    while(index<jobs.length){
      const [id,filename]=jobs[index++];
      const response=await page.goto(local+"/"+encodeURIComponent(filename),{waitUntil:"load",timeout:18000});
      assert.equal(response.status(),200);
      if(label==="base" && id in pending){
       assert.equal(await page.locator(".knowledge-panel").count(),0);
       const visible=await page.locator(".knowledge-pending").isVisible();
       assert.ok(visible,id);
       result[id]??={};
       result[id][viewport]={pending:true, outerOverflow:await page.evaluate(() =>
        Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-document.documentElement.clientWidth)};
       if(["kitamagotake","tamagotengutakemodoki"].includes(id)){
        await page.locator(".knowledge-pending").screenshot({path:`screens/${label}-${id}-${width}.png`});
       }
       continue;
      }
      const details=page.locator(".knowledge-sources");
      await details.locator("summary").click();
      const item=await page.evaluate(()=>{
       const panel=document.querySelector(".knowledge-panel"), links=[...panel.querySelectorAll(".knowledge-sources a")];
       const px=document.documentElement.clientWidth;
       const outerOverflow=Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-px;
       const array=[...panel.querySelectorAll(".knowledge-row")];
       const spills=array.filter(row=>{
        const box=row.getBoundingClientRect();
        return box.right>px+1 || [...row.children].some(child=>child.scrollWidth>child.clientWidth+2);
       }).map(row=>row.querySelector("dt").textContent);
       const overlaps=array.some(row=>{
        const a=row.children[0].getBoundingClientRect(), b=row.children[1].getBoundingClientRect();
        return a.left<b.right-1&&a.right>b.left+1&&a.top<b.bottom-1&&a.bottom>b.top+1;
       });
       return {width:px,outerOverflow,spills,overlaps,sources:links.length,sourceLinks:links.map(a=>a.getAttribute("href")),linksVisible:links.every(a=>!!a.getClientRects().length),opened:panel.querySelector(".knowledge-sources").open,
               warningCount:panel.querySelectorAll(".knowledge-warning").length,
               safetyLabel:array.find(r=>r.children[0].textContent==="食毒情報")?.children[1].firstChild.textContent ?? null,
               warning:panel.querySelector(".knowledge-warning")?.textContent ?? panel.innerText.split("\n").slice(-1)[0],
               foodNote:array.find(r=>r.children[0].textContent==="食毒情報")?.children[1].textContent ?? null,
               labels:array.map(row=>row.children[0].textContent)};
      });
      result[id]??={};result[id][viewport]=item;
      if(["enokitake","naratake","mukitake","kakisimeji","uraguronigaiguchi","kurokawa","chaamigasatake","kitamagotake","tamagotengutakemodoki","kihoukitake"].includes(id)){
       await page.locator(".knowledge-panel").screenshot({path:`screens/${label}-${id}-${width}.png`});
      }
    }
  }));
  for(const page of workers)await page.close();
  const probe=await ctx.newPage();
  await probe.goto(local+"/"+encodeURIComponent(pages.enokitake),{waitUntil:"load"});
  const photo=probe.locator(".gallery a.gallery-item").first();
  let opened=false, closed=false, scrollDifference=null, error=null;
  try{
    await photo.scrollIntoViewIfNeeded({timeout:2500});
    await probe.waitForTimeout(250);
    const before=await probe.evaluate(()=>scrollY);
    await photo.click({timeout:3000});
    const close=probe.locator(".lg-close");
    await close.waitFor({state:"visible",timeout:2500});
    opened=true;
    await close.click();
    await close.waitFor({state:"hidden",timeout:4000});
    closed=true;
    await probe.waitForTimeout(350);
    scrollDifference=Math.abs((await probe.evaluate(()=>scrollY))-before);
  }catch(e){error=String(e).split("\n")[0];}
  flow[viewport]={opened,closed,scrollDifference,error};
  await ctx.close();
 }
 console.log(JSON.stringify({label,pages:Object.keys(result).length,flow,issues:Object.entries(result).flatMap(([id,v])=>Object.entries(v).filter(([,q])=>q.outerOverflow>1||(!q.pending&&(q.spills.length||q.overlaps||!q.opened||!q.linksVisible))).map(([width,q])=>({id,width,outerOverflow:q.outerOverflow,spills:q.spills,overlaps:q.overlaps})))},null,2));
 await fs.writeFile(`browser-${label}.json`,JSON.stringify({result,flow},null,2));
 } finally {await browser.close();site.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
