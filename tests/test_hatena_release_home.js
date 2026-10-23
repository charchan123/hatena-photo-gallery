const test=require('node:test'),assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../hatena/release-2026-10-24/home-bootstrap.js'),'utf8');
function fixture({pathname='/',search='',origin='https://exsudoporus-ruber.hatenablog.jp',marker=true,pageClass='page-index',existing=false,contentOK=true}={}){
 const nodes=new Map(),classes=new Set([pageClass]),timers=[];
 function element(tag){return {tag,attrs:{},events:{},children:[],setAttribute(k,v){this.attrs[k]=v},append(...v){this.children.push(...v)},addEventListener(k,v){this.events[k]=v}}}
 const container=element('div'),content=element('div');content.parentElement=contentOK?container:null;
 container.insertBefore=(node,ref)=>{assert.equal(ref,content);nodes.set(node.id,node)};
 const doc={body:{classList:{contains:k=>classes.has(k),add:k=>classes.add(k)}},
 createElement:element,getElementById:k=>nodes.get(k),querySelector:k=>k==='#main-inner article.entry'?{}:null};
 nodes.set('container-inner',container);nodes.set('content',content);
 if(marker)nodes.set('kinoko-home-release',{dataset:{release:marker===true?'2026-10-24':'other'}});
 if(existing)nodes.set('photoGallery',{});
 vm.runInNewContext(code,{document:doc,location:{origin,pathname,search},URLSearchParams,setTimeout:fn=>timers.push(fn)});
 return {nodes,classes,timers,portal:nodes.get('kinoko-home-portal')};
}
test('root mount is additive, has native fallback and retains sandbox permissions',()=>{
 const f=fixture();assert.ok(f.portal);assert.ok(f.classes.has('kinoko-home-ready'));
 const [nav,status,frame]=f.portal.children;
 assert.deepEqual(nav.children.map(a=>a.href),['/archive','https://charchan123.github.io/hatena-photo-gallery/new-top.html','/?kinoko-native=1','/rss']);
 assert.equal(frame.id,'photoGallery');assert.ok(frame.attrs.sandbox.includes('allow-top-navigation-by-user-activation'));
 assert.equal(frame.attrs.scrolling,'no');f.timers[0]();assert.match(status.textContent,/高さを確認できません/);
 frame.events['kinoko:height-ready']();assert.equal(status.hidden,true);
});
for(const options of [{marker:false},{marker:'wrong'},{pathname:'/new-top'},{pathname:'/entry/a'},
 {origin:'https://other.test'},{search:'?page=2'},{search:'?kinoko-native=1'},{existing:true},{pageClass:'page-entry'},{contentOK:false}]){
 test('does not activate on '+JSON.stringify(options),()=>assert.equal(fixture(options).portal,undefined));
}
test('tracking and same-origin preview queries do not break root mounting',()=>{
 assert.ok(fixture({search:'?utm_source=test'}).portal);
 assert.ok(fixture({search:'?preview=synthetic'}).portal);
});
