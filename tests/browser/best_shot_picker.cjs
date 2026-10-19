'use strict';
// Optional real-browser regression suite. All API/image responses are isolated fixtures.
// PLAYWRIGHT_MODULE_PATH=/path/to/playwright node tests/browser/best_shot_picker.cjs
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const out=process.env.BEST_SHOT_SCREENSHOTS,fixtureRoot=process.env.BEST_SHOT_FIXTURES;
const records=[
 ['obs-1','ベニテングタケ','2026-10-01'],['obs-3','ベニタケ','2026-10-03'],
 ['obs-2','ベニテングタケ','2026-10-02'],['obs-4','バライロウラベニイロガワリ','2026-10-04'],
 ['other-month','キノコ写真 別月','2024-05-01'],
 ['obs-5','ベニテングタケ','2026-09-05'],['obs-6','ベニテングタケ',null],['obs-7','ベニテングタケ','2025-10-07'],
 ...Array.from({length:1000},(_,i)=>['bulk-'+i,'キノコ写真 '+i,'2024-06-01'])
].map(([observation_id,gallery_name,date])=>({observation_id,gallery_name,src:'https://photos.example.test/'+observation_id+'.svg',capture:{date},article:{title:'観察記事 '+observation_id,article_id:'article-'+observation_id}}));
const initial=[{selection_id:'best-1',observation_id:'obs-1',comment:'残すコメント',order:1,annual_comment:'年間の記録',location:'静岡'},
 {selection_id:'best-3',observation_id:'obs-3',comment:'もう一枚',order:3}];
const fixtures=()=>({csrf:'fixture-only',observations:records,best_shots:{version:1,entries:structuredClone(initial),annual_best:{'2026':'best-1'}},
 counts:{best_shots:2,annual_years:1,research_open:0,research_identified:0,active_notices:0,master:0,sources:0,knowledge_batches:0},
 cases:[],identified:[],notices:[],master:[],knowledge:[],preview:{},repo:{gh_authenticated:false},feature_facets:{},portal_source:'isolated fixture',portal_observation_count:records.length});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox',...(process.env.CHROMIUM_SINGLE_PROCESS?['--single-process','--no-zygote','--disable-gpu']:[])]});
 let assertions=0;
 const check=(actual,expected)=>{assert.deepEqual(actual,expected);assertions++};
 async function setup(options={},before=false){
  const context=await browser.newContext(options),page=await context.newPage(),app=fixtures();
  const writes=[],issues=[];let failure=null;
  page.on('pageerror',e=>issues.push(e.message));
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(url.hostname==='photos.example.test')return route.fulfill({status:url.pathname.includes('obs-6')?404:200,contentType:'image/svg+xml',body:url.pathname.includes('obs-6')?'':`<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"><rect width="300" height="200" fill="#d5e9cf"/><text x="24" y="105" font-size="24">${url.pathname.slice(1)}</text></svg>`});
   if(url.pathname==='/api/state')return route.fulfill({json:app});
   if(url.pathname.startsWith('/api/')){
    const body=req.postDataJSON();writes.push({path:url.pathname,body});
    await new Promise(r=>setTimeout(r,120));
    if(failure==='network'){failure=null;return route.abort('failed')}
    if(failure){const result=failure;failure=null;return route.fulfill({status:400,json:result})}
    if(url.pathname==='/api/best-shot/add'){app.best_shots.entries.push(body.entry);app.counts.best_shots++}
    if(url.pathname==='/api/best-shot/update')Object.assign(app.best_shots.entries.find(e=>e.selection_id===body.selection_id),body.changes);
    if(url.pathname==='/api/best-shot/annual'){app.best_shots.annual_best[String(body.year)]=body.selection_id;app.counts.annual_years=Object.keys(app.best_shots.annual_best).length;}
    if(url.pathname==='/api/best-shot/delete'){app.best_shots.entries=app.best_shots.entries.filter(e=>e.selection_id!==body.selection_id);for(const y of Object.keys(app.best_shots.annual_best))if(app.best_shots.annual_best[y]===body.selection_id)delete app.best_shots.annual_best[y];app.counts.best_shots=app.best_shots.entries.length;}
    return route.fulfill({json:{ok:true}});
   }
   const file={'/':'index.html','/admin.css':'admin.css','/admin.js':'admin.js','/deletions.js':'deletions.js'}[url.pathname];
   if(file)return route.fulfill({body:fs.readFileSync(before&&file==='admin.js'?path.join(fixtureRoot,'before-admin.js'):path.join(root,'admin/static',file)),contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html'});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://127.0.0.1:8765/');await page.waitForSelector('#cards .card');await page.click('[data-page=best]');
  return {page,context,app,writes,issues,fail:value=>failure=value};
 }
 function candidate(page,id){return page.locator(`.photo-option[data-observation-id="${id}"]`)}
 async function select(page,id){await candidate(page,id).getByRole('button',{name:'この写真を選択',exact:true}).click()}
 async function open(page){await page.click('#add-best');await page.waitForSelector('#photo-search')}
 async function close(page){await page.locator('#editor').getByRole('button',{name:'キャンセル',exact:true}).click()}
 if(out&&fixtureRoot){
  fs.mkdirSync(out,{recursive:true});
  for(const width of [1280,390])for(const before of [true,false]){
   const x=await setup({viewport:{width,height:1000}},before),q=x.page;
   x.app.best_shots.entries.push({selection_id:'best-2',observation_id:'obs-2',comment:'3枚目の選択',order:2});x.app.counts.best_shots=3;
   await q.reload();await q.click('[data-page=best]');await open(q);await q.fill('#photo-search','べ');await select(q,'obs-4');await q.fill('[name=comment]','4枚目の写真を追加');
   check(await q.locator('#dialog-save').isDisabled(),before);check(await q.locator('[name=order]').inputValue(),before?'1':'4');
   await q.locator('.order-field').scrollIntoViewIfNeeded();await q.screenshot({path:path.join(out,`${width}-${before?'before-limit':'after-order-4'}.png`)});await x.context.close();
  }
 }
 const d=await setup({viewport:{width:1280,height:1000}}),p=d.page;
 await open(p);
 check(await p.locator('.photo-option').count(),24);check(await p.locator('.photo-preview img').count(),0);check(await p.locator('.photo-option img').evaluateAll(images=>images.every(im=>im.loading==='lazy')),true);check(await p.locator('[name=observation_id]').inputValue(),'');
 await p.fill('#photo-search','べ');check(await p.locator('.photo-option').count(),7);
 await p.fill('#photo-search','ベニテ');const ids=await p.locator('.photo-option').evaluateAll(rows=>rows.map(r=>r.dataset.observationId));
 await p.fill('#photo-search','べにて');check(await p.locator('.photo-option').evaluateAll(rows=>rows.map(r=>r.dataset.observationId)),ids);
 await p.fill('#photo-search','ﾍﾞﾆﾃ');check(await p.locator('.photo-option').evaluateAll(rows=>rows.map(r=>r.dataset.observationId)),ids);
 check(await candidate(p,'obs-2').locator('img').getAttribute('src'),records[2].src);
 assert.match(await candidate(p,'obs-2').innerText(),/2026-10-02[\s\S]*観察記事 obs-2/);assertions++;
 await candidate(p,'obs-2').hover();check(await p.locator('.photo-preview').isVisible(),true);check(await p.locator('[name=observation_id]').inputValue(),'');check(d.writes.length,0);
 await candidate(p,'obs-2').getByRole('button',{name:'拡大して確認',exact:true}).click();check(await p.locator('[name=observation_id]').inputValue(),'');
 await p.locator('.photo-preview').getByRole('button',{name:'拡大確認を閉じる'}).click();
 await p.focus('#photo-search');await p.keyboard.press('Enter');check(await p.locator('#editor').isVisible(),true);check(d.writes.length,0);
 await p.locator('#photo-search').evaluate(e=>{e.dispatchEvent(new CompositionEvent('compositionstart'));e.value='べにて';e.dispatchEvent(new InputEvent('input',{isComposing:true}));e.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true}));});
 await candidate(p,'obs-2').getByRole('button',{name:'この写真を選択',exact:true}).click();check(await p.locator('[name=observation_id]').inputValue(),'');
 await p.locator('#photo-search').evaluate(e=>e.dispatchEvent(new CompositionEvent('compositionend')));
 await candidate(p,'obs-2').getByRole('button',{name:'この写真を選択',exact:true}).focus();await p.keyboard.press('Enter');check(await p.locator('[name=observation_id]').inputValue(),'obs-2');check(await p.locator('[name=order]').inputValue(),'2');
 await p.fill('[name=comment]','保存するコメント');
 await p.getByRole('button',{name:'月内順序を1減らす',exact:true}).click();check(await p.locator('[name=order]').inputValue(),'1');check(await p.getByRole('button',{name:'月内順序を1減らす',exact:true}).isDisabled(),true);
 assert.match(await p.locator('#order-error').innerText(),/順序「1」/);assertions++;check(await p.locator('#dialog-save').isDisabled(),true);
 await p.focus('[name=order]');await p.keyboard.press('ArrowDown');check(await p.locator('[name=order]').inputValue(),'1');
 await p.fill('[name=order]','3');check(await p.getByRole('button',{name:'月内順序を1増やす',exact:true}).isDisabled(),false);
 await p.keyboard.press('ArrowUp');check(await p.locator('[name=order]').inputValue(),'4');check(await p.locator('#dialog-save').isEnabled(),true);
 await p.keyboard.press('End');check(await p.locator('[name=order]').inputValue(),'4');
 await p.fill('[name=order]','2');
 await p.locator('[name=order]').evaluate(e=>{e.dispatchEvent(new WheelEvent('wheel',{deltaY:100,bubbles:true}));e.dispatchEvent(new ClipboardEvent('paste',{bubbles:true}));});check(await p.locator('[name=order]').inputValue(),'2');
 for(const bad of ['0','-1','1.5','','1e2','9007199254740993']){
  await p.fill('[name=order]',bad);check(await p.locator('#dialog-save').isDisabled(),true);
  await p.locator('#editor form').evaluate(f=>f.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  check(await p.locator('#editor').isVisible(),true);check(await p.locator('#order-error').innerText(),'1以上の整数を入力してください');check(d.writes.length,0);
  await p.fill('[name=order]','2');
 }
 // Manual value stays unchanged while searching/previewing; a different chosen photo recalculates.
 await select(p,'obs-5');check(await p.locator('[name=order]').inputValue(),'1');
 await p.getByRole('button',{name:'月内順序を1増やす',exact:true}).click();check(await p.locator('[name=order]').inputValue(),'2');
 await p.fill('#photo-search','べ');check(await p.locator('[name=order]').inputValue(),'2');
 await candidate(p,'obs-4').hover();check(await p.locator('[name=order]').inputValue(),'2');
 await select(p,'obs-2');check(await p.locator('[name=order]').inputValue(),'2');
 d.fail({error:'order must be unique within a year and month',message:'入力を確認してください',field_errors:{order:'2026年10月に順序「2」の写真が登録されています'}});
 await p.click('#dialog-save');await p.waitForFunction(()=>document.querySelector('#dialog-save').textContent==='変更予定に追加');
 check(await p.locator('#editor').isVisible(),true);check(await p.locator('[name=comment]').inputValue(),'保存するコメント');check(await p.locator('[name=observation_id]').inputValue(),'obs-2');
 assert.match(await p.locator('#order-error').innerText(),/順序「2」/);assertions++;
 check(await p.locator('[name=order]').isEnabled(),true);
 check(await p.evaluate(()=>document.activeElement?.id),'best-order');
 const geometry=await p.locator('#order-error').evaluate(e=>{const label=e.previousElementSibling.getBoundingClientRect(),err=e.getBoundingClientRect();return {sameLine:Math.abs(label.top-err.top)<6,right:err.left>label.right,color:getComputedStyle(e).color}});
 check(geometry.sameLine,true);check(geometry.right,true);check(geometry.color,'rgb(180, 35, 24)');
 if(out){fs.mkdirSync(out,{recursive:true});await p.screenshot({path:path.join(out,'desktop-order-error.png')});}
 // Clear on field correction. Network errors retain values and allow retry.
 await p.focus('[name=order]');await p.keyboard.press('ArrowUp');await p.keyboard.press('ArrowDown');check(await p.locator('#order-error').innerText(),'');
 d.fail('network');await p.click('#dialog-save');await p.waitForFunction(()=>document.querySelector('#dialog-save').textContent==='変更予定に追加');
 check(await p.locator('#editor').isVisible(),true);assert.match(await p.locator('#best-modal-error').innerText(),/通信/);assertions++;check(await p.locator('[name=comment]').inputValue(),'保存するコメント');
 const before=d.writes.length;
 await p.locator('#dialog-save').evaluate(e=>{e.click();e.click()});await p.waitForFunction(()=>!document.querySelector('#editor').open);
 check(d.writes.length,before+1);check(d.writes.at(-1).body.entry.observation_id,'obs-2');check(d.writes.at(-1).body.entry.order,2);await p.waitForFunction(()=>document.querySelector('#message').textContent==='変更予定に追加しました');check(await p.locator('#message').innerText(),'変更予定に追加しました');
 // A fourth slot is available; duplicate photos and unknown dates still block saves.
 await open(p);await p.fill('#photo-search','べ');await select(p,'obs-4');check(await p.locator('[name=order]').inputValue(),'4');check(await p.locator('#dialog-save').isEnabled(),true);check(await p.locator('#order-error').innerText(),'');
 await select(p,'obs-6');await p.locator('.photo-chosen').scrollIntoViewIfNeeded();await p.waitForSelector('.photo-chosen .image-failure');check(await p.locator('#dialog-save').isDisabled(),true);assert.match(await p.locator('#observation_id-error').innerText(),/撮影日/);assertions++;
 await select(p,'obs-1');assert.match(await p.locator('#observation_id-error').innerText(),/すでにBest Shot/);assertions++;
 await p.fill('#photo-search','no matches');assert.match(await p.locator('.photo-results').innerText(),/一致する写真がありません/);assertions++;
 await p.fill('#photo-search','');check(await p.locator('.photo-option').count(),24);
 await p.getByRole('button',{name:'さらに24件表示'}).click();check(await p.locator('.photo-option').count(),48);
 await close(p);
 // Editing the existing selection excludes self and preserves optional fields + annual mapping.
 await p.locator('#best-list .item').first().getByRole('button',{name:'編集・写真差し替え'}).click();
 check(await p.locator('[name=observation_id]').inputValue(),'obs-1');check(await p.locator('[name=order]').inputValue(),'1');check(await p.locator('#order-error').innerText(),'');
 await p.focus('[name=order]');await p.keyboard.press('Enter');await p.waitForFunction(()=>!document.querySelector('#editor').open);check(d.writes.at(-1).body.changes,{});check(d.app.best_shots.annual_best,{'2026':'best-1'});
 await p.locator('#best-list .item').nth(1).getByRole('button',{name:'編集・写真差し替え'}).click();
 await p.click('#dialog-save');await p.waitForFunction(()=>!document.querySelector('#editor').open);check(d.writes.at(-1).body.changes,{});check('location' in d.app.best_shots.entries[1],false);check('annual_comment' in d.app.best_shots.entries[1],false);
 await p.locator('#best-list .item').nth(1).getByRole('button',{name:'編集・写真差し替え'}).click();await p.fill('#photo-search','べにて');await select(p,'obs-5');await p.click('#dialog-save');await p.waitForFunction(()=>!document.querySelector('#editor').open);check(d.writes.at(-1).body.changes,{observation_id:'obs-5',order:1});
 check(d.issues,[]);if(!process.env.CHROMIUM_SINGLE_PROCESS)await d.context.close();
 const t=await setup({viewport:{width:390,height:844},hasTouch:true,isMobile:true}),mobile=t.page;
 await open(mobile);await mobile.fill('#photo-search','べにて');
 await candidate(mobile,'obs-2').getByRole('button',{name:'拡大して確認',exact:true}).tap();check(await mobile.locator('[name=observation_id]').inputValue(),'');check(t.writes.length,0);check(await mobile.locator('.photo-preview').isVisible(),true);
 if(out)await mobile.screenshot({path:path.join(out,'mobile-preview.png')});
 await mobile.locator('.photo-preview').getByRole('button',{name:'拡大確認を閉じる'}).tap();await candidate(mobile,'obs-2').getByRole('button',{name:'この写真を選択',exact:true}).tap();check(await mobile.locator('[name=observation_id]').inputValue(),'obs-2');check(await mobile.locator('[name=order]').inputValue(),'2');
 await mobile.getByRole('button',{name:'月内順序を1減らす',exact:true}).tap();check(await mobile.locator('#dialog-save').isDisabled(),true);
 const bounds=await mobile.locator('#editor').evaluate(e=>({fits:e.scrollWidth<=e.clientWidth,width:e.getBoundingClientRect().width}));check(bounds.fits,true);assert.ok(bounds.width<=390);assertions++;
 if(out)await mobile.screenshot({path:path.join(out,'mobile-order-error.png')});
 await mobile.fill('[name=order]','30');await mobile.fill('[name=comment]','スマホから順序30で保存');check(await mobile.locator('#dialog-save').isEnabled(),true);
 if(out)await mobile.screenshot({path:path.join(out,'mobile-order-30.png')});
 await mobile.locator('#dialog-save').tap();await mobile.waitForFunction(()=>!document.querySelector('#editor').open);check(t.writes.at(-1).body.entry.order,30);check(t.app.best_shots.annual_best,{'2026':'best-1'});
 check(t.issues,[]);if(!process.env.CHROMIUM_SINGLE_PROCESS)await t.context.close();
 // Each month size exercises add, editable high order, a hole, annual, replacement/month move and delete.
 for(const width of [1280,390]){
  const x=await setup({viewport:{width,height:1000},hasTouch:width===390,isMobile:width===390}),q=x.page;
  for(const count of [1,3,4,10,30,35]){
   x.app.best_shots.entries=Array.from({length:count-1},(_,i)=>({selection_id:'fixture-'+i,observation_id:'bulk-'+i,comment:'保存済み '+i,order:i+1,annual_comment:'年間メモ',location:'静岡'}));x.app.best_shots.annual_best={};x.app.counts.best_shots=count-1;
   await q.reload();await q.click('[data-page=best]');await open(q);await q.fill('#photo-search','キノコ写真 '+(count-1));await select(q,'bulk-'+(count-1));check(await q.inputValue('[name=order]'),String(count));
   await q.fill('[name=comment]','月 '+count+' 枚のテスト');
   if(out&&count===30){await q.locator('.order-field').scrollIntoViewIfNeeded();await q.screenshot({path:path.join(out,`${width}-month-30-editor.png`)});}
   await q.click('#dialog-save');await q.waitForFunction(()=>!document.querySelector('#editor').open);check(x.app.best_shots.entries.length,count);const sid=x.writes.at(-1).body.entry.selection_id;
   const item=()=>q.locator('#best-list .item').filter({hasText:'selection: '+sid});
   await item().getByRole('button',{name:'年間ベスト',exact:true}).click();await q.click('#confirm-ok');await q.waitForFunction(()=>!document.querySelector('#confirm').open);check(x.app.best_shots.annual_best,{'2024':sid});
   if(count>=4){
    await q.locator('#best-list .item').filter({has:q.getByText('selection: fixture-1',{exact:true})}).getByRole('button',{name:'削除',exact:true}).click();await q.click('#confirm-ok');await q.waitForFunction(()=>!document.querySelector('#confirm').open);
    await open(q);await q.fill('#photo-search','キノコ写真 '+count);await select(q,'bulk-'+count);check(await q.inputValue('[name=order]'),'2');await q.fill('[name=comment]','空き番号2を再利用');await q.click('#dialog-save');await q.waitForFunction(()=>!document.querySelector('#editor').open);check(x.app.best_shots.entries.length,count);
   }
   await item().getByRole('button',{name:'編集・写真差し替え',exact:true}).click();await q.fill('[name=order]',String(count+10));await q.click('#dialog-save');await q.waitForFunction(()=>!document.querySelector('#editor').open);check(x.app.best_shots.entries.find(e=>e.selection_id===sid).order,count+10);
   if(count>1){
    await open(q);await q.fill('#photo-search','キノコ写真 0');await select(q,'bulk-0');check(await q.locator('#dialog-save').isDisabled(),true);assert.match(await q.locator('#observation_id-error').innerText(),/すでにBest Shot/);assertions++;await close(q);
   }
   await item().getByRole('button',{name:'編集・写真差し替え',exact:true}).click();await q.fill('#photo-search','キノコ写真 別月');await select(q,'other-month');check(await q.inputValue('[name=order]'),'1');await q.click('#dialog-save');await q.waitForFunction(()=>!document.querySelector('#editor').open);
   check(x.app.best_shots.entries.find(e=>e.selection_id===sid).observation_id,'other-month');check(x.app.best_shots.entries.find(e=>e.selection_id===sid).comment,'月 '+count+' 枚のテスト');check(x.app.best_shots.annual_best,{'2024':sid});
   await item().getByRole('button',{name:'削除',exact:true}).click();await q.click('#confirm-ok');await q.waitForFunction(()=>!document.querySelector('#confirm').open);check(x.app.best_shots.entries.some(e=>e.selection_id===sid),false);check(x.app.best_shots.annual_best,{});
  }
  check(x.issues,[]);await x.context.close();
 }
 await browser.close();
 console.log(`Best Shot real Chromium browser: ${assertions} assertions passed (desktop mouse/keyboard, IME event simulation, touch emulation; isolated API/image fixtures)`);
})().catch(e=>{console.error(e);process.exit(1)});
