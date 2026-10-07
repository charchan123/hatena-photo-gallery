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

test('ten visible particles retain the six green / four bright purple balance',()=>{
  assert.equal(PRESETS.length,10);
  const green=PRESETS.filter(p=>p.color==='#C7ED55');
  const purple=PRESETS.filter(p=>p.color==='#C084FC');
  assert.equal(green.length,6);assert.equal(purple.length,4);
  for(const p of green){
    assert.ok(p.size>=3&&p.size<=7&&p.opacity>=.55&&p.opacity<=.75);
    assert.ok(p.blur>=0&&p.blur<=1.5);
  }
  for(const p of purple){
    assert.ok(p.size>=4&&p.size<=8&&p.opacity>=.65&&p.opacity<=.85);
    assert.ok(p.blur>=0&&p.blur<=1);
  }
  assert.ok(Math.min(...purple.map(p=>p.opacity))>=Math.max(...green.map(p=>p.opacity)));
  assert.ok(new Set(PRESETS.map(p=>p.size)).size>3);
  assert.ok(new Set(PRESETS.map(p=>p.duration)).size>4);
  for(const p of PRESETS){
    assert.ok(p.duration>=1800&&p.duration<=2700&&p.delay>=0&&p.delay<=300);
    assert.ok(p.duration+p.delay<2900, 'finish before the unchanged cleanup fallback');
    assert.ok(p.y>=.4&&p.y<=.7&&p.x>=.4&&p.x<=.6);
  }
});

test('radial destinations include diagonals, lateral drift and a gentle downward particle',()=>{
  const directions={upperLeft:0,upperRight:0,left:0,right:0,up:0,down:0};
  for(const p of PRESETS){
    assert.ok(Math.hypot(p.dx,p.dy)>=35&&Math.hypot(p.dx,p.dy)<=80);
    if(p.dy>0)directions.down++;
    else if(Math.abs(p.dx)<=10)directions.up++;
    else if(p.dy<=-35)directions[p.dx<0?'upperLeft':'upperRight']++;
    else directions[p.dx<0?'left':'right']++;
    // The bent path stays bounded too, not just its endpoint.
    assert.ok(Math.hypot(p.dx*.85+p.sway,p.dy*.85)<=80);
  }
  assert.deepEqual(directions,{upperLeft:2,upperRight:2,left:2,right:2,up:1,down:1});
  assert.ok(PRESETS.filter(p=>Math.abs(p.dy)<=20&&Math.abs(p.dx)>=30).length>=3);
});

test('initial kick follows each destination and slows into a bent drift',()=>{
  const e=environment();setup(e.doc,e.win);e.fire('pointerenter',e.card());
  const particles=e.body.children[0].children;
  PRESETS.forEach((p,i)=>{
    const style=particles[i].style, value=k=>parseFloat(style[k]);
    const x=value('--spore-kick-x'),y=value('--spore-kick-y');
    assert.ok(Math.hypot(x,y)>=10&&Math.hypot(x,y)<=20);
    assert.ok(Math.abs(x*p.dy-y*p.dx)<1e-9, 'kick follows the signed radial vector');
    assert.equal(Math.sign(x),Math.sign(p.dx));assert.equal(Math.sign(y),Math.sign(p.dy));
    assert.ok(p.duration*.1>=150&&p.duration*.1<=300);
    const midX=value('--spore-mid-x'),midY=value('--spore-mid-y');
    const initialSpeed=Math.hypot(x,y)/(p.duration*.1);
    const driftSpeed=Math.hypot(midX-x,midY-y)/(p.duration*.4);
    assert.ok(initialSpeed>driftSpeed*1.5);
    const lateX=value('--spore-sway-x'),lateY=value('--spore-late-y');
    assert.ok(Math.abs(lateX*p.dy-lateY*p.dx)>1, 'late drift bends off the launch line');
    assert.equal(value('--spore-end-x'),p.dx);assert.equal(value('--spore-end-y'),p.dy);
  });
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
