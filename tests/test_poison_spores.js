const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const css = fs.readFileSync(path.join(__dirname, '../assets/gallery.css'), 'utf8');
const {PRESETS, OVERHANG, CLEANUP_MS, TOUCH_DELAY_MS, trajectory, motionPath, burstBounds, setup} = require('../assets/poison-spores.js');

function environment() {
  const handlers = {}, windowHandlers = {}, timers = new Map(), delays = new Map();
  const add = (store,type,fn) => { const prev=store[type]; store[type]=event=>{if(prev)prev(event);fn(event);}; };
  let timerId = 0, mutation;
  class Element {
    constructor() { this.children=[]; this.style={setProperty:(k,v)=>{this.style[k]=v;}}; this.events={}; this.isConnected=true; }
    setAttribute(k,v) { this[k]=v; }
    appendChild(child) { this.children.push(child); child.parent=this; }
    remove() { if(this.parent) this.parent.children=this.parent.children.filter(x=>x!==this); this.isConnected=false; }
    addEventListener(type,fn) { this.events[type]=fn; }
  }
  const body=new Element(); body.matches=()=>true;
  const doc={body, hidden:false, documentElement:{clientWidth:1440}, createElement:()=>new Element(),
    addEventListener:(type,fn)=>add(handlers,type,fn)};
  const reduced={matches:false,addEventListener:(type,fn)=>{reduced.change=fn;}};
  const hover={matches:true,addEventListener:(type,fn)=>{hover.change=fn;}};
  const coarse={matches:false};
  const win={innerHeight:900,matchMedia:q=>q.includes('reduced')?reduced:q==='(pointer: coarse)'?coarse:hover,
    MutationObserver:class {constructor(fn){mutation=fn;}observe(){}disconnect(){}},
    setTimeout:(fn,ms)=>{timers.set(++timerId,fn);delays.set(timerId,ms);return timerId;}, clearTimeout:id=>timers.delete(id),
    addEventListener:(type,fn)=>add(windowHandlers,type,fn)};
  function card(poison=true) {
    const c=new Element();c.visible=true;c.focusVisible=true;c.poison=poison;
    c.href='detail.html';c.getAttribute=k=>c[k]||null;c.hasAttribute=k=>!!c[k];c.closest=selector=>selector.includes('card-fav')?null:c.poison?c:null;
    c.navigations=0;c.click=()=>{const e=clickEvent(c,{detail:0,pointerType:''});handlers.click(e);if(!e.defaultPrevented)c.navigations++;};
    c.matches=selector=>selector===':focus-visible'?c.focusVisible:c.poison;
    c.getClientRects=()=>c.visible?[{}]:[];
    c.querySelector=()=>({getBoundingClientRect:()=>({left:100,top:200,right:300,bottom:330,width:200,height:130})});
    return c;
  }
  return {doc,win,body,handlers,windowHandlers,timers,delays,reduced,hover,coarse,card,mutate:()=>mutation(),
    fire:(type,target,pointerType='mouse')=>handlers[type]({target,pointerType})};
}

test('ten bright cores retain the six green / four purple balance and soft edges',()=>{
  assert.equal(PRESETS.length,10);
  const green=PRESETS.filter(p=>p.core==='#D2FF5A'&&p.edge==='#69D600');
  const purple=PRESETS.filter(p=>p.core==='#CFA0FF'&&p.edge==='#7838D1');
  assert.equal(green.length,6);assert.equal(purple.length,4);
  for(const p of green)assert.ok(p.size>=5&&p.size<=9&&p.opacity===.90);
  for(const p of purple)assert.ok(p.size>=6&&p.size<=10&&p.opacity===.95);
  const block=css.match(/\.poison-spore \{([^}]+)\}/)[1];
  assert.match(block,/radial-gradient\(circle, var\(--spore-core\) 0% 25%, var\(--spore-edge\) 55%, transparent 100%\)/);
  assert.doesNotMatch(block,/filter:|box-shadow:/);
  for(const p of PRESETS){
    assert.ok(p.duration>=2400&&p.duration<=3400&&p.delay>=0&&p.delay<=200);
    assert.ok(p.duration+p.delay<CLEANUP_MS);
  }
  assert.ok(new Set(PRESETS.map(p=>p.size)).size>=4);
  assert.ok(new Set(PRESETS.map(p=>p.duration)).size>=4);
});

function point(points,t) {
  const u=1-t;
  return [0,1].map(i=>u*u*u*points[0][i]+3*u*u*t*points[1][i]+3*u*t*t*points[2][i]+t*t*t*points[3][i]);
}
function pathLength(points) {
  let length=0,prev=points[0];
  for(let i=1;i<=1000;i++) { const next=point(points,i/1000);length+=Math.hypot(next[0]-prev[0],next[1]-prev[1]);prev=next; }
  return length;
}

test('single regular Bezier curves spread in six directions with bounded arc lengths',()=>{
  const directions={upperLeft:0,upperRight:0,left:0,right:0,up:0,down:0};
  for(const p of PRESETS){
    if(p.dy>0)directions.down++;
    else if(Math.abs(p.dx)<=10)directions.up++;
    else if(p.dy<=-35)directions[p.dx<0?'upperLeft':'upperRight']++;
    else directions[p.dx<0?'left':'right']++;
    const points=trajectory(p,260,166);
    assert.ok(pathLength(points)>=70&&pathLength(points)<=150);
    const forward=[points[3][0]-points[0][0],points[3][1]-points[0][1]];
    // Positive projection of all derivative control vectors: no cusp, stop or reversal.
    for(let i=0;i<3;i++)assert.ok((points[i+1][0]-points[i][0])*forward[0]+(points[i+1][1]-points[i][1])*forward[1]>0);
    assert.ok(Math.abs((points[1][0]-points[0][0])*forward[1]-(points[1][1]-points[0][1])*forward[0])>1);
    assert.match(motionPath(p,{left:100,top:100,width:260,height:166},{left:20,top:20}),/^path\("M [-\d.]+ [-\d.]+ C [-\d.]+ [-\d.]+, [-\d.]+ [-\d.]+, [-\d.]+ [-\d.]+"\)$/);
  }
  assert.deepEqual(directions,{upperLeft:2,upperRight:2,left:2,right:2,up:1,down:1});
});

test('motion has only endpoints, separate appearance, and continuously decreasing nonzero speed',()=>{
  const motion=css.match(/@keyframes poison-spore-motion \{([\s\S]*?)\n\}/)[1];
  assert.equal((motion.match(/offset-distance:/g)||[]).length,2);
  assert.match(motion,/from \{ offset-distance:0%; \}/);
  assert.match(motion,/to \{ offset-distance:100%; \}/);
  assert.doesNotMatch(motion,/opacity|transform/);
  const appearance=css.match(/@keyframes poison-spore-appearance \{([\s\S]*?)\n\}/)[1];
  assert.doesNotMatch(appearance,/offset-distance|transform/);
  assert.match(appearance,/10%, 65%/);
  assert.match(css,/poison-spore-appearance var\(--spore-duration\) linear/);
  const curve=css.match(/poison-spore-motion var\(--spore-duration\) cubic-bezier\(([^)]+)\)/)[1].split(',').map(Number);
  const [x1,y1,x2,y2]=curve;
  function derivative(a,b,t){return 3*(1-t)**2*a+6*(1-t)*t*(b-a)+3*t*t*(1-b);}
  let previous=Infinity,initial;
  for(let i=0;i<=10000;i++){
    const t=i/10000, speed=derivative(y1,y2,t)/derivative(x1,x2,t);
    if(i===0)initial=speed;
    assert.ok(speed>0&&speed<=previous+1e-10,'no re-acceleration or resting plateau');
    previous=speed;
  }
  assert.ok(initial/previous>5&&previous>.15,'clearly slower but still moving at the end');
});

test('six outward paths reach surrounding space without clipping or touching names',()=>{
  for(const width of [160,200,260,326,400]){
    const height=width*.64;
    let crossed=0;
    for(const p of PRESETS){
      const points=trajectory(p,width,height),[x,y]=points[3];
      const outside=Math.max(-x,x-width,-y,0);
      if(outside>=35)crossed++;
      assert.ok(outside<=60+1e-8);
      for(let i=0;i<=100;i++){
        const [px,py]=point(points,i/100);
        assert.ok(px-p.size/2>-OVERHANG&&px+p.size/2<width+OVERHANG);
        assert.ok(py-p.size/2>-OVERHANG&&py+p.size/2<height);
      }
    }
    assert.ok(crossed>=6);
  }
  assert.equal(OVERHANG,80);
  assert.deepEqual(burstBounds({left:100,top:100,right:300,bottom:230},400,600),{left:20,top:20,width:360,height:210});
  assert.deepEqual(burstBounds({left:5,top:10,right:395,bottom:200},400,600),{left:0,top:0,width:400,height:200});
});

test('one burst per enter, no nonpoison/touch, re-enter and keyboard work',()=>{
  const e=environment();setup(e.doc,e.win);
  assert.equal(e.body.children.length,0);
  e.fire('pointerenter',e.card(false));assert.equal(e.body.children.length,0);
  const c=e.card();e.fire('pointerenter',c,'touch');assert.equal(e.body.children.length,0);
  e.hover.matches=false;e.fire('pointerenter',c);assert.equal(e.body.children.length,0);
  e.hover.matches=true;e.fire('pointerenter',c);
  assert.equal(e.body.children.length,1);assert.equal(e.body.children[0].children.length,10);
  assert.equal(e.body.children[0]['aria-hidden'],'true');
  const layer=e.body.children[0];e.fire('pointerenter',c);e.fire('focusin',c);
  assert.equal(e.body.children[0],layer);
  for(const p of [...layer.children])p.events.animationend({animationName:'poison-spore-appearance'});
  assert.equal(layer.children.length,10,'appearance completion must not remove particles early');
  for(const p of [...layer.children])p.events.animationend({animationName:'poison-spore-motion'});
  assert.equal(e.body.children.length,0);assert.equal(e.timers.size,0);
  e.fire('pointerenter',c);assert.equal(e.body.children.length,0); // Still hovering.
  e.fire('focusout',c);e.fire('pointerleave',c);e.fire('pointerenter',c);
  assert.equal(e.body.children.length,1);
  e.fire('pointerleave',c);e.fire('focusin',c);assert.equal(e.body.children.length,1);
});

test('keyboard supports coarse devices, reduced motion and exclusions fail closed',()=>{
  const e=environment();setup(e.doc,e.win);e.hover.matches=false;
  const c=e.card();c.focusVisible=false;e.fire('focusin',c);assert.equal(e.body.children.length,0);
  c.focusVisible=true;e.fire('focusin',c);assert.equal(e.body.children.length,1);
  e.reduced.matches=true;e.reduced.change();assert.equal(e.body.children.length,0);
  e.fire('focusout',c);e.fire('focusin',c);assert.equal(e.body.children.length,0);
  const other=environment();other.doc.body.matches=()=>false;
  assert.equal(setup(other.doc,other.win),null);assert.deepEqual(other.handlers,{});
});

test('filter/removal, scroll, reduced motion, timer and burst cap clean up',()=>{
  const e=environment();setup(e.doc,e.win);
  const c=e.card();e.fire('pointerenter',c);c.visible=false;e.mutate();assert.equal(e.body.children.length,0);
  const detached=e.card();e.fire('pointerenter',detached);detached.isConnected=false;e.mutate();assert.equal(e.body.children.length,0);
  for(let i=0;i<9;i++)e.fire('pointerenter',e.card());
  assert.equal(e.body.children.length,3);assert.equal(e.timers.size,3);
  e.windowHandlers.scroll();assert.equal(e.body.children.length,0);assert.equal(e.timers.size,0);
  e.fire('pointerenter',e.card());for(const fn of [...e.timers.values()])fn();assert.equal(e.body.children.length,0);
});

function clickEvent(card, extra={}) {
  return {target:card,pointerType:'touch',detail:1,button:0,defaultPrevented:false,
    preventDefault(){this.defaultPrevented=true;},...extra};
}
test('coarse poison tap delays native activation 600ms and double tap stays one burst',()=>{
 const e=environment();e.coarse.matches=true;setup(e.doc,e.win);const c=e.card();
 const first=clickEvent(c);e.handlers.click(first);assert(first.defaultPrevented);
 assert.equal(e.body.children.length,1);assert.equal(e.body.children[0].children.length,10);
 const timers=[...e.timers.keys()];const second=clickEvent(c);e.handlers.click(second);
 assert(second.defaultPrevented);assert.deepEqual([...e.timers.keys()],timers);
 const id=timers.find(id=>e.delays.get(id)===TOUCH_DELAY_MS);assert.equal(TOUCH_DELAY_MS,600);
 assert.equal(c.navigations,0);e.timers.get(id)();assert.equal(c.navigations,1);
});
test('ordinary, reduced, keyboard and modified links keep native immediate behavior',()=>{
 for(const mode of ['nonpoison','reduced','keyboard','mouse','modified','blank','download','fine']){
  const e=environment();e.coarse.matches=mode!=='fine';e.reduced.matches=mode==='reduced';setup(e.doc,e.win);
  const c=e.card(mode!=='nonpoison');if(mode==='blank')c.target='_blank';if(mode==='download')c.download='photo';
  const event=clickEvent(c,{detail:mode==='keyboard'?0:1,pointerType:mode==='mouse'?'mouse':'touch',ctrlKey:mode==='modified'});
  e.handlers.click(event);assert(!event.defaultPrevented,mode);assert.equal(e.body.children.length,0,mode);
 }
});
test('touch cancellation and stale targets cannot trigger deferred navigation',()=>{
 for(const mode of ['pagehide','hidden','removed','changed']){
  const e=environment();e.coarse.matches=true;setup(e.doc,e.win);const c=e.card();e.handlers.click(clickEvent(c));
  if(mode==='pagehide')e.windowHandlers.pagehide();if(mode==='hidden'){e.doc.hidden=true;e.handlers.visibilitychange();}
  if(mode==='removed')c.isConnected=false;if(mode==='changed')c.href='other.html';
  for(const [id,fn]of [...e.timers])if(e.delays.get(id)===600)fn();assert.equal(c.navigations,0,mode);
 }
});

// Color-only follow-up: freeze every preset's geometry, timing and opacity.
test('color adjustment leaves every motion and appearance parameter unchanged',()=>{
  const crypto=require('node:crypto');
  const geometry=PRESETS.map(({core,edge,...rest})=>rest);
  assert.equal(crypto.createHash('sha256').update(JSON.stringify(geometry)).digest('hex'),
    '1037f439d0687a8c8fdaf3b6cf92ae500a21475f74ef1b4e0a7662d3304bb766');
});
