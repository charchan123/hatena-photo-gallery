'use strict';
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),out=path.resolve(process.argv[2]||process.env.ADMIN_PR_EVIDENCE||'/tmp/admin-pr-evidence');fs.mkdirSync(out,{recursive:true});
let child,browser,port,assertions=0;
const check=(value,label)=>{assert.ok(value,label);assertions++};
async function start(){child=spawn(process.env.PYTHON_BIN||'python',['tests/browser/admin_pr_server.py',path.join(out,'fixture')],{cwd:root,stdio:['ignore','pipe','inherit']});port=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('server start timeout')),15000);child.on('exit',code=>reject(Error('server exit '+code)));child.stdout.on('data',data=>{text+=data;const line=text.split('\n')[0];try{const state=JSON.parse(line);clearTimeout(timer);resolve(state.port)}catch{}})});}
async function stop(){if(child){const p=child;child=null;p.kill();await new Promise(resolve=>p.once('exit',resolve))}}
(async()=>{
 await start();browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:1000}}),page=await context.newPage();
 await context.route('https://fixture.test/**',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"><rect width="300" height="200" fill="#bcd0ab"/></svg>'}));
 const base=()=>`http://127.0.0.1:${port}`;
 async function visit(){await page.goto(base());await page.waitForSelector('#cards .card');}
 async function state(){return page.evaluate(async()=>await(await fetch('/__fixture/state')).json())}
 async function mode(value){await page.evaluate(value=>fetch('/__fixture/mode',{method:'POST',body:JSON.stringify({mode:value})}),value)}
 async function open(){await page.click('[data-page=changes]');await page.click('#validate');await page.waitForFunction(()=>!document.querySelector('#create-pr').disabled);await page.click('#create-pr');}
 await visit();
 await page.evaluate(async()=>{const s=await(await fetch('/api/state')).json();const r=await fetch('/api/best-shot/update',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':s.csrf},body:JSON.stringify({selection_id:'fixture-best',changes:{comment:'管理人が確認した変更予定'}})});if(!r.ok)throw Error('fixture edit failed')});await page.reload();
 const saved=(await state()).saved.files;
 for(const [value,text] of [['stale','手動照合'],['auth','gh auth login'],['save','空き容量'],['validation','入力検証']]){
  await mode(value);await open();await page.click('#confirm-ok');
  await page.waitForFunction(()=>document.querySelector('#confirm-error')?.textContent.length>0);
  check(await page.locator('#confirm').isVisible(),value+' dialog stays open');
  check((await page.locator('#confirm-error').innerText()).includes(text),value+' actionable error');
  check(await page.locator('#confirm-error').evaluate(e=>e.getBoundingClientRect().top>=0&&e.getBoundingClientRect().bottom<=innerHeight),value+' visible inside modal');
  check(await page.locator('#confirm-ok').isEnabled(),value+' retry enabled');
  assert.deepEqual((await state()).saved.files,saved);assertions++;
  await page.screenshot({path:path.join(out,value+'-error.png')});
  await page.locator('#confirm [value=cancel]').click();
 }
 await mode('success');await open();const calls=(await state()).calls;
 await page.click('#confirm-ok');check(await page.locator('#confirm-ok').isDisabled(),'submit locked');
 await page.keyboard.press('Escape');check(await page.locator('#confirm').isVisible(),'Escape blocked during creation');
 await page.locator('#confirm-ok').dispatchEvent('click');
 await page.waitForFunction(()=>!document.querySelector('#confirm').open);
 const link=page.locator('#message a');check(await link.getAttribute('href')==='https://github.com/fixture/test/pull/123','success URL link');
 check((await page.locator('#message').innerText()).includes('明示承認'),'success requires approval and CI');
 check((await state()).calls===calls+1,'double click cannot duplicate PR');
 assert.deepEqual((await state()).saved.files,saved);assertions++;
 await page.screenshot({path:path.join(out,'draft-pr-success.png')});
 await mode('refresh');await open();await page.click('#confirm-ok');await page.waitForFunction(()=>!document.querySelector('#confirm').open);
 check(await page.locator('#message a').getAttribute('href')==='https://github.com/fixture/test/pull/123','refresh failure retains successful URL');
 await stop();await start();await visit();const restored=await page.evaluate(async()=>await(await fetch('/api/state')).json());
 check(restored.draft_restored,'restart restores local draft');
 check(restored.best_shots.entries[0].comment==='管理人が確認した変更予定','draft content preserved');
 check(JSON.parse(fs.readFileSync(path.join(out,'fixture/data/best-shots.json'),'utf8')).entries[0].comment==='元のコメント','source data untouched');
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({assertions,draft:true,ci:'pending',production_writes:false},null,2));
 console.log('PASS:',assertions,'real localhost admin PR assertions');await browser.close();await stop();
})().catch(async error=>{console.error(error);if(browser)await browser.close();await stop();process.exitCode=1});
