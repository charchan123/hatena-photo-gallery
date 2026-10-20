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
  await page.waitForFunction(()=>[...document.querySelectorAll('.native-probe [data-hatena-star]')].every(h=>[...h.shadowRoot.querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth>0)));
  const first=page.locator('.native-probe').first().locator('a').first();await first.hover();await page.waitForFunction(()=>document.querySelector('.native-probe [data-hatena-star]').shadowRoot.querySelector('a').innerText.includes('id:'));
  await page.screenshot({path:path.join(root,'screenshots','native-profile-probe.png')});assert.deepEqual(writes,[]);
  // Read the real blog's visible native widget as an independent visual reference.
  // Unrelated scripts are blocked; no account/session or add operation is used.
  const real=await browser.newContext({viewport:{width:768,height:700}});
  await real.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(r.method()!=='GET'||/(star\.add|star\.delete|\/stars?\/(add|delete|remove))/.test(u.pathname)){writes.push({method:r.method(),path:u.pathname});return route.abort()}if(r.resourceType()==='script'&&u.hostname!=='s.hatena.ne.jp')return route.abort();return route.continue()});
  const original=await real.newPage();await original.goto('https://exsudoporus-ruber.hatenablog.jp/',{waitUntil:'domcontentloaded'});
  const blog=original.locator('[data-hatena-star-container]').filter({visible:true}).first();
  await blog.locator('a').first().waitFor({state:'visible'});
  await original.waitForFunction(()=>[...document.querySelectorAll('[data-hatena-star-container]')].filter(c=>c.getBoundingClientRect().width>0).slice(0,1).every(c=>{const h=c.querySelector('[data-hatena-star]');return h?.shadowRoot&&[...h.shadowRoot.querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth>0)}));
  assert.equal(await blog.getAttribute('data-hatena-star-url'),fixture.records[0].uri);
  const actual=await blog.locator('[data-hatena-star]').evaluate(h=>[...h.shadowRoot.children].filter(n=>n.tagName==='A'||n.tagName==='BUTTON').map(n=>({count:n.tagName==='BUTTON'?Number(n.textContent):1,avatar:n.querySelector('picture img')?.getAttribute('src'),name:n.querySelector('picture img')?.alt,color:n.querySelector('img[title]')?.title,href:n.getAttribute('href')})));
  assert.deepEqual(actual,evidence[0].stars);
  await blog.screenshot({path:path.join(root,'screenshots','original-blog-native-strip.png')});
  await blog.locator('a').first().hover();await original.waitForFunction(()=>[...document.querySelectorAll('[data-hatena-star-container]')].some(c=>c.querySelector('[data-hatena-star]')?.shadowRoot?.querySelector('a')?.innerText.includes('id:')));
  assert.deepEqual(writes,[]);await real.close();
  fs.writeFileSync(path.join(root,'profile-probe-result.json'),JSON.stringify({result:'PASS',renderer:'official widget/star.js profile-icon',generic_companion:'official HatenaStar.js with empty SiteConfig; no duplicate hosts',hover:'native id tooltip observed on isolated and real blog pages',original_blog:{uri:fixture.records[0].uri,exact_native_items_match:true,profile_avatars_loaded:true,unrelated_scripts_blocked:true},evidence,writes,real_star_addition:'NOT_ATTEMPTED',authenticated_addition:'UNVERIFIED'},null,2));
  console.log('PASS: native profile avatars, colour overlays, original URI, native tooltip and add iframe; no writes');
 }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exit(1)});
