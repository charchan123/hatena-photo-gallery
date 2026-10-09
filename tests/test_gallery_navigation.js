const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('assets/gallery.js','utf8');
function fixture(){
 const values=new Map(),clicks=[],handlers={},events={},timers=new Map(),posts=[];
 const location={origin:'https://gallery.test',href:'https://gallery.test/index.html',pathname:'/index.html'};
 let now=1000,timer=0;
 const storage={getItem:k=>values.has(k)?values.get(k):null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
 const window={parent:{postMessage:(data,origin)=>posts.push({data,origin})},location,sessionStorage:storage,
 addEventListener:(t,f)=>events[t]=f,setTimeout:(f,ms)=>{timers.set(++timer,{f,ms});return timer},clearTimeout:id=>timers.delete(id)};
 const document={referrer:'https://parent.test/new-top',addEventListener:(t,f)=>handlers[t]=f};
 const c={window,location,sessionStorage:storage,URL,Date:{now:()=>now}};vm.createContext(c);
 vm.runInContext(source.slice(0,source.indexOf('document.addEventListener("DOMContentLoaded"'))+'\nthis.remember=rememberIframeNavigation;this.consume=consumeIframeNavigation;this.setup=setupIframeNavigation;',c);
 const link=(href='https://gallery.test/detail.html',target='',download=false)=>({href,isConnected:true,getAttribute:k=>k==='target'?target:null,hasAttribute:k=>k==='download'&&download,
 click(){const event=clickEvent(this);handlers.click(event);if(!event.defaultPrevented)clicks.push(this.href)}});
 const clickEvent=(a,overrides={})=>({target:{closest:()=>a},button:0,defaultPrevented:false,preventDefault(){this.defaultPrevented=true},...overrides});
 const ack=(extra={})=>events.message({source:window.parent,origin:'https://parent.test',data:{type:'navigationIntentAck',id:posts.at(-1).data.id},...extra});
 return {c,window,location,storage,values,link,document,handlers,events,timers,posts,clicks,clickEvent,ack,time:t=>now=t,setup:()=>c.setup(document,window)};
}
test('old-parent destination replay is consumed once and rejects stale/unrelated markers',()=>{
 const f=fixture();f.c.remember(f.link());f.location.pathname='/detail.html';f.time(1500);
 assert.equal(f.c.consume(),true);assert.equal(f.c.consume(),false);assert.equal(f.values.size,0);
 f.location.pathname='/index.html';f.c.remember(f.link());assert.equal(f.c.consume(),false);
 f.time(1000);f.c.remember(f.link());f.location.pathname='/detail.html';f.time(11001);assert.equal(f.c.consume(),false);
 f.time(1000);f.c.remember(f.link());f.time(999);assert.equal(f.c.consume(),false);
});
test('only real same-frame internal HTML links send an intent',()=>{
 const f=fixture();f.setup();
 for(const l of [null,f.link('https://other.test/detail.html'),f.link(undefined,'_top'),f.link(undefined,'_blank'),f.link(undefined,'',true),f.link('https://gallery.test/photo.jpg'),f.link('https://gallery.test/index.html#title')])f.handlers.click(f.clickEvent(l));
 for(const key of ['defaultPrevented','metaKey','ctrlKey','shiftKey','altKey'])f.handlers.click(f.clickEvent(f.link(),{[key]:true}));
 f.handlers.click(f.clickEvent(f.link(),{button:1}));
 assert.equal(f.posts.length,0);assert.equal(f.values.size,0);
 f.window.parent=f.window;f.handlers.click(f.clickEvent(f.link()));assert.equal(f.posts.length,0);
});
test('ACK precedes native navigation, is authenticated and cannot navigate twice',()=>{
 const f=fixture();f.setup();const a=f.link();const e=f.clickEvent(a);f.handlers.click(e);
 assert.equal(e.defaultPrevented,true);assert.equal(f.clicks.length,0);assert.equal(f.posts.length,1);
 assert.equal(f.posts[0].data.type,'navigationIntent');assert.equal(f.posts[0].data.destination,'/detail.html');assert.equal(f.posts[0].origin,'https://parent.test');
 f.ack({source:{}});f.ack({origin:'https://evil.test'});f.ack({data:{type:'navigationIntentAck',id:'wrong'}});assert.equal(f.clicks.length,0);
 f.ack();assert.deepEqual(f.clicks,[a.href]);assert.equal(f.timers.size,0);assert.equal(f.values.size,0);
 f.ack();assert.equal(f.clicks.length,1);assert.equal(f.posts.length,1,'no duplicate departing scroll request');
});
test('blocked storage still completes via ACK; missing parent uses one bounded fallback',()=>{
 const f=fixture();for(const key of ['getItem','setItem','removeItem'])f.storage[key]=()=>{throw Error('blocked')};
 f.setup();assert.equal(f.c.consume(),false);f.handlers.click(f.clickEvent(f.link()));f.ack();assert.equal(f.clicks.length,1);
 const old=fixture();old.setup();old.handlers.click(old.clickEvent(old.link()));assert.equal(old.timers.size,1);
 const timeout=[...old.timers.values()][0];assert.equal(timeout.ms,120);timeout.f();assert.equal(old.clicks.length,1);assert.equal(old.timers.size,0);
 assert.deepEqual(old.posts.map(p=>p.data.type),['navigationIntent','scrollToTitle']);assert.equal(old.c.consume(),false);
});
test('repeated clicks, pagehide and changed links cannot leave duplicate navigation',()=>{
 const f=fixture();f.setup();const a=f.link();f.handlers.click(f.clickEvent(a));f.handlers.click(f.clickEvent(a));assert.equal(f.posts.length,1);f.ack();assert.equal(f.clicks.length,1);
 const changed=fixture();changed.setup();const l=changed.link();changed.handlers.click(changed.clickEvent(l));l.href='https://gallery.test/other.html';changed.ack();assert.equal(changed.clicks.length,0);assert.equal(changed.posts.at(-1).data.type,'navigationIntentCancel');
 const leaving=fixture();leaving.setup();leaving.handlers.click(leaving.clickEvent(leaving.link()));leaving.events.pagehide();assert.equal(leaving.timers.size,0);
});
test('destination replay remains tied to pageshow for older parent handlers',()=>{
 assert.match(source,/addEventListener\("pageshow", event => \{\s*if \(consumeIframeNavigation\(\) && !isHistoryTraversal\(event\)\)/);
 assert.match(source,/setupIframeNavigation\(document, window\)/);
});

test('a previous child referrer is not mistaken for the parent origin',()=>{
 const f=fixture();f.document.referrer='https://gallery.test/features.html';f.setup();f.handlers.click(f.clickEvent(f.link()));
 assert.equal(f.posts[0].origin,'*');f.ack({source:{}});assert.equal(f.clicks.length,0);f.ack();assert.equal(f.clicks.length,1);
});
