const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('assets/gallery.js','utf8');
function fixture(){
 const values=new Map(),window={parent:{}},location={origin:'https://gallery.test',href:'https://gallery.test/index.html',pathname:'/index.html'};
 let now=1000;
 const storage={getItem:k=>values.has(k)?values.get(k):null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
 const c={window,location,sessionStorage:storage,URL,Date:{now:()=>now}};vm.createContext(c);
 vm.runInContext(source.slice(0,source.indexOf('document.addEventListener("DOMContentLoaded"'))+'\nthis.remember=rememberIframeNavigation;this.consume=consumeIframeNavigation;',c);
 const link=(href='https://gallery.test/detail.html',target='',download=false)=>({href,getAttribute:k=>k==='target'?target:null,hasAttribute:k=>k==='download'&&download});
 return {c,window,location,storage,values,link,time:t=>now=t};
}
test('same-frame navigation is consumed once by the destination document',()=>{
 const f=fixture();f.c.remember(f.link());f.location.pathname='/detail.html';f.time(1500);
 assert.equal(f.c.consume(),true);assert.equal(f.c.consume(),false);assert.equal(f.values.size,0);
});
test('in-place and unrelated documents cannot replay stale navigation',()=>{
 const f=fixture();assert.equal(f.c.consume(),false);f.c.remember(f.link());assert.equal(f.c.consume(),false);
 f.c.remember(f.link());f.location.pathname='/detail.html';f.time(11001);assert.equal(f.c.consume(),false);
 f.time(1000);f.c.remember(f.link());f.time(999);assert.equal(f.c.consume(),false);
});
test('external links, new targets, downloads and top-level pages are excluded',()=>{
 const f=fixture();
 for(const l of [f.link('https://other.test/detail.html'),f.link(undefined,'_top'),f.link(undefined,'_blank'),f.link(undefined,'',true),f.link('https://gallery.test/photo.jpg')])f.c.remember(l);
 assert.equal(f.values.size,0);f.window.parent=f.window;f.c.remember(f.link());assert.equal(f.values.size,0);
});
test('unavailable or corrupt storage never blocks navigation or scrolls',()=>{
 const f=fixture();f.storage.getItem=()=>'{';assert.equal(f.c.consume(),false);
 f.storage.setItem=()=>{throw Error('blocked')};assert.doesNotThrow(()=>f.c.remember(f.link()));
 f.storage.getItem=()=>{throw Error('blocked')};assert.equal(f.c.consume(),false);
});
test('replay is tied to pageshow; prevented/modifier clicks remain excluded',()=>{
 assert.match(source,/addEventListener\("pageshow", event => \{\s*if \(consumeIframeNavigation\(\) && !isHistoryTraversal\(event\)\)/);
 assert.match(source,/if \(e.defaultPrevented \|\| e.button > 0 \|\| e.metaKey \|\| e.ctrlKey \|\| e.shiftKey \|\| e.altKey\) return/);
 assert.match(source,/if \(\/\\\.html\(\\\?\|\$\)\/.test\(href\)\) \{\s*rememberIframeNavigation\(a\)/);
});
