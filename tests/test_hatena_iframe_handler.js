const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync('hatena/hatena-footer-iframe-handler-candidate-2026-10-09.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
function fixture() {
  const handlers={}, loads={}, writes=[], posts=[], scrolls=[], timers=[];
  const win={scrollY:350,innerHeight:900,addEventListener:(t,f)=>handlers[t]=f,scrollTo:v=>{scrolls.push(v);win.scrollY=v.top;}};
  const wrapper={style:{minHeight:'',overflowAnchor:''},getBoundingClientRect:()=>({top:300-win.scrollY})};
  const iframe={src:'https://charchan123.github.io/hatena-photo-gallery/new-top.html',closest:()=>wrapper,parentElement:wrapper,
    contentWindow:{postMessage:(...v)=>posts.push(v)},addEventListener:(t,f)=>loads[t]=f,getBoundingClientRect:()=>({top:300-win.scrollY}),
    style:new Proxy({}, {set:(o,k,v)=>(writes.push([k,v]),o[k]=v,true)})};
  Object.defineProperty(iframe,'offsetHeight',{get(){throw Error('forced reflow');}});
  const doc={getElementById:()=>iframe,fullscreenElement:null,exitFullscreen:()=>{doc.exits=(doc.exits||0)+1;return Promise.resolve();}};
  vm.runInNewContext(code,{window:win,document:doc,location:{href:'https://example.test/new-top'},URL,getComputedStyle:()=>({minHeight:'0px'}),setTimeout:(f,d)=>timers.push([f,d])});
  const message=(data,extra={})=>handlers.message({data,source:iframe.contentWindow,origin:'https://charchan123.github.io',...extra});
  return {handlers,loads,writes,posts,scrolls,timers,win,wrapper,iframe,doc,message};
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

test('authenticated intent ACK is required for load-time navigation scroll and short-page reclaim',()=>{
 const f=fixture();f.loads.load();assert.equal(f.scrolls.length,0,'initial load never scrolls');
 f.win.scrollY=5850;f.message({type:'setHeight',height:1797});assert.equal(f.wrapper.style.minHeight,'6450px');
 const intent={type:'navigationIntent',id:'nav-1',destination:'/hatena-photo-gallery/index.html'};
 for(const extra of [{source:null},{source:{}},{origin:'https://evil.github.io'}])f.message(intent,extra);
 assert.equal(f.posts.filter(x=>x[0].type==='navigationIntentAck').length,0);
 for(const destination of ['https://evil.test/index.html','/other/index.html','/hatena-photo-gallery/image.jpg'])f.message({...intent,destination});
 assert.equal(f.posts.filter(x=>x[0].type==='navigationIntentAck').length,0);
 f.message(intent);assert.equal(f.win.scrollY,5850,'intent alone does not scroll');assert.equal(f.posts.at(-1)[0].type,'navigationIntentAck');
 f.loads.load();assert.equal(f.win.scrollY,280);assert.equal(f.wrapper.style.minHeight,'');
 f.message({type:'setHeight',height:1797});assert.equal(f.iframe.style.height,'1797px');assert.equal(f.wrapper.style.minHeight,'');assert.equal(f.scrolls.length,1);
 f.loads.load();assert.equal(f.scrolls.length,1,'consumed intent cannot scroll later loads');
});
test('cancelled intent and ordinary height/resize do not authorize navigation scroll',()=>{
 const f=fixture();f.message({type:'navigationIntent',id:'cancel',destination:'/hatena-photo-gallery/index.html'});
 f.message({type:'navigationIntentCancel',id:'cancel'});f.loads.load();assert.equal(f.scrolls.length,0);
 f.message({type:'setHeight',height:1000});f.handlers.resize();assert.equal(f.scrolls.length,0);
});
