'use strict';
// Read-only feasibility: use the blog's native profile-icon renderer, never click add.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(process.argv[2]),fixture=JSON.parse(fs.readFileSync(path.join(root,'fixture.json'))),writes=[];
const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(fs.readFileSync(path.join(root,'profile-probe.html')))});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const c=await browser.newContext({viewport:{width:768,height:600}});await c.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(r.method()!=='GET'||/(star\.add|star\.delete|\/stars?\/(add|delete|remove))/.test(u.pathname)){writes.push({method:r.method(),path:u.pathname});return route.abort()}return route.continue()});
  const page=await c.newPage();await page.goto('http://127.0.0.1:'+server.address().port,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(totals=>[...document.querySelectorAll('.native-probe')].every((r,i)=>{const s=r.querySelector('[data-hatena-star]')?.shadowRoot;if(!s||!s.querySelector('iframe'))return false;return [...s.children].reduce((n,c)=>n+(c.tagName==='A'?1:c.tagName==='BUTTON'?Number(c.textContent):0),0)===totals[i]}),fixture.records.map(r=>r.total));
  await page.locator('.native-probe').first().locator('a').first().waitFor({state:'attached'});
  const evidence=[];
  for(let i=0;i<3;i++){
   const row=page.locator('.native-probe').nth(i),expected=fixture.records[i];
   assert.equal(await row.locator('[data-hatena-star]').count(),1);
   assert.equal(new URL(await row.locator('iframe').getAttribute('src')).searchParams.get('url'),expected.uri);
   assert.equal(new URL(await row.locator('iframe').getAttribute('src')).searchParams.get('variant'),'profile-icon');
   await row.locator('iframe').contentFrame().locator('button').first().waitFor();
   const stars=await row.locator('[data-hatena-star]').evaluate(e=>[...e.shadowRoot.children].filter(c=>c.tagName==='A'||c.tagName==='BUTTON').map(c=>({count:c.tagName==='BUTTON'?Number(c.textContent):1,avatar:c.querySelector('picture img')?.getAttribute('src'),name:c.querySelector('picture img')?.alt,color:c.querySelector('img[title]')?.title,href:c.getAttribute('href')})));
   assert.equal(stars.reduce((a,s)=>a+s.count,0),expected.total);
   for(const s of stars.filter(s=>s.avatar)){assert.equal(s.avatar,'https://cdn.profile-image.st-hatena.com/users/'+s.name+'/profile.png');assert.equal(s.href,'https://blog.hatena.ne.jp/'+s.name+'/');assert.ok(expected.stars.some(e=>e.name===s.name&&'★('+e.color+')'===s.color))}
   evidence.push({uri:expected.uri,total:expected.total,stars});
  }
  const first=page.locator('.native-probe').first().locator('a').first();await first.hover();await page.waitForFunction(()=>document.querySelector('.native-probe [data-hatena-star]').shadowRoot.querySelector('a').innerText.includes('id:'));
  await page.screenshot({path:path.join(root,'screenshots','native-profile-probe.png')});assert.deepEqual(writes,[]);
  fs.writeFileSync(path.join(root,'profile-probe-result.json'),JSON.stringify({result:'PASS',renderer:'official widget/star.js profile-icon',generic_companion:'official HatenaStar.js with empty SiteConfig; no duplicate hosts',hover:'native id tooltip observed',evidence,writes,real_star_addition:'NOT_ATTEMPTED',authenticated_addition:'UNVERIFIED'},null,2));
  console.log('PASS: native profile avatars, colour overlays, original URI, native tooltip and add iframe; no writes');
 }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exit(1)});
