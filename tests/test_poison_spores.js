const assert = require('node:assert/strict');
const {test} = require('node:test');
const {PRESETS, burstBounds, setup} = require('../assets/poison-spores.js');

function environment() {
  const handlers = {}, windowHandlers = {}, timers = new Map();
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
    addEventListener:(type,fn)=>{handlers[type]=fn;}};
  const reduced={matches:false,addEventListener:(type,fn)=>{reduced.change=fn;}};
  const hover={matches:true,addEventListener:(type,fn)=>{hover.change=fn;}};
  const win={innerHeight:900,matchMedia:q=>q.includes('reduced')?reduced:hover,
    MutationObserver:class {constructor(fn){mutation=fn;}observe(){}disconnect(){}},
    setTimeout:fn=>{timers.set(++timerId,fn);return timerId;}, clearTimeout:id=>timers.delete(id),
    addEventListener:(type,fn)=>{windowHandlers[type]=fn;}};
  function card(poison=true) {
    const c=new Element();c.visible=true;c.focusVisible=true;c.poison=poison;
    c.matches=selector=>selector===':focus-visible'?c.focusVisible:c.poison;
    c.getClientRects=()=>c.visible?[{}]:[];
    c.querySelector=()=>({getBoundingClientRect:()=>({left:100,top:200,right:300,bottom:330,width:200,height:130})});
    return c;
  }
  return {doc,win,body,handlers,windowHandlers,timers,reduced,hover,card,mutate:()=>mutation(),
    fire:(type,target,pointerType='mouse')=>handlers[type]({target,pointerType})};
}

test('presets have bounded two-color nonuniform bursts',()=>{
  assert.equal(PRESETS.length,10);
  assert.equal(PRESETS.filter(p=>p.color==='#B8E34A').length,6);
  assert.equal(PRESETS.filter(p=>p.color==='#9A6BC9').length,4);
  for(const p of PRESETS){
    assert.ok(p.size>=3&&p.size<=8&&p.opacity>=.25&&p.opacity<=.65);
    assert.ok(p.duration>=1600&&p.duration<=2600&&p.delay>=0&&p.delay<=300);
    assert.ok(p.rise>=40&&p.rise<=90&&p.blur>=0&&p.blur<=2);
    assert.ok(p.y>=.4&&p.y<=.7&&p.x>=.4&&p.x<=.6);
  }
  assert.ok(PRESETS.some(p=>p.dx<0)&&PRESETS.some(p=>p.dx>0));
  assert.ok(new Set(PRESETS.map(p=>p.size)).size>3);
});

test('bounds escape the image by at most 24px, avoid names and viewport overflow',()=>{
  assert.deepEqual(burstBounds({left:100,top:100,right:300,bottom:230},400,600),{left:76,top:76,width:248,height:154});
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
  for(const p of [...layer.children])p.events.animationend();
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
