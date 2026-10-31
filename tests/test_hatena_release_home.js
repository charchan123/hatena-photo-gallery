const test=require('node:test'),assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../hatena/release-2026-10-24/home-bootstrap.js'),'utf8');
function fixture({pathname='/',search='',origin='https://exsudoporus-ruber.hatenablog.jp',marker=true,pageClass='page-index',existing=false,contentOK=true}={}){
 const nodes=new Map(),classes=new Set([pageClass]),timers=[];
 function element(tag){return {tag,hidden:false,getBoundingClientRect(){return {height:600}},attrs:{},events:{},children:[],setAttribute(k,v){this.attrs[k]=v},append(...v){this.children.push(...v)},addEventListener(k,v){this.events[k]=v}}}
 const container=element('div'),content=element('div');content.parentElement=contentOK?container:null;
 container.insertBefore=(node,ref)=>{assert.equal(ref,content);nodes.set(node.id,node)};
 const doc={body:{classList:{contains:k=>classes.has(k),add:(...ks)=>ks.forEach(k=>classes.add(k)),remove:(...ks)=>ks.forEach(k=>classes.delete(k))}},
 createElement:element,getElementById:k=>nodes.get(k),querySelector:k=>k==='#main-inner article.entry'?{}:null};
 nodes.set('container-inner',container);nodes.set('content',content);
 if(marker)nodes.set('kinoko-home-release',{dataset:{release:marker===true?'2026-10-24':'other'}});
 if(existing)nodes.set('photoGallery',{});
 vm.runInNewContext(code,{document:doc,location:{origin,pathname,search},URLSearchParams,setTimeout:fn=>timers.push(fn)});
 return {nodes,classes,timers,portal:nodes.get('kinoko-home-portal')};
}
test('root mount keeps native DOM but hides fallback after successful readiness',()=>{
 const f=fixture();assert.ok(f.portal);assert.ok(f.classes.has('kinoko-home-ready'));
 const [status,frame,menu]=f.portal.children;const nav=menu.children[1];
 assert.deepEqual(nav.children.map(a=>a.href),['/archive','https://charchan123.github.io/hatena-photo-gallery/new-top.html','/?kinoko-native=1','/rss']);
 assert.equal(menu.hidden,true);assert.equal(frame.id,'photoGallery');
 assert.ok(frame.attrs.sandbox.includes('allow-top-navigation-by-user-activation'));assert.equal(frame.attrs.scrolling,'no');
 frame.events['kinoko:height-ready']();f.timers[0]();assert.equal(status.hidden,true);assert.equal(menu.hidden,true);assert.ok(f.classes.has('kinoko-home-active'));
});
test('startup failure reveals all escape links and rejects late readiness',()=>{
 const f=fixture();const [status,frame,menu]=f.portal.children;
 f.timers[0]();assert.equal(frame.hidden,true);assert.equal(menu.hidden,false);assert.equal(menu.open,true);
 assert.match(status.textContent,/新トップを確認できません/);frame.events['kinoko:height-ready']();assert.equal(menu.hidden,false);assert.equal(f.classes.has('kinoko-home-active'),false);
});
for(const options of [{marker:false},{marker:'wrong'},{pathname:'/new-top'},{pathname:'/entry/a'},
 {origin:'https://other.test'},{search:'?page=2'},{search:'?kinoko-native=1'},{existing:true},{pageClass:'page-entry'},{contentOK:false}]){
 test('does not activate on '+JSON.stringify(options),()=>assert.equal(fixture(options).portal,undefined));
}
test('tracking and same-origin preview queries do not break root mounting',()=>{
 assert.ok(fixture({search:'?utm_source=test'}).portal);
 assert.ok(fixture({search:'?preview=synthetic'}).portal);
});

// Carried-over Gate2 opening-ACK model regressions; uses public-only fixtures.
(() => {
'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const R=__dirname,root=path.join(R,'..');
const oldChild=fs.readFileSync(path.join(R,'fixtures/hatena-release/before-photo-opening.js'),'utf8');
const oldParent=fs.readFileSync(path.join(R,'fixtures/hatena-release/before-photo-opening-parent.html'),'utf8');
const newChild=fs.readFileSync(path.join(root,'assets/gallery.js'),'utf8');
const newParent=fs.readFileSync(path.join(root,'hatena/release-2026-10-24/footer-managed.html'),'utf8').replace(/\r\n/g,'\n');
const PH='https://exsudoporus-ruber.hatenablog.jp',CH='https://child.test';
const footerScript=s=>[...s.matchAll(/<script>\r?\n?([\s\S]*?)<\/script>/g)].at(-1)[1];
const childScript=s=>s.slice(s.indexOf('  let overlayParentOrigin = null;'),s.indexOf('  // Only observation-record exits'));
function style(){const s={};Object.defineProperty(s,'setProperty',{value:(k,v)=>s[k]=v});return s;}
function fixture({old=false,mode='window',legacyHost=false,noOverlay=false,failPopover=false,failDialog=false,portal=false}={}){
 const queue=[],calls=[],warnings=[],hostHandlers={},childHandlers={},frameHandlers={},timers=new Map();let timerId=0;
 let popover=false,dialog=null,phCount=0,shown=0,heights=0;
 const defer=(f,d)=>{timers.set(++timerId,{f,d});return timerId;};
 const on=(map)=>(t,f)=>(map[t]??=[]).push(f);
 const host={innerWidth:900,innerHeight:897,scrollY:mode==='window'?4050:0,addEventListener:on(hostHandlers),removeEventListener(){},
  scrollTo(o){calls.push(['restore-window',o.top]);this.scrollY=o.top;root.scrollTop=o.top;}};
 const root={scrollTop:host.scrollY,clientHeight:897,scrollHeight:mode==='body'?897:7300,overflowY:mode==='body'?'hidden':'visible'};
 const body={scrollTop:mode==='body'?4050:0,clientHeight:mode==='body'?841:7300,clientTop:0,overflowY:mode==='body'?'auto':'visible',
  addEventListener(){},removeEventListener(){},getBoundingClientRect:()=>({top:56}),
  scrollTo(o){calls.push(['restore-body',o.top]);this.scrollTop=o.top;}};
 const y=()=>mode==='body'?body.scrollTop:host.scrollY;
 function move(v){if(mode==='body')body.scrollTop=v;else {host.scrollY=v;root.scrollTop=v;}}
 const attrs=new Map();
 const wrapper={style:style(),dataset:{},getAttribute:k=>attrs.get(k)??null,
  setAttribute(k,v){attrs.set(k,v);},removeAttribute(k){attrs.delete(k);if(k==='style')for(const n of Object.keys(this.style))delete this.style[n];},
  before(){phCount++;},matches:()=>popover,
  getBoundingClientRect:()=>({top:popover?0:300-y(),height:parseFloat(wrapper.style.height)||6693,width:885}),
  hidePopover(){calls.push(['popover-hide']);popover=false;}};
 if(!noOverlay)wrapper.showPopover=()=>{calls.push(['popover-show',y()]);if(failPopover)throw Error('simulated');popover=true;move(0);};
 const frame={style:style(),dataset:{},src:CH+'/hatena-photo-gallery/new-top.html',closest:()=>wrapper,parentElement:wrapper,
  addEventListener:on(frameHandlers),dispatchEvent(){},getAttribute:k=>k==='style'?null:null,
  removeAttribute(k){if(k==='style')for(const n of Object.keys(this.style))delete this.style[n];},setAttribute(){},
  getBoundingClientRect:()=>({top:popover?0:300-y(),height:parseFloat(frame.style.height)||6643,width:popover?900:885})};
 const child={parent:host,addEventListener:on(childHandlers),location:{origin:CH},
  postMessage(data,target){assert.equal(target,CH);queue.push({to:'child',data,origin:PH,source:host});}};
 frame.contentWindow=child;
 host.postMessage=(data,target)=>{assert.equal(target,PH);queue.push({to:'host',data,origin:CH,source:child});};
 const hostDoc={documentElement:root,body,fullscreenElement:null,
  getElementById:id=>id==='photoGallery'?frame:id==='kinoko-home-portal'?wrapper:null,
  createElement:()=>({style:style(),setAttribute(){},remove(){phCount--;}})};
 vm.runInNewContext(footerScript(old||legacyHost?oldParent:newParent),{window:host,document:hostDoc,location:{href:PH+'/'},URL,
  getComputedStyle:e=>({overflowY:e.overflowY,minHeight:'0',marginTop:'20px',marginBottom:'0px'}),
  setTimeout:defer,clearTimeout:id=>timers.delete(id),Event:class Event{}});
 const links=Array.from({length:2},(_,i)=>({href:'https://example.invalid/photo-'+i,
  querySelector:()=>({alt:'photo '+i}),focus:o=>calls.push(['trigger-focus',o.preventScroll])}));
 const children={'.shot-close':{focus:o=>calls.push(['close-focus',o.preventScroll])},'.shot-prev':{},'.shot-next':{},img:{},p:{}};
 const childDoc={body:{classList:{contains:()=>portal},append(){}},documentElement:{dataset:{}},addEventListener(){},
  querySelectorAll:()=>links,createElement(){
   const listeners={};dialog={open:false,setAttribute(){},querySelector:q=>children[q],
    addEventListener:on(listeners),showModal(){if(failDialog)throw Error('simulated');shown++;calls.push(['show-modal',y(),popover]);this.open=true;if(!popover)move(0);},
    close(){if(!this.open)return;this.open=false;for(const f of listeners.close||[])f();}};return dialog;
  }};
 const context=vm.createContext({window:child,parent:host,document:childDoc,HTMLDialogElement:class{},
  sendHeight:()=>heights++,setTimeout:defer,clearTimeout:id=>timers.delete(id),console:{warn:x=>warnings.push(x)}});
 vm.runInContext(childScript(old?oldChild:newChild),context);
 const deliver=e=>{for(const f of (e.to==='child'?childHandlers:hostHandlers).message||[])f(e);};
 const flush=()=>{let count=0;while(queue.length){if(++count>60)throw Error('message loop');deliver(queue.shift());}};
 function advertise(){for(const f of frameHandlers.load||[])f();flush();}
 advertise();
 return {host,child,root,body,frame,wrapper,queue,calls,warnings,timers,context,links,deliver,flush,move,y,
  open(i=0){vm.runInContext('openShot(__link)',Object.assign(context,{__link:links[i]}));},
  close(){dialog?.close();},runTimeout(){for(const [id,t]of [...timers])if(t.d===2000){timers.delete(id);t.f();}},
  get popover(){return popover;},get shown(){return shown;},get placeholderCount(){return phCount;},
  get dataset(){return childDoc.documentElement.dataset;},get heights(){return heights;}};
}
for(const mode of ['window','body']){
 test('old model reproduces 4050 -> 0 saved/restored ('+mode+')',()=>{
  const f=fixture({old:true,mode});f.open();assert.equal(f.y(),0);f.flush();f.close();f.flush();
  assert.deepEqual(f.calls.filter(x=>x[0].startsWith('restore-')).at(-1),['restore-'+mode,0]);
 });
 test('paired protocol captures before modal, restores4050 ('+mode+')',()=>{
  const f=fixture({mode});f.open();assert.equal(f.shown,0);assert.equal(f.y(),4050);
  f.flush();assert.equal(f.shown,1);assert.ok(f.popover);
  const start=f.calls.findIndex(x=>x[0]==='popover-show'),show=f.calls.findIndex(x=>x[0]==='show-modal');
  assert.ok(start<show);assert.equal(f.calls[start][1],4050);
  f.close();f.flush();assert.equal(f.y(),4050);assert.equal(f.popover,false);assert.equal(f.placeholderCount,0);
  assert.deepEqual(f.calls.filter(x=>x[0].startsWith('restore-')).at(-1),['restore-'+mode,4050]);
 });
}
test('wrong-origin, wrong-source and stale ACK cannot open dialog',()=>{
 const f=fixture();f.open();const id=f.queue[0].data.id;
 for(const extra of [{origin:'https://attacker.invalid'},{source:{}},{data:{type:'photoOpeningAck',id:'photo-0-0',ok:true}},{data:{type:'photoOpeningAck',id,ok:'true'}}])
  f.deliver({to:'child',origin:PH,source:f.host,data:{type:'photoOpeningAck',id,ok:true},...extra});
 assert.equal(f.shown,0);f.flush();assert.equal(f.shown,1);
});
test('wrong-origin/source or malformed opening requests cannot promote parent',()=>{
 for(const extra of [{origin:'https://attacker.invalid'},{source:{}},{data:{type:'photoOpening',id:'bad'}},{data:{type:'photoOpening',id:'photo-'+'0'.repeat(90)+'-1'}}]){
  const f=fixture();f.deliver({to:'host',origin:CH,source:f.child,data:{type:'photoOpening',id:'photo-1-1'},...extra});
  assert.equal(f.popover,false);assert.equal(f.y(),4050);
 }
});
test('double clicks while pending do not issue multiple requests',()=>{
 const f=fixture();f.open();f.open(1);assert.equal(f.queue.length,1);f.flush();assert.equal(f.shown,1);
});
test('duplicate ACK does not reopen dialog or recapture position',()=>{
 const f=fixture();f.open();f.deliver(f.queue.shift());const ack=f.queue.shift();f.deliver(ack);f.deliver(ack);
 assert.equal(f.shown,1);assert.equal(f.calls.filter(x=>x[0]==='popover-show').length,1);
 f.close();f.flush();assert.equal(f.y(),4050);
});
test('missing ACK times out, cancels parent and ignores late ACK',()=>{
 const f=fixture();f.open();f.deliver(f.queue.shift());const late=f.queue.shift();assert.ok(f.popover);
 f.runTimeout();f.flush();assert.equal(f.popover,false);assert.equal(f.y(),4050);assert.equal(f.shown,0);
 f.deliver(late);assert.equal(f.shown,0);assert.ok(f.warnings.length);
});
test('wrong cancellation id cannot close another active photo',()=>{
 const f=fixture();f.open();f.flush();assert.ok(f.popover);
 f.deliver({to:'host',origin:CH,source:f.child,data:{type:'photoOpeningCancel',id:'photo-0-0'}});
 assert.ok(f.popover);f.close();f.flush();assert.equal(f.y(),4050);
});
test('another opening request cannot steal active snapshot',()=>{
 const f=fixture();f.open();f.flush();
 f.deliver({to:'host',origin:CH,source:f.child,data:{type:'photoOpening',id:'photo-9-9'}});
 assert.equal(f.queue.at(-1).data.ok,false);f.flush();f.close();f.flush();assert.equal(f.y(),4050);
});
test('popover failure rejects ACK, preserves list and cleans placeholder',()=>{
 const f=fixture({failPopover:true});f.open();f.flush();assert.equal(f.shown,0);assert.equal(f.popover,false);
 assert.equal(f.y(),4050);assert.equal(f.placeholderCount,0);
});
test('showModal failure cancels prepared parent and restores position',()=>{
 const f=fixture({failDialog:true});f.open();f.flush();assert.equal(f.shown,0);assert.equal(f.popover,false);
 assert.equal(f.y(),4050);assert.equal(f.placeholderCount,0);
});
test('old parent without capability retains original compatibility path',()=>{
 const f=fixture({legacyHost:true});f.open();assert.equal(f.shown,1);assert.equal(f.queue[0].data.type,'lgOpening');
});
test('no overlay host does not advertise opening protocol',()=>{
 const f=fixture({noOverlay:true});f.open();assert.equal(f.shown,1);assert.equal(f.queue.length,0);
});
test('valid repeat close is idempotent',()=>{
 const f=fixture();f.open();f.flush();f.close();f.flush();f.close();f.flush();
 assert.equal(f.y(),4050);assert.equal(f.placeholderCount,0);
});
test('photo trigger receives preventScroll focus on close',()=>{
 const f=fixture();f.open();f.flush();f.close();f.flush();assert.deepEqual(f.calls.find(x=>x[0]==='trigger-focus'),['trigger-focus',true]);
});
test('900/899 authenticated column selection retained',()=>{
 const f=fixture({portal:true});assert.equal(f.dataset.portalColumns,'2');
 f.deliver({to:'child',origin:PH,source:f.host,data:{type:'requestHeight',overlayViewport:true,photoOpeningProtocol:1,portalWide:false}});
 assert.equal(f.dataset.portalColumns,'1');
 f.deliver({to:'child',origin:'https://attacker.invalid',source:f.host,data:{type:'requestHeight',portalWide:true}});
 assert.equal(f.dataset.portalColumns,'1');
});
test('navigation and height handlers unchanged outside new opening branches',()=>{
 const begin="    if (data.type === 'navigationIntent')",oldEnd="    } else if (data.type === 'lgOpening')",newEnd="    } else if (data.type === 'photoOpening')";
 assert.equal(oldParent.slice(oldParent.indexOf(begin),oldParent.indexOf(oldEnd)),newParent.slice(newParent.indexOf(begin),newParent.indexOf(newEnd)));
 assert.ok(newParent.includes('portalWide:document.getElementById(\'kinoko-home-portal\') ? window.innerWidth >= 900 : undefined'));
 assert.equal(oldChild.slice(0,oldChild.indexOf('document.addEventListener("DOMContentLoaded"')),newChild.slice(0,newChild.indexOf('document.addEventListener("DOMContentLoaded"')));
 for(const source of [oldParent,newParent])assert.ok(source.includes("if (event.source !== iframe.contentWindow || event.origin !== galleryOrigin) return;"));
});
test('archived Gate2 child payload hashes remain frozen',()=>{
 const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
 assert.equal(hash('tests/fixtures/hatena-release/accepted-public-gallery.js'),'23e8bb1abd04b5f0c034fd6dc84aee5bd72611474d34b312f08e1536e603d734');
 assert.equal(hash('assets/portal.css'),'2eff9ed126bc16447b42b63ff9ccb51065619784d28eb31d285df3aaccf0e13a');
});
test('both complete parent script blocks and child source parse',()=>{
 for(const match of newParent.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
 new vm.Script(newChild);
});

})();
