'use strict';
let state, csrf, pendingConfirm, selectedKnowledge;
const $=s=>document.querySelector(s), node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
async function api(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body||{})});const v=await r.json();if(!r.ok){const e=Error(v.error||'操作に失敗しました');e.fieldErrors=v.field_errors;e.userMessage=v.message;throw e}return v}
function message(text,error=false){const e=$('#message');e.textContent=text;e.className=error?'error':''}
function item(title,meta,img){const el=node('article',undefined,'item');if(img){const im=node('img');im.src=img;im.alt=title;el.append(im)}else el.append(node('div'));const body=node('div');body.append(node('h3',title),node('p',meta,'meta'));el.append(body);const actions=node('div',undefined,'item-actions');el.append(actions);return [el,actions,body]}
function button(text,fn,danger=false){const b=node('button',text,danger?'danger':'');b.type='button';b.onclick=fn;return b}
function show(page){document.querySelectorAll('.page').forEach(e=>e.hidden=e.id!==page);document.querySelectorAll('nav button').forEach(e=>e.classList.toggle('active',e.dataset.page===page));$('#page-title').textContent=document.querySelector(`[data-page="${page}"]`).textContent;if(page==='changes')renderPreview();if(page==='sync')loadSync()}
function render(){const c=state.counts;const cards=[['ベストショット',c.best_shots+'件'],['年間Best',c.annual_years+'年'],['調査中キノコ',c.research_open+'件'],['判明済み',c.research_identified+'件'],['activeな告知',c.active_notices+'件'],['master登録種',c.master+'種'],['source',c.sources+'件'],['情報拡充',c.knowledge_batches+' batch'+(c.knowledge_pending?' / 未決 '+c.knowledge_pending+'件':'')]];$('#cards').replaceChildren(...cards.map(([a,b])=>{const e=node('div',undefined,'card');e.append(node('span',a),node('strong',b));return e}));renderBest();renderResearch();renderNotices();renderKnowledge();renderStatus()}

function renderKnowledge(){const batches=$('#knowledge-batches'),candidates=$('#knowledge-candidates');batches.replaceChildren();candidates.replaceChildren();const rows=state.knowledge||[];if(!rows.length){batches.append(node('p','0 batch','meta'));$('#knowledge-pr').disabled=true;return}if(!rows.some(r=>r.batch_id===selectedKnowledge))selectedKnowledge=rows[0].batch_id;rows.forEach(r=>{const e=node('article',undefined,'item knowledge-batch'),body=node('div');body.append(node('h3',r.batch_id),node('p',`${r.status} / ${r.created_at||'-'} / ${r.generator||'-'} / ${r.origin||'-'}`,'badge'),node('p',`base: ${r.base_main_sha||'-'} / ${r.base_matches?'origin/main一致':'不一致'}`,'meta'),node('p',`${r.candidate_count}候補 / 採用 ${r.approved_count} / 保留 ${r.held_count} / 未決 ${r.pending_count}`,'meta'));if((r.blockers||[]).length)body.append(node('p',r.blockers.join(' / '),'error'));const actions=node('div',undefined,'item-actions');actions.append(button('選択',()=>{selectedKnowledge=r.batch_id;renderKnowledge()}));if(r.review_changed)actions.append(button('レビューをリセット',()=>confirmAction('batch内容が変更されたため、全候補を未決へリセットします。',()=>api('/api/knowledge/reset',{batch_id:r.batch_id})),true));e.append(body,actions);batches.append(e)});const batch=rows.find(r=>r.batch_id===selectedKnowledge);(batch.candidates||[]).forEach(c=>{const e=node('article',undefined,'item'),body=node('div'),actions=node('div',undefined,'item-actions');body.append(node('h3',`${c.mushroom_name} / ${c.mushroom_id}`),node('p',`${c.facet_label} / ${c.facet_id}`,'badge'));(c.evidence_records||[]).forEach((v,i)=>{const evidence=node('section',undefined,'knowledge-evidence');evidence.append(node('h4',`根拠 ${i+1}: ${v.evidence_id}`),node('p',`${v.evidence_kind} / source: ${v.source_id}`,'meta'),node('p',v.evidence_text),node('p',`qualifiers: ${(v.qualifiers||[]).join(', ')||'-'}`,'meta'),node('p',`quote: ${v.quote}`));if(/^https?:\/\//.test(v.source_url)){const a=node('a',v.source_url);a.href=v.source_url;a.target='_blank';a.rel='noopener noreferrer';evidence.append(a)}body.append(evidence)});body.append(node('p',`decision: ${c.decision_id} / 現在 ${c.human_decision}`,'meta'));const note=field('review note','note',c.note||'','textarea');body.append(note);['approved','held','pending'].forEach((v,i)=>actions.append(button(['採用','保留','未決に戻す'][i],async()=>{await api('/api/knowledge/decision',{batch_id:batch.batch_id,candidate_id:c.candidate_id,human_decision:v,note:note.querySelector('textarea').value});await load()})));e.append(body,actions);candidates.append(e)});$('#knowledge-pr').disabled=!(batch.status==='PASS'&&batch.base_matches&&batch.pending_count===0&&batch.approved_count>0&&state.repo.gh_authenticated)}
function observation(id){return state.observations.find(o=>o.observation_id===id)||{}}
function renderBest(){const out=$('#best-list');out.replaceChildren();state.best_shots.entries.forEach(row=>{const o=observation(row.observation_id), cap=(o.capture||{}).date||'日付不明';const [e,a,b]=item(o.gallery_name||'観察不明',`${cap} / ${row.comment}`,o.src);b.append(node('p',`selection: ${row.selection_id}`,'meta'));a.append(button('編集・写真差し替え',()=>bestDialog(row,o)),button('年間ベスト',()=>setAnnual(row,o)),button('削除',()=>confirmAction('このベストショットを削除しますか？',()=>api('/api/best-shot/delete',{selection_id:row.selection_id})),true));out.append(e)})}
function field(label,name,value='',type='text'){const l=node('label',label),i=node(type==='textarea'?'textarea':'input');i.name=name;i.value=value;if(type!=='textarea')i.type=type;l.append(i);return l}
function openEditor(title,fields,save){$('#dialog-title').textContent=title;const area=$('#dialog-fields');area.replaceChildren(...fields);const editor=$('#editor'),submit=ev=>{ev.preventDefault();save(new FormData($('#editor form')))};$('#dialog-save').disabled=false;editor.querySelectorAll('[value=cancel]').forEach(b=>b.onclick=()=>editor.close());$('#dialog-save').onclick=submit;$('#editor form').onsubmit=ev=>{if(ev.submitter?.value==='cancel')return;submit(ev)};editor.classList.toggle('best-editor',fields.some(e=>e.classList.contains('photo-picker')));editor.showModal()}
// Best Shot picker: only explicit selection changes the hidden observation ID.
function normalizeMushroomName(value){
 return String(value||'').normalize('NFKC').toLocaleLowerCase('ja').replace(/[\u3041-\u3096]/g,c=>String.fromCharCode(c.charCodeAt(0)+0x60)).trim();
}
function captureMonth(o){
 const raw=o?.capture?.date;
 if(typeof raw!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(raw))return '';
 const d=new Date(raw+'T00:00:00Z');
 return Number.isNaN(d.getTime())||d.toISOString().slice(0,10)!==raw?'':raw.slice(0,7);
}
function monthSlots(id,ownId){
 const month=captureMonth(observation(id));
 const others=state.best_shots.entries.filter(e=>e.selection_id!==ownId&&captureMonth(observation(e.observation_id))===month);
 return {month,full:others.length>=3,free:[1,2,3].filter(n=>!others.some(e=>e.order===n)),others};
}
function observationSelect(selected,current,onSelect){
 const root=node('section',undefined,'photo-picker');root.setAttribute('aria-label','観察写真の選択');
 const hidden=node('input');hidden.type='hidden';hidden.name='observation_id';hidden.value=selected||'';
 const label=node('label','キノコ名で写真を検索'),search=node('input');search.type='search';search.placeholder='例：べにて';search.id='photo-search';label.htmlFor=search.id;label.append(search);
 const error=node('p',undefined,'field-error');error.id='observation_id-error';error.setAttribute('role','status');error.setAttribute('aria-live','polite');search.setAttribute('aria-describedby',error.id);
 const chosen=node('div',undefined,'photo-chosen'),count=node('p',undefined,'meta'),list=node('div',undefined,'photo-results');
 count.setAttribute('role','status');count.setAttribute('aria-live','polite');list.setAttribute('aria-label','検索結果');
 const preview=node('section',undefined,'photo-preview');preview.hidden=true;preview.setAttribute('aria-label','写真の拡大確認');
 const previewHeading=node('h4','拡大確認（ここでは選択は変わりません）'),previewBody=node('div');
 const previewClose=button('拡大確認を閉じる',()=>{preview.hidden=true;previewBody.replaceChildren();if(lastPreviewButton?.isConnected)lastPreviewButton.focus()});
 preview.append(previewHeading,previewBody,previewClose);
 const rows=[...state.observations].sort((a,b)=>{const score=o=>(current&&o.article?.article_id===current.article?.article_id?2:0)+(current&&o.gallery_name===current.gallery_name?1:0);return score(b)-score(a)}).map(o=>({o,key:normalizeMushroomName(o.gallery_name)}));
 let limit=24,composing=false,lastPreviewButton;
 function photo(o,large=false){
  const box=node('div',undefined,'photo-image'),im=node('img');im.alt=o.gallery_name||'観察写真';im.loading=large?'eager':'lazy';im.decoding='async';
  im.onerror=()=>{box.replaceChildren(node('span','画像を読み込めませんでした','image-failure'))};
  im.src=o.src||'';box.append(im);return box;
 }
 function details(o){const d=node('div',undefined,'photo-details');d.append(node('strong',o.gallery_name||'名前不明'),node('span',`撮影日：${o.capture?.date||'確認が必要'}`),node('span',`記事：${o.article?.title||'記事名なし'}`),node('small',`写真ID：${o.observation_id}`));return d}
 function markChosen(){
  chosen.replaceChildren();const o=observation(hidden.value);
  if(o.observation_id){chosen.append(node('p','選択中の写真','badge'),photo(o),details(o));}
  else chosen.append(node('p','写真はまだ選択されていません。候補の「この写真を選択」を押してください。'));
 }
 function showPreview(o,trigger,focus=false){
  if(composing)return;
  lastPreviewButton=trigger;previewBody.replaceChildren(photo(o,true),details(o));preview.hidden=false;
  if(focus){preview.scrollIntoView({block:'nearest'});previewClose.focus()}
 }
 function renderResults(){
  const key=normalizeMushroomName(search.value),matches=rows.filter(r=>r.key.includes(key));
  list.replaceChildren();preview.hidden=true;previewBody.replaceChildren();
  count.textContent=`${matches.length}件の写真 / ${Math.min(limit,matches.length)}件を表示`;
  if(!matches.length)list.append(node('p','一致する写真がありません。キノコ名を短くするか、検索文字を消してください。'));
  matches.slice(0,limit).forEach(({o})=>{
   const row=node('article',undefined,'photo-option');row.dataset.observationId=o.observation_id;
   const inspect=button('拡大して確認',()=>showPreview(o,inspect,true)),choose=button(o.observation_id===hidden.value?'選択中':'この写真を選択',ev=>{
    if(composing||ev.isComposing)return;
    const changed=hidden.value!==o.observation_id;hidden.value=o.observation_id;markChosen();renderResults();
    if(changed)onSelect(o);search.focus();
   });choose.setAttribute('aria-pressed',String(o.observation_id===hidden.value));
   const actions=node('div',undefined,'photo-option-actions');actions.append(inspect,choose);
   row.append(photo(o),details(o),actions);
   row.addEventListener('pointerenter',ev=>{if(ev.pointerType==='mouse')showPreview(o,inspect)});
   list.append(row);
  });
  if(matches.length>limit)list.append(button('さらに24件表示',()=>{limit+=24;renderResults()}));
 }
 search.addEventListener('compositionstart',()=>{composing=true});
 search.addEventListener('compositionend',()=>{composing=false;limit=24;renderResults()});
 search.addEventListener('input',ev=>{if(composing||ev.isComposing)return;limit=24;renderResults()});
 search.addEventListener('keydown',ev=>{if(ev.key==='Enter')ev.preventDefault()});
 const browser=node('div',undefined,'photo-browser');browser.append(list,preview);root.append(hidden,label,error,chosen,count,browser);markChosen();renderResults();return root;
}
function bestField(label,name,value='',type='text'){
 const l=field(label,name,value,type),control=l.querySelector('input,textarea');
 control.id='best-'+name;const err=node('span',undefined,'field-error');err.id=name+'-error';err.setAttribute('role','status');err.setAttribute('aria-live','polite');
 const heading=node('span',undefined,'field-heading');heading.append(node('span',label),err);l.firstChild.remove();l.prepend(heading);control.setAttribute('aria-describedby',err.id);return l;
}
function orderControl(value,onChange){
 const root=node('div',undefined,'order-field'),heading=node('div',undefined,'field-heading'),label=node('label','月内順序');label.htmlFor='best-order';
 const error=node('span',undefined,'field-error');error.id='order-error';error.setAttribute('role','status');error.setAttribute('aria-live','polite');heading.append(label,error);
 const input=node('input');input.id='best-order';input.name='order';input.type='text';input.readOnly=true;input.inputMode='numeric';input.setAttribute('aria-describedby','order-error order-help');input.setAttribute('role','spinbutton');input.setAttribute('aria-valuemin','1');input.setAttribute('aria-valuemax','3');
 const up=button('▲',()=>set(Number(input.value)+1,true)),down=button('▼',()=>set(Number(input.value)-1,true));up.setAttribute('aria-label','月内順序を1増やす');down.setAttribute('aria-label','月内順序を1減らす');
 function set(n,manual=false){input.value=String(Math.max(1,Math.min(3,n)));input.setAttribute('aria-valuenow',input.value);up.disabled=n>=3;down.disabled=n<=1;if(manual)onChange()}
 input.addEventListener('keydown',ev=>{if(['ArrowUp','ArrowDown','Home','End'].includes(ev.key)){ev.preventDefault();set(ev.key==='Home'?1:ev.key==='End'?3:Number(input.value)+(ev.key==='ArrowUp'?1:-1),true)}});
 const controls=node('div',undefined,'order-controls'),arrows=node('div',undefined,'order-arrows');arrows.append(up,down);controls.append(input,arrows);
 const help=node('p','▲▼または上下キーで1〜3を選択','meta');help.id='order-help';root.append(heading,controls,help);set(value);root.setOrder=set;return root;
}
function openBestEditor(row=null,current=null){
 let picker,order,busy=false;
 const fields={},ownId=row?.selection_id;
 function error(name,text){const e=$('#'+name+'-error');if(e)e.textContent=text||'';const control=$(`[name="${name}"]`);if(control)control.setAttribute('aria-invalid',String(Boolean(text)));if(name==='observation_id')$('#photo-search').setAttribute('aria-invalid',String(Boolean(text)))}
 function validate(){
  const id=picker.querySelector('[name=observation_id]').value,slots=monthSlots(id,ownId),n=Number(order.querySelector('input').value);
  const duplicate=state.best_shots.entries.some(e=>e.selection_id!==ownId&&e.observation_id===id);
  const obsError=!id?'観察写真を選択してください':duplicate?'この写真はすでにBest Shotに登録されています':!slots.month?'撮影日を確認できない写真です。撮影日の確認が必要です':'';
  const orderError=!Number.isInteger(n)||n<1||n>3?'1〜3の番号を選択してください':slots.month&&slots.full?`${slots.month.replace('-','年')}月はすでに3枚登録されています`:slots.others.some(e=>e.order===n)?`${slots.month.replace('-','年')}月に順序「${n}」の写真が登録されています`:'';
  error('observation_id',obsError);error('order',orderError);
  const comment=fields.comment.querySelector('textarea').value.trim();error('comment',!comment?'コメントを入力してください':Array.from(comment).length>200?'コメントは200文字以内で入力してください':'');
  let invalid=Boolean(obsError||orderError||!comment||Array.from(comment).length>200);
  for(const [name,max] of [['annual_comment',200],['location',100]])if(fields[name]){const value=fields[name].querySelector('input,textarea').value.trim(),bad=Array.from(value).length>max;error(name,bad?`${name==='location'?'場所':'年間コメント'}は${max}文字以内で入力してください`:'');invalid=invalid||bad;}
  if(fields.selection_id){const id=fields.selection_id.querySelector('input').value.trim(),bad=!id||state.best_shots.entries.some(e=>e.selection_id===id);error('selection_id',bad?'重複しないselection IDを入力してください':'');invalid=invalid||bad;}
  $('#dialog-save').disabled=busy||Boolean(obsError||orderError);return !invalid;
 }
 function autoOrder(o){const slots=monthSlots(o.observation_id,ownId);order.setOrder(slots.free[0]||1);validate();$('#best-modal-error').textContent='';}
 picker=observationSelect(row?.observation_id||'',current,autoOrder);
 order=orderControl(row?.order||1,()=>{validate();$('#best-modal-error').textContent=''});
 fields.comment=bestField('コメント','comment',row?.comment||'','textarea');
 const inputs=[picker];
 if(row){fields.annual_comment=bestField('年間コメント','annual_comment',row.annual_comment||'','textarea');fields.location=bestField('場所','location',row.location||'');}
 else {fields.selection_id=bestField('selection ID','selection_id','best-'+Date.now());inputs.push(fields.selection_id);}
 inputs.push(fields.comment,...(row?[fields.annual_comment,fields.location]:[]),order);
 if(!row)inputs.push(field('トップにNEW!（true/false）','notice','true'));
 const general=node('p',undefined,'field-error modal-error');general.id='best-modal-error';general.setAttribute('role','alert');inputs.push(general);
 Object.values(fields).forEach(f=>f.addEventListener('input',()=>{validate();general.textContent=''}));
 openEditor(row?'ベストショット編集・写真差し替え':'ベストショットを追加',inputs,async f=>{
  if(busy)return;
  if(!validate()){general.textContent='入力内容を確認してください。変更予定には追加されていません。';focusError();return;}
  busy=true;const save=$('#dialog-save');save.disabled=true;save.textContent='確認・保存中…';$('#editor form').setAttribute('aria-busy','true');
  // Lock only this editor while sending; cancellation cannot hide a pending outcome.
  const editor=$('#editor'),cancel=ev=>ev.preventDefault();editor.addEventListener('cancel',cancel);const closers=[...editor.querySelectorAll('[value=cancel]')];closers.forEach(b=>b.disabled=true);
  const locked=[...editor.querySelectorAll('input,textarea,select,button')].map(e=>[e,e.disabled]);locked.forEach(([e])=>e.disabled=true);
  const common={observation_id:f.get('observation_id'),comment:f.get('comment'),order:Number(f.get('order'))};
  let body,path;
  if(row){const changes={};const values={...common,annual_comment:f.get('annual_comment'),location:f.get('location')};for(const [key,value] of Object.entries(values)){
   // Preserve absent/null/empty optional fields on an unchanged edit.
   if((key==='annual_comment'||key==='location')&&value===(row[key]||''))continue;
   const proposed=(key==='annual_comment'||key==='location')?value||null:value;if(proposed!==row[key])changes[key]=proposed;
  }path='/api/best-shot/update';body={selection_id:row.selection_id,changes};}
  else {path='/api/best-shot/add';body={entry:{selection_id:f.get('selection_id'),...common},add_notice:f.get('notice')==='true'};}
  let accepted=false;
  try{await api(path,body);accepted=true;editor.close();const refreshed=await load();message(refreshed?'変更予定に追加しました':'変更予定には追加しましたが、一覧を再取得できませんでした。再読み込みしてください。',!refreshed);}
  catch(e){general.textContent=e.userMessage||'通信またはサーバーの確認に失敗しました。入力内容を保持しています。変更予定を確認してから再試行してください。';Object.entries(e.fieldErrors||{}).forEach(([name,text])=>error(name,text));}
  finally{busy=false;save.textContent='変更予定に追加';editor.querySelector('form').removeAttribute('aria-busy');editor.removeEventListener('cancel',cancel);locked.forEach(([e,wasDisabled])=>e.disabled=wasDisabled);closers.forEach(b=>b.disabled=false);if(!accepted){validateButton();focusError();}}
 });
 function validateButton(){const id=picker.querySelector('[name=observation_id]').value,slots=monthSlots(id,ownId);$('#dialog-save').disabled=slots.full||!slots.month||!id||state.best_shots.entries.some(e=>e.selection_id!==ownId&&e.observation_id===id);}
 function focusError(){const invalid=$('#editor [aria-invalid=true]:not([type=hidden])');if(invalid){invalid.focus();invalid.scrollIntoView({block:'center'})}else{general.tabIndex=-1;general.focus();general.scrollIntoView({block:'nearest'})}}
 if(row)validate();else validateButton();
}
function bestDialog(row,current){openBestEditor(row,current)}
$('#add-best').onclick=()=>openBestEditor();
function setAnnual(row,o){confirmAction(`${(o.capture||{}).date?.slice(0,4)}年の年間ベストに指定しますか？`,()=>api('/api/best-shot/annual',{year:(o.capture||{}).date.slice(0,4),selection_id:row.selection_id}))}
function renderResearch(){const open=$('#case-list'),done=$('#identified-list');open.replaceChildren();done.replaceChildren();state.cases.forEach(c=>{const [e,a]=item(c.gallery_name,`${c.status} / ${(c.capture_dates||[]).join('、')}`,c.photos[0]?.src);a.append(button('正体が判明',()=>identifyDialog(c)));open.append(e)});state.identified.forEach(x=>{const [e,a]=item(`${x.case.gallery_name} → ${x.identification.identified_name}`,x.identification.identified_at,x.case.photos[0]?.src);a.append(button('判明を取り消す',()=>confirmAction('調査中に戻します。履歴はreopenedとして保持します。',()=>api('/api/reopen',{identification_id:x.identification.identification_id})),true));done.append(e)})}
function identifyDialog(c){const names=node('datalist');names.id='master-names';state.master.forEach(m=>{const o=node('option');o.value=m.canonical_name_ja;names.append(o)});const name=field('判明した名前','identified_name');name.querySelector('input').setAttribute('list','master-names');openEditor('正体が判明',[name,names,field('メモ（任意）','note','', 'textarea'),field('IDENTIFIED! summary','summary','1種の正体が判明')],async f=>change('/api/identify',{case_id:c.case_id,identified_name:f.get('identified_name'),note:f.get('note'),summary:f.get('summary')}))}
function renderNotices(){const out=$('#notice-list');out.replaceChildren();state.notices.forEach((n,i)=>{const [e,a,b]=item(`${n.kind.toUpperCase()} / ${n.section}`,n.summary);b.append(node('p',`${n.occurred_at} / ${n.active?'表示中':'非表示'} / 残り ${Math.ceil(n.remaining_seconds/3600)}時間`,'meta'));a.append(button('編集',()=>noticeDialog(n,i)),button('削除',()=>confirmAction('この告知を削除しますか？',()=>api('/api/notice/delete',{index:i})),true));out.append(e)})}
function noticeDialog(n,i){openEditor('更新告知を編集',[field('section','section',n.section),field('kind','kind',n.kind),field('summary','summary',n.summary),field('occurred_at（timezone必須）','occurred_at',n.occurred_at)],async f=>change('/api/notice/update',{index:i,event:{section:f.get('section'),kind:f.get('kind'),summary:f.get('summary'),occurred_at:f.get('occurred_at')}}))}
$('#add-notice').onclick=()=>{const section=node('label','section'),ss=node('select');ss.name='section';['best-shots','research','guide','season','features','about','daily','links'].forEach(v=>{const o=node('option',v);o.value=v;ss.append(o)});section.append(ss);const kind=node('label','種類'),ks=node('select');ks.name='kind';['new','update','identified'].forEach(v=>{const o=node('option',v.toUpperCase());o.value=v;ks.append(o)});kind.append(ks);openEditor('更新告知を追加',[section,kind,field('summary','summary','')],async f=>change('/api/notice/add',{section:f.get('section'),kind:f.get('kind'),summary:f.get('summary')}))}
function renderStatus(){const r=state.repo,f=state.feature_facets||{};$('#site-status').replaceChildren(node('h3','ローカル / GitHub状態'),node('p',`branch: ${r.branch}`),node('p',`working tree: ${r.dirty===null?'取得できませんでした':r.dirty?'dirty':'clean'}`),node('p',`local HEAD: ${r.head_sha||'取得できませんでした'}`),node('p',`origin/main: ${r.origin_main_sha||'取得できませんでした'}`),node('p',`gh-pages: ${r.gh_pages_sha||'取得できませんでした'}`),node('p',`最新Build & Deploy: ${r.latest_action?`${r.latest_action.status} / ${r.latest_action.conclusion||'-'}`:'取得できませんでした'}`),node('p',`gh CLI: ${r.gh_authenticated?'認証済み':'GitHub認証が必要'}`),node('p',`portal-data: ${state.portal_source} / observations: ${state.portal_observation_count}`),node('p',`production_mode: ${state.production_mode}`),node('p',`feature facets: v${f.version||'?'} / assignments: ${(f.entries||[]).length}`))}
function renderPreview(){const out=$('#preview');out.replaceChildren();Object.entries(state.preview).forEach(([name,p])=>{const e=node('article',undefined,'item');const b=node('div');b.append(node('h3',name),node('p',p.changed?'変更あり':'変更なし','badge '+(p.changed?'active':'')));const pre=node('pre',JSON.stringify(p.after,null,2));b.append(pre);e.append(node('div'),b);out.append(e)})}
async function change(path,body){try{await api(path,body);$('#editor').close();await load();message('変更予定に追加しました')}catch(e){message(e.message,true)}}
function confirmAction(text,fn){$('#confirm-text').textContent=text;pendingConfirm=fn;$('#confirm').showModal()}
$('#confirm-ok').onclick=async ev=>{ev.preventDefault();try{await pendingConfirm();$('#confirm').close();await load();message('変更しました')}catch(e){message(e.message,true)}};
$('#validate').onclick=async()=>{try{const v=await api('/api/validate');message('検証成功: '+JSON.stringify(v));$('#create-pr').disabled=!state.repo.gh_authenticated}catch(e){message(e.message,true)}};
$('#create-pr').onclick=()=>confirmAction('origin/mainから一時worktreeを作成し、commit・push・PR作成します。mergeやdeployはしません。',async()=>{const v=await api('/api/pr',{operation:'admin-console'});message('PR: '+v.url)});
$('#knowledge-preview').onclick=async()=>{try{const v=await api('/api/knowledge/preview',{batch_id:selectedKnowledge});$('#knowledge-preview-result').textContent=JSON.stringify(v,null,2);$('#knowledge-pr').disabled=!(v.ready&&state.repo.gh_authenticated)}catch(e){message(e.message,true)}};
$('#knowledge-pr').onclick=()=>confirmAction('承認済み候補のみをpromotionし、origin/mainから一時worktreeを作ってPRを作成します。merge・deployは行いません。',async()=>{const v=await api('/api/knowledge/pr',{batch_id:selectedKnowledge});message('PR: '+v.url)});
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>show(b.dataset.page));
async function load(){try{const r=await fetch('/api/state');state=await r.json();if(!r.ok)throw Error(state.error);csrf=state.csrf;render();return true}catch(e){message(e.message,true);return false}}load();show('dashboard');

//  server-side allow-list and local audit state.
let syncState, syncPage=1, syncTotal=0;
const syncStateNames={non_mushroom:'キノコ以外',unidentified_mushroom:'キノコと確認済み・種名不明',named_mushroom:'名前のあるキノコ',conflict:'判定の競合',unclassified:'未分類',ambiguous:'曖昧な判定'};
const syncReasons={taxonomy_unmatched:'名前の対応が未確認',no_detected_label:'名前の記載を検出できません',taxonomy_mushroom:'既存分類でキノコと確認',taxonomy_review:'分類の確認が必要',shadow_metadata_missing:'判定情報不足',missing:'前回の写真が今回見つかりません'};
function syncError(code){const labels={ADOPTION_IMAGE_FORMAT_UNSUPPORTED:'画像形式または大きさが今回の対応範囲外です。JPEG・PNG・WebPが対象です。',ADOPTION_IMAGE_FETCH_FAILED:'公開画像本体を取得できないため採用を停止しました。',ADOPTION_IMAGE_FETCH_OR_DECODE_FAILED:'画像本体の取得・検証に失敗しました。推測で採用しません。',ADOPTION_STALE_SNAPSHOT:'公開状態が変わりました。再取得して採用を判断し直してください。',ADOPTION_IMAGE_CONTENT_CHANGED:'同じURLでも写真の中身が変わったため停止しました。',ADOPTION_DUPLICATE_URL:'同一画像URLが複数回出現し、採用対象を特定できません。',ADOPTION_NAME_NOT_IN_EXISTING_TAXONOMY:'既存分類の登録名と一致しません。推測で追加せず保留してください。',EXPLICIT_UNLISTED_CLASSIFICATION_REQUIRED:'未収録画像の分類と根拠を先に保存してください。',ADOPTION_EXPLICIT_CONFIRMATION_MISMATCH:'プレビューの採用名をそのまま入力してください。',NAME_MIGRATION_PROTECTED_REFERENCE:'ベストショット・研究室・同定履歴の対象写真は変更できません。',NAME_MIGRATION_DUPLICATE_URL:'同一URLが複数あるため、写真を一意に特定できません。',NAME_MIGRATION_NAME_NOT_IN_EXISTING_TAXONOMY:'既存分類にない名前は適用できません。提案として保留してください。',NAME_MIGRATION_SOURCE_CHANGED:'取得元の名前・分類根拠が変化しています。再レビューが必要です。',CLASSIFICATION_REASON_REQUIRED:'確認メモに分類の根拠を入力してください。',EXPLICIT_NAME_CONFIRMATION_MISMATCH:'変更前・変更後の名前をプレビューどおり入力してください。',EXPLICIT_NAME_PROPOSAL_REQUIRED:'この写真は今回の個別移行に対応していません。提案・保留のみ可能です。',STALE_REVIEW:'取得内容が変わりました。再確認してください。',STALE_PUBLIC_SNAPSHOT:'公開状態が更新されました。再取得してください。',STALE_LIVE_REVIEW:'記事や写真が更新されました。再取得して判断し直してください。',INDIVIDUAL_MIGRATION_REQUIRED:'この変更は個別移行が必要です。この画面では適用できません。',LOCAL_HATENA_CREDENTIALS_UNAVAILABLE:'ローカルのはてな認証が未設定です。',PROTECTED_REFERENCE_ERROR:'既存の登録参照を維持できないため停止しました。',FRESH_MAIN_CHECKOUT_REQUIRED:'ローカルcheckoutを最新mainへ更新してください。',GITHUB_AUTH_REQUIRED:'GitHub CLIの認証が必要です。'};return (labels[code]||'確認・検証が完了していません。')+' ('+code+')'}
const syncGroupNames={blocker:'要対応',new:'確認待ち（新規）',legacy:'確認待ち（以前から）',migration:'要対応・個別移行',auto_added:'自動追加済み',reviewed:'確認済み（履歴のみ）',held:'人間が保留',published:'既存の公開写真',unlisted:'図鑑未収録の公開記事画像',manual_added:'人間による手動採用済み'};
function syncValue(v){return v===null?'UNKNOWN':v===undefined?'未取得':String(v)}
async function syncGet(path){const r=await fetch(path,{cache:'no-store'}),v=await r.json();if(!r.ok)throw Error(v.error);return v}
async function loadSync(){try{
 syncState=await syncGet('/api/sync/state');const out=$('#sync-summary');out.replaceChildren();
 $('#sync-preview').disabled=!syncState.live_review_available;
 $('#sync-live').disabled=!syncState.credentials_available;
 if(!syncState.available){out.append(node('p','公開状態を取得できません: '+syncState.error,'error'));return}
 const s=syncState.summary,a=syncState.latest_action;
 out.append(node('p','前回成功（日本時間）: '+syncValue(s.last_success_jst)),node('p','最新Actions: '+(a?.available?`${a.status} / ${a.conclusion||'未確定'}`:'未取得（gh認証が必要）')));
 if(a?.available&&a.conclusion&&a.conclusion!=='success')out.append(node('p','直近の実行は成功していません。原因: '+(a.error_code||'未取得（Actionsの実行ログで確認してください）'),'error'));
 const fields=[['図鑑未収録画像（以前からの画像を含む）',s.unlisted_image_count],['今回新しく検出した未収録画像',s.new_unlisted_image_count],['手動採用済み写真',s.manual_adoption_count],['公開記事',s.published_articles],['公開写真',s.gallery_photos],['新規記事',s.new_articles],['新規画像',s.new_images],['削除検出',s.deleted_images],['URL変更候補',s.possible_url_changes],['分類確認候補（従来からの保留を含む）',s.classification_review_count],['人間が保留',syncState.groups.held||0],['古い判断（再確認必要）',syncState.stale_decisions],['直近成功時の自動追加写真',s.automatic_added_photo_count],['自動追加日時',s.automatic_added_photo_count===0?'今回追加なし':s.automatic_added_at],['記録された自動追加履歴',s.automatic_history_count]];
 fields.forEach(([k,v])=>out.append(node('p',k+': '+syncValue(v))));
 out.append(node('p',syncState.notice),node('p','ローカル取得エラー: '+(s.error||'なし')),node('p','公開commit: '+s.publication_sha,'meta'),node('p','snapshot: '+s.snapshot_sha256,'meta'),node('p','承認済み移行: '+(s.retirement?`${s.retirement.migration_id} / 合計 ${s.retirement.retired_total}枚`:'未取得'),'meta'));
 if(!syncState.credentials_available)out.append(node('p','ローカルのはてな認証環境変数がないため、同期候補の追加取得は利用できません。通常の自動同期は止まりません。公開済み状態の確認と保留は可能です。'));
 const history=node('details');history.append(node('summary','最近の判断履歴（ローカル・最大30件）'));(syncState.history||[]).forEach(h=>history.append(node('p',`${h.decided_at||h.at||''} / ${h.decision||h.event||''} / ${h.candidate_id||''}`,'meta')));out.append(history);
 await loadSyncRows();
 }catch(e){message(syncError(e.message),true)}}
async function loadSyncRows(){const query=new URLSearchParams({q:$('#sync-search').value,group:$('#sync-group').value,page:String(syncPage)});const v=await syncGet('/api/sync/candidates?'+query);syncTotal=v.total;$('#sync-page-info').textContent=`${v.total}件 / ${v.page}ページ目 / 30件ずつ表示`;$('#sync-prev').disabled=syncPage===1;$('#sync-next').disabled=syncPage*30>=syncTotal;const out=$('#sync-list');out.replaceChildren();
 v.rows.forEach(r=>{const [e,a,b]=item(r.current_name||r.candidate_name||r.detected_name||'名前未確認',r.auto_eligible?'自動追加予定（承認不要）':syncGroupNames[r.group],r.thumbnail);if(e.querySelector('img')){e.querySelector('img').loading='lazy';e.querySelector('img').referrerPolicy='no-referrer'}
 b.append(node('p',`現在: ${r.current_name||'未登録'} / 検出: ${r.detected_name||'なし'} / 候補: ${r.candidate_name||'未確定'}`),node('p',`${syncStateNames[r.state]||r.state} / ${syncReasons[r.reason]||'追加の確認が必要です'}`,'badge'),node('p',`${r.article_title||'記事情報未取得'} / 公開 ${r.published||'未取得'} / 更新 ${r.updated||'未取得'}`,'meta'),node('p',`EXIF撮影日: ${r.capture_date||'情報なし'} / 以前: ${r.previous_state||'未収録'}`,'meta'),node('p',`変更: ${r.change_type} / ${r.candidate_id}`,'meta'),node('p',`画像重複番号: ${r.ordinal} / 既存ID: ${r.observation_id||'未登録'}`,'meta'));
 if(r.unlisted_public_image)b.append(node('p',r.is_new_occurrence?'新しく検出した、図鑑に未収録の画像です。':'以前から公開記事に存在する、図鑑未収録の画像です。新規問題の件数とは区別しています。','meta'));
 if(r.review && ['classify_named','classify_unknown','classify_non_mushroom'].includes(r.review.decision))b.append(node('p','人間の分類（公開への適用とは別）：'+({classify_named:'キノコ・'+r.review.proposed_name,classify_unknown:'キノコだが種名不明',classify_non_mushroom:'キノコ以外'}[r.review.decision]),'meta'));
 if(r.manual_adoption_receipt)b.append(node('p','手動採用済み。自動分類の結果とは別の承認記録です。適用 '+r.manual_adoption_receipt.applied_at,'meta'));
 if(r.adoption_block_reason)b.append(node('p','個別採用・継続不可：'+syncError(r.adoption_block_reason),'error'));
 if(r.auto_eligible)b.append(node('p','既存の安全条件を満たす自動追加候補です。事前承認は不要です。','meta'));
 if(r.automatic_receipt)b.append(node('p',`自動追加: ${r.automatic_receipt.added_at} / 追加時判定: ${r.automatic_receipt.classification_status} / ${r.automatic_receipt.reason}`,'meta'));
 if(r.article_url){const link=node('a','公開記事を確認');link.href=r.article_url;link.target='_blank';link.rel='noopener noreferrer';b.append(link)}
 if(!r.thumbnail)b.append(node('p','安全な画像URLを取得できないため写真表示は利用できません。ハッシュからURLを推測しません。','meta'));
 if(r.stale_review)b.append(node('p','前の判断は古いため適用しません。再確認してください。','error'));
 if(r.protected_existing)b.append(node('p','既存写真は保護されています。ID・URL・削除は変更しません。参照のない単一写真の名前だけ、個別検証とDraft PRを経由して修正できます。','meta'));
 if(r.protected_reference)b.append(node('p','ベストショット・研究室・同定履歴への参照があるため、個別の名前移行も禁止です。','error'));
 if(r.human_name_migration)b.append(node('p','人間の承認済み名前修正: '+r.human_name_migration,'meta'));
 const comment=field('確認メモ（ローカルに保存。PRには本文ではなくハッシュのみ）','comment',r.review?.comment||'','textarea');b.append(comment);
 const choose=async(decision,proposed_name='')=>{try{await api('/api/sync/decision',{candidate_id:r.candidate_id,bundle_id:v.bundle_id,decision,comment:comment.querySelector('textarea').value,proposed_name});await loadSync();message('確認履歴をローカルに保存しました。自動公開の許可・停止条件は変わりません。')}catch(e){message(syncError(e.message),true)}};
 a.append(button('確認済み（履歴のみ）',()=>choose('confirmed')),button('保留',()=>choose('hold')),button('確認不要・現状維持',()=>choose('no_change')),button('判断取消',()=>choose('pending')));
 a.append(button('名前修正を提案（公開未収録・保護対象は保留のみ）',()=>openEditor('名前の提案を保留として保存',[field('人間が確認した名前','name')],async f=>{await choose('propose_name',f.get('name'));$('#editor').close()})));
 if(r.name_migration_available && r.review?.decision==='propose_name')a.append(button('この名前修正を実生成プレビュー',async()=>{try{const p=await api('/api/sync/exception-preview',{candidate_id:r.candidate_id,bundle_id:v.bundle_id});syncException=p;$('#sync-exception-result').textContent=`変更前：${p.old_name}\n変更後：${p.proposed_name}\n対象写真ID：${p.observation_id}\n既存写真ID維持：${p.validation.preserved_photo_ids}枚\n参照保護：検証済み\n公開：まだ変更していません。承認後にDraft PRを作成します。`;$('#sync-exception-technical').textContent=JSON.stringify(p,null,2);$('#sync-exception-approve').disabled=false;$('#sync-exception-pr').disabled=true;message('実生成済み。旧名と新名を確認して明示承認してください。')}catch(e){syncException=null;$('#sync-exception-approve').disabled=true;message(syncError(e.message),true)}}));
 if(r.unlisted_public_image && syncState.live_review_available)a.append(button('この未収録画像を分類して確認',()=>syncClassifyDialog(r,v.bundle_id,comment.querySelector('textarea').value)));
 if(r.adoption_available && ['classify_named','classify_unknown'].includes(r.review?.decision))a.append(button('この写真の採用を実生成プレビュー',async()=>{try{const p=await api('/api/sync/adoption-preview',{candidate_id:r.candidate_id,bundle_id:v.bundle_id});syncAdoption=p;$('#sync-adoption-result').textContent=`採用名：${p.gallery_name}\n未適用承認の更新：${p.replaces_unapplied_instruction?'以前の未適用承認だけを置換します（写真削除ではありません）':'なし'}\n新しい写真ID：${p.observation_id}\n既存ID維持：${p.validation.preserved_photo_ids}枚\n通常の自動追加：${p.validation.added_photos}枚\nこの実行の手動採用：${p.validation.manual_adoptions_applied_this_run}枚\nまだ公開していません。明示承認後、個別Draft PRを作成します。`;$('#sync-adoption-technical').textContent=JSON.stringify(p,null,2);$('#sync-adoption-approve').disabled=false;$('#sync-adoption-pr').disabled=true;message('個別採用の実生成プレビューが成功しました。')}catch(e){syncAdoption=null;$('#sync-adoption-approve').disabled=true;message(syncError(e.message),true)}}));
 if(!r.protected_existing)a.append(button('対象外を提案（保留）',()=>choose('exclude')));
 out.append(e);
 });if(!v.rows.length)out.append(node('p','該当する候補はありません。','empty'));
}
$('#sync-refresh').onclick=async()=>{try{await api('/api/sync/refresh');syncPage=1;await loadSync()}catch(e){message(syncError(e.message),true)}};
$('#sync-live').onclick=async()=>{try{message('公開記事をGET取得・検証しています。');await api('/api/sync/refresh',{live:true});syncPage=1;await loadSync()}catch(e){message(syncError(e.message),true)}};
$('#sync-search-button').onclick=()=>{syncPage=1;loadSyncRows().catch(e=>message(syncError(e.message),true))};
$('#sync-prev').onclick=()=>{syncPage--;loadSyncRows().catch(e=>message(syncError(e.message),true))};$('#sync-next').onclick=()=>{syncPage++;loadSyncRows().catch(e=>message(syncError(e.message),true))};
$('#sync-preview').onclick=async()=>{try{const v=await api('/api/sync/preview');$('#sync-preview-result').textContent=JSON.stringify(v,null,2);message(v.ready?'実生成・参照保護の検証が成功しました。まだ公開されていません。':'検証は保留です: '+syncError(v.error_code),!v.ready)}catch(e){message(syncError(e.message),true)}};

let syncException=null;
$('#sync-exception-approve').onclick=()=>openEditor('写真名の変更を明示確認',[field('変更前の名前を再入力','old_name'),field('変更後の名前を再入力','new_name')],async f=>{try{if(!syncException)throw Error('EXCEPTION_PREVIEW_REQUIRED');await api('/api/sync/exception-approve',{migration_id:syncException.migration_id,confirm_old_name:f.get('old_name'),confirm_new_name:f.get('new_name')});$('#editor').close();$('#sync-exception-pr').disabled=!state.repo.gh_authenticated;message('明示承認を保存しました。まだ公開されていません。')}catch(e){message(syncError(e.message),true)}});
$('#sync-exception-pr').onclick=()=>confirmAction('最新mainの隔離worktreeで実API GET取得・全テスト・鮮度確認を行い、名前変更1件だけのDraft PRを作成します。公開はしません。',async()=>{const p=await api('/api/sync/exception-pr');$('#sync-exception-pr').disabled=true;message('Draft PR: '+p.url)});

let syncAdoption=null;
function syncClassifyDialog(row,bundle,comment){
 const choice=node('label','人間による判断'),select=node('select');select.name='decision';
 [['classify_named','キノコで名前が判明'],['classify_unknown','キノコだが種名不明'],['classify_non_mushroom','キノコ以外'],['hold','判断保留']].forEach(([v,t])=>{const o=node('option',t);o.value=v;select.append(o)});choice.append(select);
 const name=field('人間が確認した名前（登録済み名称のみ）','name'),input=name.querySelector('input'),list=node('datalist');list.id='sync-adoption-names';input.setAttribute('list',list.id);(syncState.taxonomy_mushroom_names||[]).forEach(n=>{const o=node('option');o.value=n;list.append(o)});select.onchange=()=>{input.disabled=select.value!=='classify_named';if(input.disabled)input.value=''};
 openEditor('図鑑未収録画像の人間による分類',[choice,name,list,field('判断根拠（ローカル保存。PRにはハッシュのみ）','comment',comment,'textarea')],async f=>{try{await api('/api/sync/decision',{candidate_id:row.candidate_id,bundle_id:bundle,decision:f.get('decision'),proposed_name:f.get('name')||'',comment:f.get('comment')});$('#editor').close();syncAdoption=null;$('#sync-adoption-approve').disabled=true;$('#sync-adoption-pr').disabled=true;await loadSync();message('人間の分類を保存しました。採用・公開はまだ行っていません。')}catch(e){message(syncError(e.message),true)}});
}
$('#sync-adoption-approve').onclick=()=>openEditor('この写真の採用を明示確認',[field('プレビューの採用名を再入力（種名不明なら「不明」）','name')],async f=>{try{if(!syncAdoption)throw Error('ADOPTION_PREVIEW_REQUIRED');await api('/api/sync/adoption-approve',{migration_id:syncAdoption.migration_id,confirm_name:f.get('name'),confirm_adoption:true});$('#editor').close();$('#sync-adoption-pr').disabled=!state.repo.gh_authenticated;message('採用の明示承認を保存しました。まだ公開されていません。')}catch(e){message(syncError(e.message),true)}});
$('#sync-adoption-pr').onclick=()=>confirmAction('最新mainの隔離worktreeで実API GET・画像本体・全テスト・公開状態を再検証し、採用1件だけのDraft PRを作成します。merge・公開はしません。',async()=>{const p=await api('/api/sync/adoption-pr');$('#sync-adoption-pr').disabled=true;message('個別採用Draft PR: '+p.url)});
