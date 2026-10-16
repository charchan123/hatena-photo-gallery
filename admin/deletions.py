"""Local individual deletion review, persistent drafts, no automatic approval.

This is independent of ChangeSet: existing unsaved Best Shot/notice work is never
reset or staged. Only immutable individual manifests enter dedicated Draft PRs.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from article_sync import SyncError, payload_hash, read_json
from sync_deletions import plan, select, validate_history, occurrences, photo_keys
from deletion_protection import collect, open_selections
from deletion_history import GitHistory
from deletion_approvals import validate, ACTIONS, archive_context, load as load_approvals, latest
from deletion_review import details
from .core import ROOT
from .sync import LOCK, public_publication, live_capture

MESSAGES = {
    'DELETION_RECEIPT_INVALID_OR_REAPPEARED':'退役済みの記事・写真の再出現、または履歴の不整合を検出しました。自動復活せず、個別の確認が必要です。',
    'DELETION_CONFIRMATION_OR_APPROVAL_PENDING':'独立した再取得、または重要な参照の承認がまだ完了していません。',
    'DELETION_REVIEW_STALE':'公開snapshot・写真・参照が変わりました。再取得して確認し直してください。',
    'DELETION_REFERENCES_UNAVAILABLE':'保護参照を取得できませんでした。削除は許可されていません。',
    'DELETION_APPROVAL_INVALID':'承認内容を確認してください。写真ID・理由・確認入力が必要です。',
    'DELETION_ARCHIVE_CASE_STILL_HAS_LIVE_PHOTOS':'この研究ケースには残存写真があります。ケース全体の退役はできません。',
    'LOCAL_HATENA_CREDENTIALS_UNAVAILABLE':'ライブ取得の認証環境がありません。保存済みの検出結果を表示しています。',
    'DELETION_RESEARCH_CASE_WOULD_DISAPPEAR':'この操作では研究ケースが消えてしまいます。削除を保留するか、全写真を個別確認してアーカイブを選んでください。',
    'DELETION_ARCHIVE_ACTION_CONFLICT':'同じ研究ケースの判断が一致していません。写真ごとに同じアーカイブ方針を選択してください。',
    'DELETION_PROTECTED_REFERENCE_REMAINS':'Best Shotや重要な履歴の参照が残っています。削除を保留し、参照変更を個別に確認してください。',
    'DELETION_HISTORY_STORAGE_UNAVAILABLE':'確認履歴を取得できませんでした。削除は許可されていません。',
    'DELETION_LIVE_REVIEW_REQUIRED':'最新の公開記事を取得してから承認内容を確認してください。',
    'DELETION_EXPLICIT_CONFIRMATION_REQUIRED':'対象の観察写真IDを入力して、1件ずつ明示確認してください。',
    'DELETION_OBSERVATION_ONLY':'導入確認モードです。取得履歴を保存しましたが、写真の削除と公開は実行していません。',
    'DELETION_PR_RECOVERY_REQUIRED':'前回のDraft PR作成は結果が未確認です。履歴の専用ブランチをGitHubで確認してください。重複作成は停止しています。',
    'DELETION_PR_VALIDATION_BLOCKED':'実生成の安全検証が停止しました。他の承認待ちも含めて確認してください。',
}


def atomic_json(path, value):
    path=Path(path)
    if any(p.is_symlink() for p in (path,*path.parents)):raise SyncError('DELETION_LOCAL_STORAGE_UNSAFE')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='deletion-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


class DeletionReview:
    def __init__(self, root=ROOT, state_path=None):
        self.root=Path(root);self.path=Path(state_path or self.root/'admin/local-state/deletions.json')
        if any(p.is_symlink() for p in (self.path,*self.path.parents)):raise SyncError('DELETION_LOCAL_STORAGE_UNSAFE')
        self.state=read_json(self.path) if self.path.exists() else {'version':1,'decisions':{},'audit':[]}
        if self.state.get('version')!=1 or not isinstance(self.state.get('decisions'),dict):raise SyncError('DELETION_LOCAL_HISTORY_INVALID')
        self.disk_hash=payload_hash(self.state) if self.path.exists() else None
        self.publication=None;self.live=None;self.rows=[];self.history=[];self.protection=None;self.preview=None

    def save(self):
        import sqlite3
        self.path.parent.mkdir(parents=True,exist_ok=True)
        lock=self.path.with_suffix('.lock.sqlite3')
        if lock.is_symlink():raise SyncError('DELETION_LOCAL_STORAGE_UNSAFE')
        connection=sqlite3.connect(str(lock),timeout=10)
        try:
            connection.execute('BEGIN IMMEDIATE')
            current=payload_hash(read_json(self.path)) if self.path.exists() else None
            if current!=self.disk_hash:raise SyncError('DELETION_LOCAL_STATE_CONFLICT')
            atomic_json(self.path,self.state);self.disk_hash=payload_hash(self.state)
            connection.commit()
        finally:connection.close()

    def protection_context(self, publication, source, pending):
        snapshot=publication['article-sync-snapshot.json'];portal=publication['portal-data.json']
        from deletion_guard import validate_ledger
        validate_ledger(snapshot['payload'].get('deletions',[]),portal,source['articles'])
        applied={r['approval_id'] for r in snapshot['payload'].get('deletions',[]) if r['approval_id']}
        active=[m for m in latest(load_approvals(self.root)) if m['baseline']==snapshot['sha256'] and m['approval_id'] not in applied]
        missing=[{'observation_id':r['observation_id']} for key,r in photo_keys(portal).items() if key not in occurrences(source['articles'])]
        registry_before=archive_context(active,portal,read_json(self.root/'data/research-identifications.json'),
            read_json(self.root/'data/mushroom-master.json'),missing)
        return collect(portal,snapshot,self.root,pending,registry_before=registry_before),registry_before,active

    def refresh(self, live=False):
        with LOCK:
            if self.path.exists():
                self.state=read_json(self.path);self.disk_hash=payload_hash(self.state)
            self.preview=None;self.live=None;self.protection=None
            self.publication=public_publication(refresh=True)
            snapshot=self.publication['article-sync-snapshot.json'];portal=self.publication['portal-data.json']
            self.history=GitHistory(self.root).load(snapshot['payload'].get('deletion_history_head'))
            if live:
                source=live_capture();protection,self.registry_before,self.active=self.protection_context(self.publication,source,open_selections())
                rows=plan(snapshot,portal,source['articles'],source['fetch_audit'],set(source['excluded_draft_hashes']),protection)
                select(rows,snapshot,self.history,protection,datetime.now(timezone.utc).isoformat(),[m for m in latest(load_approvals(self.root)) if m['baseline']==snapshot['sha256']])
                self.live=source;self.protection=protection
            else:
                last=self.history[-1]['event'] if self.history else {}
                rows=last.get('findings',[]) if last.get('baseline')==snapshot['sha256'] else []
            self.rows=details(rows,portal)
            detections=self.state.setdefault('detections',{})
            for row in self.rows:
                detected=next((item['event']['at'] for item in self.history if item['event']['kind']=='fetch' and item['event']['candidates'].get(row['candidate_id'])==row['fingerprint']),None)
                detections.setdefault(row['fingerprint'],detected or datetime.now(timezone.utc).isoformat())
                row['detected_at']=detected or detections[row['fingerprint']]
            for cid,decision in self.state['decisions'].items():
                row=next((r for r in self.rows if r['candidate_id']==cid),None)
                if not row or row['fingerprint']!=decision['fingerprint'] or snapshot['sha256']!=decision['baseline'] or (self.protection is not None and self.protection['sha256']!=decision['protection']):
                    decision['stale']=True
            self.save();return self.dashboard()

    def dashboard(self):
        last_fetch=next((item['event'] for item in reversed(self.history) if item['event']['kind']=='fetch'),None)
        last_result=next((item['event'] for item in reversed(self.history) if item['event']['kind']=='result'),None)
        error=last_result.get('error_code') if last_result and self.publication and last_result['baseline']==self.publication['article-sync-snapshot.json']['sha256'] else None
        return {'rows':[{**r,'decision':self.state['decisions'].get(r['candidate_id'])} for r in self.rows],
            'live':self.live is not None,'history_count':sum(item['event']['kind']=='fetch' for item in self.history),'audit_record_count':len(self.history),
            'history_head':validate_history(self.history),'audit':self.state['audit'][-50:],
            'pr_attempts':list(self.state.get('pr_attempts',{}).values()),
            'baseline':self.publication['article-sync-snapshot.json']['sha256'] if self.publication else None,
            'last_checked_at':last_fetch['at'] if last_fetch else None,
            'last_fetch_healthy':last_fetch['healthy'] if last_fetch else None,
            'blocker_code':error,'blocker_message':MESSAGES.get(error,'安全確認が必要です。自動削除と公開は保留しています。') if error else None,
            'retired_review_ids':[r['observation_id'] for r in self.publication['article-sync-snapshot.json']['payload'].get('deletions',[])] if error=='DELETION_RECEIPT_INVALID_OR_REAPPEARED' else [],
            'last_success_at':self.publication['article-sync-snapshot.json']['payload']['last_success_at'] if self.publication else None,
            'publication':'未実施。個別のDraft PRと日次同期の安全検証が必要です。'}

    def row(self, body):
        if not self.publication:raise SyncError('DELETION_LIVE_REVIEW_REQUIRED')
        row=next((r for r in self.rows if r['candidate_id']==body.get('candidate_id')),None)
        if not row or body.get('fingerprint')!=row['fingerprint']:raise SyncError('DELETION_REVIEW_STALE')
        return row

    def decide(self,body):
        if set(body)-{'candidate_id','fingerprint','action','reason','confirm_id','replacement_id'}:raise SyncError('DELETION_APPROVAL_INVALID')
        with LOCK:
            row=self.row(body);action=body.get('action');reason=body.get('reason','')
            if action not in ACTIONS or not isinstance(reason,str) or not 1<=len(reason.strip())<=1000:raise SyncError('DELETION_APPROVAL_INVALID')
            if action not in {'hold','propose_replacement'} and body.get('confirm_id')!=(row['observation_id'] or row['candidate_id']):raise SyncError('DELETION_EXPLICIT_CONFIRMATION_REQUIRED')
            if action not in {'hold','propose_replacement'} and self.live is None:raise SyncError('DELETION_LIVE_REVIEW_REQUIRED')
            # Refresh against the immutable publication and the real source. A
            # different result invalidates approval while preserving input/UI.
            if self.live is not None:self.assert_fresh()
            replacement=body.get('replacement_id') or None
            if action=='propose_replacement':
                if not replacement or not any(r['observation_id']==replacement for r in self.publication['portal-data.json']['observations']):raise SyncError('DELETION_APPROVAL_INVALID')
                if replacement in {r['observation_id'] for r in self.rows}:raise SyncError('DELETION_APPROVAL_INVALID')
            snapshot=self.publication['article-sync-snapshot.json']
            m={'version':1,'candidate_id':row['candidate_id'],'fingerprint':row['fingerprint'],'baseline':snapshot['sha256'],
                'protection':self.protection['sha256'] if self.protection else '0'*64,'action':action,
                'approved_at':datetime.now(timezone.utc).isoformat(),'reason_sha256':__import__('article_sync').digest(reason.strip()),
                'case_ids':[],'archives':[],'registry_before':None,'replacement_id':replacement,
                'supersedes':next((m['approval_id'] for m in latest(load_approvals(self.root)) if m['candidate_id']==row['candidate_id']),None)}
            if action in {'archive_research','retire_research','approve_research_photo'}:
                from research_ui import build_research_cases
                refs=[r['id'] for r in row['protection'] if r['kind']=='research']
                if len(refs)!=1:raise SyncError('DELETION_APPROVAL_INVALID')
                case=next(c for c in build_research_cases(self.publication['portal-data.json']) if c['case_id']==refs[0])
                missing={r['observation_id'] for r in self.rows if not r['identity_issues']}
                ids={p['observation_id'] for p in case['photos']}
                if action=='approve_research_photo':
                    if not ids-missing:raise SyncError('DELETION_RESEARCH_CASE_WOULD_DISAPPEAR')
                elif not ids<=missing:raise SyncError('DELETION_ARCHIVE_CASE_STILL_HAS_LIVE_PHOTOS')
                registry=self.registry_before or read_json(self.root/'data/research-identifications.json')
                by_id={r['observation_id']:r for r in self.publication['portal-data.json']['observations']}
                m.update(case_ids=refs,registry_before=registry,archives=[{'case':case,
                    'observations':[by_id[p['observation_id']] for p in case['photos']],
                    'identifications':[r for r in registry['identifications'] if r['case_id']==case['case_id']]}])
            m['approval_id']=payload_hash(m);validate(m)
            candidate=deepcopy(row)
            if action not in {'hold','propose_replacement'} and not select([candidate],snapshot,self.history,self.protection,m['approved_at'],[m]):
                if row['protection'] and action=='approve':raise SyncError('DELETION_PROTECTED_REFERENCE_REMAINS')
                raise SyncError('DELETION_CONFIRMATION_OR_APPROVAL_PENDING')
            old_state=deepcopy(self.state)
            self.state['decisions'][row['candidate_id']]={**m,'note':reason.strip(),'stale':False}
            self.state['audit'].append({'at':m['approved_at'],'event':'individual_decision','candidate_id':m['candidate_id'],'action':action,'approval_id':m['approval_id']})
            try:self.save()
            except Exception:
                self.state=old_state;raise
            self.preview=None
            return {'saved':True,'published':False,'approval_id':m['approval_id']}

    def assert_fresh(self):
        if not self.live:raise SyncError('DELETION_LIVE_REVIEW_REQUIRED')
        fresh=public_publication(refresh=True);source=live_capture()
        if fresh['publication_sha']!=self.publication['publication_sha'] or source['articles']!=self.live['articles']:
            raise SyncError('DELETION_REVIEW_STALE')
        protection,_,_=self.protection_context(fresh,source,open_selections())
        if protection['sha256']!=self.protection['sha256']:raise SyncError('DELETION_REVIEW_STALE')

    def files(self):
        if not self.live:raise SyncError('DELETION_LIVE_REVIEW_REQUIRED')
        decisions=[{k:v for k,v in d.items() if k not in {'note','stale'}} for d in self.state['decisions'].values() if not d.get('stale')]
        for d in decisions:validate(d)
        existing=load_approvals(self.root)
        files={}
        for decision in decisions:
            path='sync-migrations/photo-deletions/'+decision['approval_id']+'.json'
            if (self.root/path).exists():
                if read_json(self.root/path)!=decision:raise SyncError('DELETION_APPROVAL_HISTORY_EXISTS')
            else:files[path]=decision
        # A merged archive may still be awaiting publication. Replacing it with
        # a hold must restore the active registry while retaining both capsules.
        combined=latest(existing+[d for d in decisions if d['approval_id'] not in {m['approval_id'] for m in existing}])
        snapshot=self.publication['article-sync-snapshot.json']
        applied={r['approval_id'] for r in snapshot['payload'].get('deletions',[]) if r['approval_id']}
        combined=[m for m in combined if m['baseline']==snapshot['sha256'] and m['approval_id'] not in applied]
        capsules=[m for m in getattr(self,'active',[])+decisions if m['archives']]
        if capsules:
            before=capsules[0]['registry_before']
            if any(m['registry_before']!=before for m in capsules):raise SyncError('DELETION_ARCHIVE_HISTORY_CHANGED')
            ids={cid for m in combined if m['action'] in {'archive_research','retire_research'} for cid in m['case_ids']}
            after={**before,'identifications':[r for r in before['identifications'] if r['case_id'] not in ids]}
            archive_context(combined,self.publication['portal-data.json'],after,read_json(self.root/'data/mushroom-master.json'),self.rows)
            from research_identifications import validate_registry
            validate_registry(after,self.publication['portal-data.json'],read_json(self.root/'data/mushroom-master.json'))
            if read_json(self.root/'data/research-identifications.json')!=after:files['data/research-identifications.json']=after
        return files

    def preview_changes(self):
        with LOCK:
            self.assert_fresh();files=self.files()
            if not files:raise SyncError('DELETION_APPROVAL_INVALID')
            decisions=[v for k,v in files.items() if k.startswith('sync-migrations/')]
            merged=load_approvals(self.root)
            effective=latest(merged+[m for m in decisions if m['approval_id'] not in {d['approval_id'] for d in merged}])
            selected=select(deepcopy(self.rows),self.publication['article-sync-snapshot.json'],self.history,self.protection,datetime.now(timezone.utc).isoformat(),effective)
            negative_only=all(m['action'] in {'hold','propose_replacement'} for m in decisions)
            ready=len(selected)==len(self.rows) or negative_only
            self.preview={'fingerprint':payload_hash(files),'files':files,'published':False,'ready':ready,'negative_only':negative_only}
            return {'files':files,'diff':[{'path':p,'before':read_json(self.root/p) if (self.root/p).exists() else None,'after':v} for p,v in files.items()],
                'fingerprint':self.preview['fingerprint'],'published':False,'ready':ready,
                'message':'保留・代替案はDraft PRで共有します。承認反映はマージと日次検証後のみです。' if ready else 'ほかの承認待ちがあります。全件の安全条件が揃うまで公開候補のPRは作成できません。'}

    def create_pr(self,body):
        if set(body)!={'fingerprint'}:raise SyncError('DELETION_APPROVAL_INVALID')
        from .git_workflow import run,repository_status
        from .core import safe_branch_name
        import shutil
        import subprocess
        with LOCK:
            persisted=read_json(self.path) if self.path.exists() else self.state
            attempt=persisted.get('pr_attempts',{}).get(body['fingerprint'])
            if attempt:
                if attempt['status']=='created':
                    return {'url':attempt['url'],'branch':attempt['branch'],'draft':True,'published':False,'local_audit_saved':True,'already_created':True}
                raise SyncError('DELETION_PR_RECOVERY_REQUIRED')
            if not self.preview or not self.preview['ready'] or body['fingerprint']!=self.preview['fingerprint']:raise SyncError('DELETION_REVIEW_STALE')
            if not repository_status()['gh_authenticated']:raise SyncError('GITHUB_AUTH_REQUIRED')
            if run(['git','status','--porcelain']).stdout.strip():raise SyncError('CLEAN_CHECKOUT_REQUIRED')
            run(['git','fetch','origin','main','gh-pages'])
            base=run(['git','rev-parse','origin/main']).stdout.strip()
            if run(['git','rev-parse','HEAD']).stdout.strip()!=base:raise SyncError('FRESH_MAIN_CHECKOUT_REQUIRED')
            self.assert_fresh();files=self.files()
            if payload_hash(files)!=body['fingerprint']:raise SyncError('DELETION_REVIEW_STALE')
            directory=Path(tempfile.mkdtemp(prefix='kinoko-deletion-pr-'));work=directory/'work';previous=directory/'previous'
            branch=safe_branch_name('photo-deletion');added=[]
            try:
                run(['git','worktree','add','-b',branch,str(work),'origin/main']);added.append(work)
                run(['git','worktree','add','--detach',str(previous),self.publication['publication_sha']]);added.append(previous)
                for path,value in files.items():
                    if path!='data/research-identifications.json' and not __import__('re').fullmatch(r'sync-migrations/photo-deletions/[0-9a-f]{64}\.json',path):raise SyncError('DELETION_PR_PATHS_INVALID')
                    target=work/path
                    if target.exists() and path!='data/research-identifications.json':raise SyncError('DELETION_APPROVAL_HISTORY_EXISTS')
                    atomic_json(target,value)
                import main
                env=os.environ.copy();env.update(HATENA_USER=main.HATENA_USER,HATENA_BLOG_ID=main.HATENA_BLOG_ID,HATENA_API_KEY=main.HATENA_API_KEY)
                from .sync import generate_in_worktree
                generated=generate_in_worktree(work,previous,directory/'unused',directory/'validation.json',env,deletion_preview=True)
                report=read_json(directory/'validation.json')
                expected_hold=self.preview['negative_only'] and generated.returncode==1 and report.get('error_code')=='DELETION_CONFIRMATION_OR_APPROVAL_PENDING'
                if generated.returncode and not expected_hold:raise SyncError('DELETION_PR_VALIDATION_BLOCKED')
                # No candidate ever enters gh-pages or the server's in-memory draft.
                report=read_json(directory/'validation.json')
                if report.get('result')!='PREVIEW' and not expected_hold:raise SyncError('DELETION_PR_VALIDATION_BLOCKED')
                for command in (['python','-m','pytest','-q'],['python','-m','compileall','-q','.']):
                    if run(command,cwd=work,check=False).returncode:raise SyncError('DELETION_PR_TEST_FAILED')
                for test in sorted((work/'tests').glob('*.js')):
                    if run(['node',str(test)],cwd=work,check=False).returncode:raise SyncError('DELETION_PR_TEST_FAILED')
                for path in run(['git','ls-files','--others','--exclude-standard','--','output'],cwd=work).stdout.splitlines():
                    target=work/path
                    if target.is_file() and not target.is_symlink():target.unlink()
                changed=sorted(set(run(['git','diff','--name-only'],cwd=work).stdout.splitlines()+run(['git','ls-files','--others','--exclude-standard'],cwd=work).stdout.splitlines()))
                if changed!=sorted(files):raise SyncError('DELETION_PR_PATHS_INVALID')
                for path,value in files.items():
                    if read_json(work/path)!=value:raise SyncError('DELETION_REVIEW_STALE')
                run(['git','add','--',*sorted(files)],cwd=work)
                if sorted(run(['git','diff','--cached','--name-only'],cwd=work).stdout.splitlines())!=sorted(files):raise SyncError('DELETION_PR_PATHS_INVALID')
                run(['git','diff','--cached','--check'],cwd=work)
                run(['git','fetch','origin','main','gh-pages']);self.assert_fresh()
                if run(['git','rev-parse','origin/main']).stdout.strip()!=base:raise SyncError('DELETION_REVIEW_STALE')
                run(['git','commit','-m','Review exact photo deletion and retain internal research history'],cwd=work)
                # Reserve before the first remote write. An uncertain CLI/network
                # outcome must never create another branch/PR on blind retry.
                self.state.setdefault('pr_attempts',{})[body['fingerprint']]={'fingerprint':body['fingerprint'],
                    'branch':branch,'status':'pending_remote','url':None}
                self.save()
                run(['git','push','-u','origin',branch],cwd=work)
                body_file=directory/'body.md'
                body_file.write_text('写真単位の明示承認です。保留と代替案は削除権限を与えません。\n\n'
                    '対象snapshot・画像・観察ID・保護参照・独立取得履歴を照合し、実生成と回帰試験を検証しました。'
                    '研究履歴は承認manifest内部に保存し、公開ページには出力しません。\n\n'
                    '変更ファイル:\n'+''.join('- '+p+'\n' for p in sorted(files))+
                    '\nDraft PRのみ。マージ・本番公開・ブログへの書込みは実行していません。\n',encoding='utf-8')
                result=run(['gh','pr','create','--base','main','--head',branch,'--draft','--title','写真の個別削除承認と研究履歴の保持','--body-file',str(body_file)],cwd=work)
                self.state['audit'].append({'at':datetime.now(timezone.utc).isoformat(),'event':'draft_pr_created','fingerprint':body['fingerprint']})
                self.state['pr_attempts'][body['fingerprint']].update(status='created',url=result.stdout.strip())
                self.preview=None
                try:self.save();saved=True
                except Exception:saved=False
                return {'url':result.stdout.strip(),'draft':True,'published':False,'local_audit_saved':saved}
            finally:
                for path in reversed(added):run(['git','worktree','remove','--force',str(path)],check=False)
                shutil.rmtree(directory,ignore_errors=True)
