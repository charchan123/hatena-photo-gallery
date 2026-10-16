'use strict';
let deletionState, deletionPreview, deletionBusy=false;
const deletionKinds={article_deleted:'記事削除',photo_deleted:'個別写真削除'};
const deletionStates={identity_uncertain:'取得・識別異常：削除不可',approval_pending:'管理者の承認待ち',reconfirmation_pending:'独立した再取得の確認待ち',automatic_eligible:'自動削除可能',manual_eligible:'管理者承認済み',held:'保留'};
const deletionReasons={research:'不明キノコ研究室',identification:'同定履歴',best_shot:'Best Shot',annual_best:'年間Best Shot',pending_best_shot:'未公開のBest Shot',pending_curated_reference:'未マージPRの重要参照',receipt:'個別移行履歴',curated_history:'管理者の選定・履歴',curated_page:'特集・静的ページ',pending_deletion_hold:'未マージPRの保留・代替案'};
async function deletionRequest(path,body){
 if(deletionBusy)return null;
 deletionBusy=true;const controls=[...$('#deletions').querySelectorAll('button,input,textarea,select')].map(e=>[e,e.disabled]);controls.forEach(([e])=>e.disabled=true);
 const status=$('#deletion-message');status.textContent='確認中です。しばらくお待ちください。';status.className='';
 try{const value=await api(path,body);status.textContent='保存しました。公開は行っていません。';return value}
 catch(e){status.textContent=e.userMessage||'通信に失敗しました。入力内容を保持しています。保存状況を確認してから再試行してください。';status.className='error';status.tabIndex=-1;return {failed:true}}
 finally{deletionBusy=false;controls.forEach(([e,disabled])=>e.disabled=disabled);if(status.className==='error')status.focus()}
}
async function loadDeletions(){
 const status=$('#deletion-message');
 try{const r=await fetch('/api/deletions/state');const value=await r.json();if(!r.ok)throw Error(value.message||'検出結果を取得できませんでした');deletionState=value;renderDeletions()}
 catch(e){status.textContent=e.message;status.className='error'}
}
function renderDeletions(){
 const s=deletionState;if(!s)return;
 const out=$('#deletion-list');out.replaceChildren();
 $('#deletion-summary').replaceChildren(node('p',`検出 ${s.rows.length}件 / 永続確認履歴 ${s.history_count}回`),node('p',`最終巡回 ${s.last_checked_at||'まだありません'} / 最終同期成功 ${s.last_success_at||'未確認'}`),node('p',s.live?'最新の公開記事と照合済み':'保存済みの検出です。承認には「公開記事を取得して再照合」が必要です。'),node('p','保護参照が残る写真の通常承認はできません。代替案は参照を自動変更しません。研究履歴は承認記録に保持します。アーカイブは公開ページから非表示にする操作で、公開GitHubの履歴には残ります。'));
 if(s.blocker_code){const alert=node('p',s.blocker_message,'error');alert.setAttribute('role','alert');$('#deletion-summary').append(alert);if(s.retired_review_ids?.length)$('#deletion-summary').append(node('p','再照合する退役ID：'+s.retired_review_ids.join('、'),'meta'));}
 if(!s.rows.length&&s.last_fetch_healthy===false)out.append(node('p','直近の取得・照合が安全停止しています。削除候補がないとは判断できません。保存された履歴を確認してください。','error'));
 else if(!s.rows.length)out.append(node('p','現在のsnapshotに対応する削除検出はありません。巡回履歴がない場合は、ライブ再照合で確認してください。'));
 s.rows.forEach(row=>{
  const [card,actions,body]=item(row.gallery_name||'図鑑未収録の画像',`${row.identity_issues.some(s=>s.includes('URL'))?'URL変更・記事移動の疑い':deletionKinds[row.kind]||row.kind} / ${deletionStates[row.status]||row.status}`,null);card.classList.add('deletion-card');body.classList.add('deletion-body');
  if(row.src&&/^https:\/\//.test(row.src)){const image=node('img');image.loading='lazy';image.src=row.src;image.alt=row.gallery_name||'削除候補の旧写真';image.onerror=()=>{image.hidden=true;body.prepend(node('p','元画像を読み込めませんでした','meta'))};card.firstElementChild.replaceWith(image)}
  body.append(node('p',row.article_title||'記事情報は照合キーを参照','meta'));
  if(row.article_url&&/^https:\/\//.test(row.article_url)){const link=node('a','元の記事を確認');link.href=row.article_url;link.target='_blank';link.rel='noopener noreferrer';body.append(link)}
  body.append(node('p',`観察写真ID：${row.observation_id||row.candidate_id+'（図鑑未収録）'}`,'meta'),node('p',`検出：${row.detected_at||s.last_checked_at||'今回のライブ取得'}`,'meta'));
  (row.protection||[]).forEach(ref=>body.append(node('p',`${deletionReasons[ref.kind]||ref.kind}：${ref.id}`,'error')));
  (row.related_research_cases||[]).forEach(c=>body.append(node('p',`研究ケース：元の写真 ${c.photo_count}枚 / 削除候補を除く残存 ${c.remaining_photo_count}枚`,'meta')));
  if(row.identity_issues.length)body.append(node('p','URL変更・順序・取得状態の個別調査が必要です。通常の削除承認では解除できません。','error'));
  if(row.mass_review)body.append(node('p','大量削除の確認対象です。写真ごとに判断してください。','error'));
  const recommendation=row.identity_issues.length?'削除を保留して、記事・画像の照合結果を確認してください。':row.protection.some(r=>r.kind==='research')?(row.related_research_cases?.some(c=>c.remaining_photo_count>0)?'削除を保留するか、ケースを継続する研究写真の削除承認を検討してください。':'削除を保留するか、研究履歴を残す非公開アーカイブを検討してください。'):row.protection.length?'削除を保留し、代替写真の提案と重要な参照の変更を個別に確認してください。':row.mass_review?'写真ごとに削除理由を確認して、個別に判断してください。':row.status==='automatic_eligible'?'安全条件を満たしています。日次の生成・参照検証を待ってください。':'独立した再取得による確認を待ってください。';
  body.append(node('p','推奨：'+recommendation));
  if(row.decision)body.append(node('p',`${row.decision.stale?'古い判断：再確認が必要':'保存済みの判断'} / ${row.decision.action}`,'badge'));
  const choice=node('label','この写真への判断'),select=node('select');select.name='deletion-action';
  [['hold','削除を保留'],['propose_replacement','代替写真への参照変更を提案'],['approve','個別削除を承認'],['approve_research_photo','研究写真の削除を承認（ケース・履歴は継続）'],['archive_research','研究履歴を保持して非公開アーカイブ'],['retire_research','研究ケースの退役を明示承認（履歴は保持）']].forEach(([v,t])=>{const o=node('option',t);o.value=v;const research=row.protection.some(r=>r.kind==='research'),other=row.protection.some(r=>!['research','identification'].includes(r.kind)),remaining=row.related_research_cases?.some(c=>c.remaining_photo_count>0);if((v==='approve'&&row.protection.length)||(v==='approve_research_photo'&&(!research||other||remaining===false))||(['archive_research','retire_research'].includes(v)&&(!research||other||remaining===true)))o.disabled=true;select.append(o)});if(row.decision&&!row.decision.stale)select.value=row.decision.action;choice.append(select);
  const reason=field('判断の理由（必須）','deletion-reason',row.decision?.note||'','textarea');
  const replacement=field('代替写真の観察ID（提案時のみ）','replacement-id',row.decision?.replacement_id||'');
  const confirmation=field(row.observation_id?'承認時は対象の観察写真IDを入力':'承認時は対象の確認用IDを入力','deletion-confirm','');
  body.append(choice,reason,replacement,confirmation);
  actions.append(button('この1件の判断をローカル保存',async()=>{
   const value=await deletionRequest('/api/deletions/decision',{candidate_id:row.candidate_id,fingerprint:row.fingerprint,action:select.value,
    reason:reason.querySelector('textarea').value,replacement_id:replacement.querySelector('input').value,confirm_id:confirmation.querySelector('input').value});
   if(value&&!value.failed){deletionPreview=null;$('#deletion-pr').disabled=true;await loadDeletions()}
  }));out.append(card);
 });
 $('#deletion-history').textContent=JSON.stringify({decisions:s.audit,pr_attempts:s.pr_attempts||[]},null,2);
}
$('#deletion-refresh').onclick=async()=>{const value=await deletionRequest('/api/deletions/refresh',{live:false});if(value&&!value.failed){deletionState=value;deletionPreview=null;$('#deletion-pr').disabled=true;renderDeletions()}};
$('#deletion-live').onclick=async()=>{const value=await deletionRequest('/api/deletions/refresh',{live:true});if(value&&!value.failed){deletionState=value;deletionPreview=null;$('#deletion-pr').disabled=true;renderDeletions()}};
$('#deletion-preview').onclick=async()=>{const value=await deletionRequest('/api/deletions/preview',{});if(value&&!value.failed){deletionPreview=value;$('#deletion-diff').textContent=JSON.stringify(value.diff||value.files,null,2);$('#deletion-pr').disabled=value.ready===false;$('#deletion-message').textContent=value.message||'公開は行っていません。'}};
$('#deletion-pr').onclick=async()=>{if(!deletionPreview)return;const value=await deletionRequest('/api/deletions/pr',{fingerprint:deletionPreview.fingerprint});if(value&&!value.failed){deletionPreview=null;$('#deletion-pr').disabled=true;$('#deletion-diff').textContent=`Draft PR：${value.url}\n公開は行っていません。`}};
