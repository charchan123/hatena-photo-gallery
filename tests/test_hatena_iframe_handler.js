const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync('hatena/hatena-footer-iframe-handler-candidate-2026-10-09.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
function fixture(mode = 'window') {
  const handlers={}, loads={}, writes=[], posts=[], scrolls=[], timers=[], trace=[];
  const win={scrollY:mode === 'body' ? 0 : 350,innerHeight:mode === 'body' ? 897 : 900,addEventListener:(t,f)=>handlers[t]=f,removeEventListener:t=>delete handlers[t],scrollTo:v=>{scrolls.push(v);win.scrollY=v.top;trace.push('scroll-complete');}};
  const root={scrollTop:0,clientHeight:897,scrollHeight:mode === 'body' ? 897 : 7000,overflowY:mode === 'body' ? 'hidden' : 'visible'};
  const bodyHandlers={};
  const body={scrollTop:mode === 'body' ? 4000 : 0,clientTop:0,clientHeight:841,scrollHeight:4841,overflowY:mode === 'body' ? 'auto' : 'visible',
    addEventListener:(t,f)=>bodyHandlers[t]=f,removeEventListener:t=>delete bodyHandlers[t],
    getBoundingClientRect:()=>({top:56}),scrollTo:v=>{scrolls.push({...v,host:'body'});body.scrollTop=v.top;trace.push('scroll-complete');}};
  const top=()=>mode === 'body' ? 56 + 292-body.scrollTop : 300-win.scrollY;
  const wrapper={style:{minHeight:'',overflowAnchor:''},getBoundingClientRect:()=>({top:top()})};
  const iframe={src:'https://charchan123.github.io/hatena-photo-gallery/new-top.html',closest:()=>wrapper,parentElement:wrapper,
    contentWindow:{location:{origin:'https://charchan123.github.io'},postMessage:(...v)=>{posts.push(v);trace.push(v[0].type);}},addEventListener:(t,f)=>loads[t]=f,getBoundingClientRect:()=>({top:top(),height:4199}),
    style:new Proxy({}, {set:(o,k,v)=>(writes.push([k,v]),o[k]=v,true)})};
  Object.defineProperty(iframe,'offsetHeight',{get(){throw Error('forced reflow');}});
  const doc={documentElement:root,scrollingElement:root,body,getElementById:()=>iframe,fullscreenElement:null,exitFullscreen:()=>{doc.exits=(doc.exits||0)+1;return Promise.resolve();}};
  vm.runInNewContext(code,{window:win,document:doc,location:{href:'https://example.test/new-top'},URL,getComputedStyle:e=>({minHeight:'0px',overflowY:e.overflowY}),setTimeout:(f,d)=>timers.push([f,d])});
  const message=(data,extra={})=>handlers.message({data,source:iframe.contentWindow,origin:'https://charchan123.github.io',...extra});
  return {handlers,loads,writes,posts,scrolls,timers,win,wrapper,iframe,doc,message,trace,body,root,bodyHandlers};
}
test('height is direct, finite and authenticated; duplicates do not write',()=>{
 const f=fixture();
 for(const height of [-1,Infinity,NaN,'600',null]) f.message({type:'setHeight',height});
 f.message({type:'setHeight',height:800},{origin:'https://evil.github.io'});
 f.message({type:'setHeight',height:800},{source:{}});
 assert.equal(f.writes.length,0);
 f.message({type:'setHeight',height:800.2});f.message({type:'setHeight',height:801});
 assert.deepEqual(f.writes.filter(x=>x[0]==='height'),[['height','801px']]);assert.equal(f.scrolls.length,0);
});
test('bottom collapse reserves outer space and reclaims on upward scroll',()=>{
 const f=fixture();f.win.scrollY=1600;f.message({type:'setHeight',height:700});
 assert.equal(f.wrapper.style.minHeight,'2200px');assert.equal(f.iframe.style.height,'700px');assert.equal(f.win.scrollY,1600);
 f.handlers.scroll();f.win.scrollY=100;f.handlers.scroll();assert.equal(f.wrapper.style.minHeight,'');assert.equal(f.scrolls.length,0);
});
test('navigation, lightbox close and requestHeight remain source-bound',()=>{
 const f=fixture();
 f.message({type:'scrollToTitle'},{source:{}});
 f.message({type:'scrollToTitle'},{source:null});
 f.message({type:'scrollToTitle'},{origin:'https://evil.github.io'});
 assert.equal(f.scrolls.length,0);
 f.message({type:'scrollToTitle'});assert.equal(f.scrolls[0].top,280);assert.equal(f.scrolls[0].behavior,'instant');assert.equal(f.win.scrollY,280);
 f.doc.fullscreenElement={};f.message({type:'lgClosed'});assert.equal(f.doc.exits,1);
 f.loads.load();assert.equal(f.scrolls.length,1,'load does not create a scroll request');
 f.message({type:'setHeight',height:700});assert.equal(f.win.scrollY,280);
 f.message({type:'scrollToTitle'});assert.equal(f.win.scrollY,280,'destination replay settles at the same title');
 for(const [fn] of f.timers) fn();
 assert.ok(f.posts.length>=8);assert.ok(f.posts.every(x=>x[0].type==='requestHeight'&&x[1]==='https://charchan123.github.io'));
});

test('authenticated intent scrolls before ACK; load only reclaims short-page space',()=>{
 const f=fixture();f.loads.load();assert.equal(f.scrolls.length,0,'initial load never scrolls');
 f.win.scrollY=5850;f.message({type:'setHeight',height:1797});assert.equal(f.wrapper.style.minHeight,'6450px');
 const intent={type:'navigationIntent',id:'nav-1',destination:'/hatena-photo-gallery/index.html'};
 for(const extra of [{source:null},{source:{}},{origin:'https://evil.github.io'}])f.message(intent,extra);
 assert.equal(f.posts.filter(x=>x[0].type==='navigationIntentAck').length,0);
 for(const destination of ['https://evil.test/index.html','/other/index.html','/hatena-photo-gallery/image.jpg'])f.message({...intent,destination});
 assert.equal(f.posts.filter(x=>x[0].type==='navigationIntentAck').length,0);
 assert.equal(f.scrolls.length,0,'invalid source/origin/destination cannot scroll');
 for(const id of ['',null,123,'x'.repeat(81)])f.message({...intent,id});
 assert.equal(f.scrolls.length,0,'invalid ID cannot scroll');
 f.trace.length=0;f.message(intent);assert.equal(f.win.scrollY,280,'intent settles immediately');
 assert.deepEqual(f.trace,['scroll-complete','navigationIntentAck'],'ACK follows completed scroll');
 assert.equal(f.scrolls.length,1);

 f.loads.load();assert.equal(f.win.scrollY,280);assert.equal(f.wrapper.style.minHeight,'');assert.equal(f.scrolls.length,1,'load cannot scroll a second time');
 f.message({type:'setHeight',height:1797});assert.equal(f.iframe.style.height,'1797px');assert.equal(f.wrapper.style.minHeight,'');assert.equal(f.scrolls.length,1);
 f.loads.load();assert.equal(f.scrolls.length,1,'consumed intent cannot scroll later loads');
});
test('cancel clears pending intent without rollback or any additional scroll',()=>{
 const f=fixture();f.message({type:'navigationIntent',id:'cancel',destination:'/hatena-photo-gallery/index.html'});
 f.message({type:'navigationIntentCancel',id:'cancel'});f.loads.load();assert.equal(f.scrolls.length,1);
 f.message({type:'setHeight',height:1000});f.handlers.resize();assert.equal(f.scrolls.length,1);assert.equal(f.win.scrollY,280);
});

test('repeated intent IDs ACK again but never scroll twice before load',()=>{
 const f=fixture();const intent={type:'navigationIntent',id:'same',destination:'/hatena-photo-gallery/index.html'};
 f.message(intent);f.message(intent);assert.equal(f.scrolls.length,1);
 assert.equal(f.posts.filter(x=>x[0].type==='navigationIntentAck').length,2);
 f.loads.load();f.loads.load();assert.equal(f.scrolls.length,1);
});

for (const mode of ['window', 'body']) {
 test(`${mode}: no eager post to initial parent-origin document; initial load never scrolls`,()=>{
  const f=fixture(mode);assert.equal(f.posts.length,0);
  f.iframe.contentWindow.location.origin='https://example.test';f.loads.load();assert.equal(f.posts.length,0);
  f.iframe.contentWindow.location.origin='https://charchan123.github.io';f.loads.load();
  assert.equal(f.scrolls.length,0);assert.equal(f.posts[0][0].type,'requestHeight');
 });
 test(`${mode}: source/origin/path/ID validation precedes any scroll`,()=>{
  const f=fixture(mode);const intent={type:'navigationIntent',id:'secure',destination:'/hatena-photo-gallery/index.html'};
  for(const extra of [{source:null},{source:{}},{origin:'https://evil.test'}])f.message(intent,extra);
  for(const destination of ['https://evil.test/index.html','/other/index.html','/hatena-photo-gallery/image.jpg'])f.message({...intent,destination});
  for(const id of ['',null,123,'x'.repeat(81)])f.message({...intent,id});
  assert.equal(f.scrolls.length,0);assert.equal(f.posts.length,0);
 });
 test(`${mode}: in-place heights, resize and ordinary load never scroll`,()=>{
  const f=fixture(mode),before=mode==='body'?f.body.scrollTop:f.win.scrollY;
  for(const height of [5000,4700,5200,4800])f.message({type:'setHeight',height});
  f.handlers.resize();f.loads.load();f.message({type:'setHeight',height:4800});
  assert.equal(f.scrolls.length,0);assert.equal(mode==='body'?f.body.scrollTop:f.win.scrollY,before);
 });
}
test('measured Hatena BODY coordinates: 4000 → 272 before ACK, window remains 0',()=>{
 const f=fixture('body');assert.equal(f.iframe.getBoundingClientRect().top,-3652);
 f.message({type:'navigationIntent',id:'body-nav',destination:'/hatena-photo-gallery/index.html'});
 assert.equal(f.body.scrollTop,272);assert.equal(f.win.scrollY,0);
 assert.deepEqual(f.trace,['scroll-complete','navigationIntentAck']);
 assert.equal(f.scrolls.length,1);assert.equal(f.scrolls[0].host,'body');assert.equal(f.scrolls[0].behavior,'instant');
 f.loads.load();f.message({type:'setHeight',height:700});
 assert.equal(f.scrolls.length,1);assert.equal(f.body.scrollTop,272);assert.equal(f.wrapper.style.minHeight,'821px');
});
test('BODY bottom collapse uses body viewport and reclaims on body upward scroll',()=>{
 const f=fixture('body');f.message({type:'setHeight',height:700});
 assert.equal(f.wrapper.style.minHeight,'4549px');assert.equal(f.iframe.style.height,'700px');
 f.bodyHandlers.scroll();f.body.scrollTop=100;f.bodyHandlers.scroll();assert.equal(f.wrapper.style.minHeight,'');
 assert.equal(f.body.scrollTop,100);assert.equal(f.scrolls.length,0);assert.equal(f.handlers.scroll,undefined);
});
test('BODY mode survives top/short content and transfers listeners on layout change',()=>{
 const f=fixture('body');f.body.scrollTop=0;f.body.scrollHeight=f.body.clientHeight;
 f.message({type:'navigationIntent',id:'top',destination:'/hatena-photo-gallery/index.html'});
 assert.equal(f.scrolls[0].host,'body');
 f.body.overflowY='visible';f.root.overflowY='visible';f.root.scrollHeight=7000;f.handlers.resize();
 assert.equal(f.bodyHandlers.scroll,undefined);assert.equal(typeof f.handlers.scroll,'function');
 f.body.overflowY='auto';f.root.overflowY='hidden';f.root.scrollHeight=897;f.handlers.resize();
 assert.equal(f.handlers.scroll,undefined);assert.equal(typeof f.bodyHandlers.scroll,'function');
 assert.equal(f.scrolls.length,1,'listener/resize changes do not scroll');
});
test('BODY border is excluded from content coordinates; resize uses clientHeight',()=>{
 const f=fixture('body');f.body.clientTop=2;f.body.clientHeight=700;
 f.message({type:'setHeight',height:700});assert.equal(f.wrapper.style.minHeight,'4410px');
 f.body.clientHeight=600;f.handlers.resize();assert.equal(f.wrapper.style.minHeight,'4310px');
 f.message({type:'navigationIntent',id:'border',destination:'/hatena-photo-gallery/index.html'});
 assert.equal(f.body.scrollTop,270);assert.equal(f.win.scrollY,0);
});

test('BODY legacy navigation, lgClosed and bounded requestHeight retain authentication',()=>{
 const f=fixture('body');
 f.message({type:'scrollToTitle'},{source:null});f.message({type:'scrollToTitle'},{origin:'https://evil.test'});
 assert.equal(f.scrolls.length,0);f.message({type:'scrollToTitle'});
 assert.equal(f.body.scrollTop,272);assert.equal(f.win.scrollY,0);
 f.doc.fullscreenElement={};f.message({type:'lgClosed'},{origin:'https://evil.test'});assert.equal(f.doc.exits,undefined);
 f.message({type:'lgClosed'});assert.equal(f.doc.exits,1);
 for(const [fn] of f.timers)fn();
 assert.ok(f.posts.length>=4);assert.ok(f.posts.every(p=>p[0].type==='requestHeight'&&p[1]==='https://charchan123.github.io'));
 assert.equal(f.scrolls.length,1);
});
