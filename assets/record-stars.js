/* Official Hatena renderer owns all reads, colours and additions. No posting API here. */
(function(root){
 'use strict';
 function total(items){
  if(!items.length)return null; // Empty DOM also occurs before load/failure; never infer zero.
  let sum=0;
  for(const item of items){
   const count=item.kind==='star'?1:item.kind==='count'?item.count:null;
   if(!Number.isSafeInteger(count)||count<0||!Number.isSafeInteger(sum+count))return null;
   sum+=count;
  }
  return sum;
 }
 if(typeof module==='object'&&module.exports){module.exports={total};return;}
 const doc=root.document;if(!doc)return;
 // A stalled third-party deferred script must not leave the portal's existing fade-in at opacity 0.
 // Keep normal gallery initialization intact; only reveal already-rendered HTML after three seconds.
 root.setTimeout(()=>{if(doc.body?.classList.contains('portal-index')&&getComputedStyle(doc.body).opacity==='0'){
  doc.body.style.opacity='1';doc.body.dataset.recordStarsLoadingFallback='';
 }},3000);
 root.Hatena=root.Hatena||{};root.Hatena.Star=root.Hatena.Star||{};
 root.Hatena.Star.SiteConfig={entryNodes:{'article.record-star-entry':{
  uri:'a.record-star-permalink',title:'strong.record-preview-title',container:'div.record-stars-native'
 }}};
 // The blog's official renderer consumes these declarative attributes. Its DOMContentLoaded
 // registration runs before the generic SiteConfig renderer, which skips an existing native host.
 for(const row of doc.querySelectorAll('article.record-star-entry')){
  const mount=row.querySelector('.record-stars-native'),permalink=row.querySelector('a.record-star-permalink');
  if(!mount||!permalink)continue;
  mount.dataset.hatenaStarContainer='';mount.dataset.hatenaStarUrl=permalink.href;
  mount.dataset.hatenaStarTitle=row.querySelector('.record-preview-title').textContent;
  mount.dataset.hatenaStarVariant='profile-icon';
  mount.dataset.hatenaStarProfileUrlTemplate='https://blog.hatena.ne.jp/{username}/';
 }
 const shadowCSS=':host{display:inline-block;white-space:nowrap;max-width:100%;vertical-align:middle}'+
  ':host>[data-record-star-hidden]{display:none!important}'+
  ':host>a,:host>button{min-width:20px;min-height:28px;justify-content:center}'+
  '[part~=star-button-container]{min-width:36px;min-height:28px;margin:0!important}'+
  '@media(pointer:coarse){:host>a,:host>button{min-width:28px;min-height:28px}}';
 function start(){
  for(const group of doc.querySelectorAll('.record-stars')){
   const mount=group.querySelector('.record-stars-native'),link=group.querySelector('.record-stars-total'),dots=group.querySelector('.record-stars-ellipsis');
   if(!mount||!link||!dots)continue;
   let shadow,observer,frame=0;
   function unknown(){mount.removeAttribute('data-ready');link.textContent='スター';link.setAttribute('aria-label','元記事ではてなスターを見る・追加する');dots.hidden=true;delete group.dataset.total;}
   function schedule(){if(!frame)frame=root.requestAnimationFrame(()=>{frame=0;render()});}
   function render(){
    const host=mount.querySelector('[data-hatena-star]');
    if(!host?.shadowRoot){unknown();return;}
    if(shadow!==host.shadowRoot){
     observer?.disconnect();shadow=host.shadowRoot;
     observer=new MutationObserver(schedule);observer.observe(shadow,{childList:true,subtree:true,characterData:true});
    }
    if(!shadow.querySelector('style[data-record-star-style]')){
     const style=doc.createElement('style');style.dataset.recordStarStyle='';style.textContent=shadowCSS;shadow.append(style);
    }
    const nodes=Array.from(shadow.children).filter(e=>!e.matches('style[data-record-star-style]'));
    const control=nodes.find(e=>e.matches('[part~=star-button-container]'));
    const items=nodes.filter(e=>e!==control),parsed=items.map(e=>
     e.matches('a[href]')&&e.querySelector('img,svg')?{kind:'star'}:
     e.matches('button')&&/^\d+$/.test(e.textContent.trim())?{kind:'count',count:Number(e.textContent.trim())}:{kind:'unknown'});
    // An unexpected vendor structure fails closed; original article link remains available.
    if(!control||nodes.filter(e=>e.matches('[part~=star-button-container]')).length!==1||parsed.some(i=>i.kind==='unknown')){unknown();return;}
    const n=total(parsed);
    if(n===null){link.textContent='スター';link.setAttribute('aria-label','元記事ではてなスターを見る・追加する');delete group.dataset.total;}
    else{link.textContent='（'+n+'）';link.setAttribute('aria-label','はてなスター合計'+n+'個。元記事で見る・追加する');group.dataset.total=String(n);}
    for(const iframe of control.querySelectorAll('iframe'))iframe.title='元記事のはてなスターを追加：'+group.closest('.record-preview-row').querySelector('.record-preview-title').textContent;
    // Preserve the native iframe, event handlers and image URLs; hide only excess siblings.
    mount.dataset.ready='';dots.hidden=true;
    for(const e of items)e.removeAttribute('data-record-star-hidden');
    const widths=items.map(e=>{const s=getComputedStyle(e);return e.getBoundingClientRect().width+(parseFloat(s.marginLeft)||0)+(parseFloat(s.marginRight)||0)});
    const controlStyle=getComputedStyle(control),controlWidth=control.getBoundingClientRect().width+(parseFloat(controlStyle.marginLeft)||0)+(parseFloat(controlStyle.marginRight)||0);
    let available=mount.clientWidth-controlWidth,used=0,keep=0;
    if(widths.reduce((a,b)=>a+b,0)>available){dots.hidden=false;available=mount.clientWidth-controlWidth;}
    for(const width of widths){if(width>0&&used+width<=available+.1){used+=width;keep++;}else break;}
    items.forEach((e,i)=>{if(i>=keep)e.dataset.recordStarHidden='';});
    dots.hidden=keep===items.length;
   }
   new MutationObserver(schedule).observe(mount,{childList:true,subtree:true});
   if(root.ResizeObserver)new ResizeObserver(schedule).observe(group);
   root.addEventListener('resize',schedule,{passive:true});root.addEventListener('pageshow',schedule);
   schedule();
  }
 }
 if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',start,{once:true});else start();
})(typeof window==='undefined'?{}:window);
