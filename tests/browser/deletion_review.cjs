'use strict';
// Isolated real Chromium desktop/touch regressions. No backend/source writes.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),out=process.env.DELETION_SCREENSHOTS;
const oid='obs-'+ 'a'.repeat(64),cid='b'.repeat(64),fp='c'.repeat(64);
function fixtures(){return {csrf:'fixture-token',observations:[],best_shots:{version:1,entries:[],annual_best:{}},cases:[],identified:[],notices:[],master:[],knowledge:[],preview:{},repo:{gh_authenticated:false},feature_facets:{},counts:{best_shots:0,annual_years:0,research_open:0,research_identified:0,active_notices:0,master:0,sources:0,knowledge_batches:0},portal_source:'fixture',portal_observation_count:0}}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox',...(process.env.CHROMIUM_SINGLE_PROCESS?['--single-process','--no-zygote','--disable-gpu']:[])]});let assertions=0;
 const check=(actual,expected)=>{assert.deepEqual(actual,expected);assertions++};
 async function setup(options={}){
  const context=await browser.newContext(options),page=await context.newPage(),writes=[],issues=[];let failure=null;
  const state={rows:[{candidate_id:cid,fingerprint:fp,observation_id:oid,gallery_name:'カワリハツ？',src:'https://photos.example.test/old.svg',article_title:'隔離fixtureの観察記事',article_url:'https://example.test/entry/1',kind:'photo_deleted',status:'approval_pending',identity_issues:[],mass_review:false,protection:[{kind:'research',id:'research-940496f1ccdb136f'}]}],live:true,history_count:2,audit:[],pr_attempts:[{branch:'admin/photo-deletion-fixture',status:'pending_remote'}],last_checked_at:'2026-10-15T00:00:00Z',last_success_at:'2026-10-13T00:00:00Z'};
  page.on('pageerror',e=>issues.push(e.message));
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(url.hostname==='photos.example.test')return route.fulfill({status:404,body:''});
   if(url.pathname==='/api/state')return route.fulfill({json:fixtures()});
   if(url.pathname==='/api/deletions/state')return route.fulfill({json:state});
   if(url.pathname.startsWith('/api/deletions/')){
    writes.push({path:url.pathname,body:req.postDataJSON()});await new Promise(r=>setTimeout(r,150));
    if(failure==='network'){failure=null;return route.abort('failed')}
    if(failure){const value=failure;failure=null;return route.fulfill({status:400,json:value})}
    const body=req.postDataJSON();
    if(url.pathname.endsWith('/decision')){state.rows[0].decision={...body,note:body.reason,stale:false};state.audit.push({action:body.action});return route.fulfill({json:{saved:true,published:false}})}
    if(url.pathname.endsWith('/preview'))return route.fulfill({json:{fingerprint:'d'.repeat(64),files:{'sync-migrations/photo-deletions/fixture.json':{action:state.rows[0].decision.action}},published:false}});
    if(url.pathname.endsWith('/pr'))return route.fulfill({json:{url:'https://github.com/example/fixture/pull/1',draft:true,published:false}});
    return route.fulfill({json:state});
   }
   const file={'/':'index.html','/admin.css':'admin.css','/admin.js':'admin.js','/deletions.js':'deletions.js'}[url.pathname];
   if(file)return route.fulfill({body:fs.readFileSync(path.join(root,'admin/static',file)),contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html'});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://127.0.0.1:8765/');await page.waitForSelector('#cards .card');await page.click('[data-page=deletions]');await page.waitForSelector('.deletion-card');
  return {context,page,state,writes,issues,fail:v=>failure=v};
 }
 const d=await setup({viewport:{width:1280,height:1000}}),p=d.page;
 check(await p.locator('#deletion-history').textContent().then(s=>s.includes('admin/photo-deletion-fixture')),true);check(await p.locator('#deletion-summary').innerText().then(s=>s.includes('GitHub')),true);
 check(await p.locator('.deletion-card').count(),1);assert.match(await p.locator('.deletion-card').innerText(),/カワリハツ？[\s\S]*research-940496f1ccdb136f/);assertions++;
 await p.getByText('元画像を読み込めませんでした',{exact:true}).waitFor();check(d.writes.length,0);check(await p.locator('.deletion-body').evaluate(e=>e.getBoundingClientRect().width>500),true);
 await p.selectOption('[name=deletion-action]','archive_research');await p.fill('[name=deletion-reason]','研究履歴を残して非公開にする');await p.fill('[name=deletion-confirm]',oid);
 d.fail({error:'DELETION_REVIEW_STALE',message:'公開snapshot・写真・参照が変わりました。再取得して確認し直してください。'});
 await p.getByRole('button',{name:'この1件の判断をローカル保存'}).click();await p.waitForFunction(()=>!deletionBusy);
 check(await p.inputValue('[name=deletion-reason]'),'研究履歴を残して非公開にする');check(await p.inputValue('[name=deletion-confirm]'),oid);check(await p.inputValue('[name=deletion-action]'),'archive_research');
 check(await p.locator('#deletions').isVisible(),true);check(await p.evaluate(()=>document.activeElement.id),'deletion-message');assert.match(await p.locator('#deletion-message').innerText(),/変わりました/);assertions++;
 check(await p.locator('[name=deletion-reason]').isEnabled(),true);
 if(out){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,'desktop-deletion-error.png')});}
 const before=d.writes.length;
 await p.getByRole('button',{name:'この1件の判断をローカル保存'}).evaluate(e=>{e.click();e.click()});await p.waitForFunction(()=>!deletionBusy);
 check(d.writes.length,before+1);check(d.writes.at(-1).body.confirm_id,oid);check(d.state.rows[0].decision.action,'archive_research');
 check(await p.inputValue('[name=deletion-reason]'),'研究履歴を残して非公開にする');
 await p.getByRole('button',{name:'承認内容と変更予定の差分を確認'}).click();await p.waitForFunction(()=>!deletionBusy);
 assert.match(await p.locator('#deletion-diff').innerText(),/archive_research/);assertions++;check(await p.locator('#deletion-pr').isEnabled(),true);
 d.fail('network');await p.locator('#deletion-pr').click();await p.waitForFunction(()=>!deletionBusy);
 assert.match(await p.locator('#deletion-message').innerText(),/通信/);assertions++;check(await p.locator('#deletion-pr').isEnabled(),true);
 await p.locator('#deletion-pr').focus();await p.keyboard.press('Enter');await p.waitForFunction(()=>!deletionBusy);
 assert.match(await p.locator('#deletion-diff').innerText(),/Draft PR[\s\S]*公開は行っていません/);assertions++;check(await p.locator('#deletion-pr').isDisabled(),true);
 check(d.issues,[]);
 const m=await setup({viewport:{width:390,height:844},isMobile:true,hasTouch:true}),mp=m.page;
 await mp.selectOption('[name=deletion-action]','hold');await mp.fill('[name=deletion-reason]','管理者の判断を待つ');await mp.getByRole('button',{name:'この1件の判断をローカル保存'}).tap();await mp.waitForFunction(()=>!deletionBusy);
 check(m.writes.length,1);check(m.writes[0].body.action,'hold');check(await mp.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);check(await mp.locator('#deletions').evaluate(e=>e.getBoundingClientRect().width>=340),true);
 await mp.reload();await mp.waitForSelector('#cards .card');await mp.click('[data-page=deletions]');await mp.waitForSelector('.deletion-card');
 check(await mp.inputValue('[name=deletion-reason]'),'管理者の判断を待つ');check(m.writes.length,1);check(m.issues,[]);
 if(out)await mp.screenshot({path:path.join(out,'mobile-research-approval.png'),fullPage:true});
 if(!process.env.CHROMIUM_SINGLE_PROCESS)await d.context.close();if(!process.env.CHROMIUM_SINGLE_PROCESS)await m.context.close();await browser.close();console.log(`PASS: ${assertions} Chromium deletion-review assertions (desktop, keyboard, touch; isolated fixtures)`);
})().catch(e=>{console.error(e);process.exitCode=1});
