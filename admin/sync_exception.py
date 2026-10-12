"""Explicit human preview/approval for one usable name migration, not request-only."""
from datetime import datetime, timezone
from pathlib import Path
import json

from article_sync import digest, payload_hash, SyncError
from sync_exceptions import check_target, raw_fingerprint, validate_manifest
from .sync import LOCK, ReviewError, public_publication, live_capture, validate_package


def build_manifest(review,candidate_id):
    if not review.live: raise ReviewError('LIVE_REVIEW_REQUIRED')
    row=next((r for r in review.rows if r['candidate_id']==candidate_id),None)
    d=review.decisions.get(candidate_id)
    if not row or not d or d['decision']!='propose_name' or not row.get('name_migration_available'):
        raise ReviewError('EXPLICIT_NAME_PROPOSAL_REQUIRED')
    if d['bundle_id']!=review.bundle_id or d['fingerprint']!=row['fingerprint']: raise ReviewError('STALE_REVIEW')
    if not d.get('comment','').strip(): raise ReviewError('CLASSIFICATION_REASON_REQUIRED')
    raw=review.live['portal']; previous=review.publication['portal-data.json']; articles=review.live['articles']
    matches=[r for r in raw['observations'] if digest(r['article']['article_id'])==row['article_hash'] and digest(r['src'])==row['url_hash']]
    if len(matches)!=1: raise ReviewError('NAME_MIGRATION_TARGET_MISSING_OR_AMBIGUOUS')
    images=[im for im in articles.get(row['article_hash'],{}).get('images',[]) if im['url_hash']==row['url_hash']]
    if len(images)!=1: raise ReviewError('NAME_MIGRATION_DUPLICATE_URL')
    evidence={'version':1,'operation':'rename_existing_unique_photo',
        'baseline_snapshot_sha256':review.publication['article-sync-snapshot.json']['sha256'],
        'article_hash':row['article_hash'],'url_hash':row['url_hash'],'observation_id':row['observation_id'],
        'old_name':row['current_name'],'proposed_name':d['proposed_name'],
        'raw_fingerprint':raw_fingerprint(matches[0],images[0]),'approved_at':d['decided_at'],
        'reason_sha256':digest(d['comment']),'approval':'explicit_human_name_confirmation'}
    manifest=validate_manifest({**evidence,'migration_id':payload_hash(evidence)})
    check_target(manifest,raw,previous,articles)
    return manifest


def preview(review,body):
    if not isinstance(body,dict) or set(body)!={'candidate_id','bundle_id'}: raise ReviewError('INVALID_INPUT')
    with LOCK:
        review.exception_preview=None
        if body['bundle_id']!=review.bundle_id: raise ReviewError('STALE_REVIEW')
        fresh=public_publication(refresh=True); live=live_capture(); review.assert_fresh(fresh,live)
        manifest=build_manifest(review,body['candidate_id'])
        result=validate_package(fresh,manifest)
        review.exception_preview={'manifest':manifest,'bundle_id':review.bundle_id,
            'validation':result,'approved':False}
        return {'ready':True,'migration_id':manifest['migration_id'],
            'old_name':manifest['old_name'],'proposed_name':manifest['proposed_name'],
            'observation_id':manifest['observation_id'],'identity':'same Atom article + exact globally unique image URL',
            'affected_pages':['図鑑','五十音','季節','特徴','詳細','観察記録'],
            'protected_references':'参照対象の写真は変更禁止。実生成で再検証済み。',
            'validation':result,'applied':False,'publication':'Draft PRのマージと日次同期成功後のみ反映'}


def approve(review,body):
    if not isinstance(body,dict) or set(body)!={'migration_id','confirm_old_name','confirm_new_name'}: raise ReviewError('INVALID_INPUT')
    with LOCK:
        package=review.exception_preview
        if not package or not package['validation']['ready']: raise ReviewError('EXCEPTION_PREVIEW_REQUIRED')
        m=package['manifest']
        if body!={'migration_id':m['migration_id'],'confirm_old_name':m['old_name'],'confirm_new_name':m['proposed_name']}:
            raise ReviewError('EXPLICIT_NAME_CONFIRMATION_MISMATCH')
        fresh=public_publication(refresh=True);live=live_capture();review.assert_fresh(fresh,live)
        if build_manifest(review,next(r['candidate_id'] for r in review.rows if r['observation_id']==m['observation_id']))!=m:
            raise ReviewError('STALE_REVIEW')
        package['approved']=False
        record={'event':'name_migration_explicitly_approved','at':datetime.now(timezone.utc).isoformat(),
                'migration_id':m['migration_id'],'application':'DRAFT_PR_REQUIRED_NOT_PUBLISHED'}
        review.audit.append(record);review._save()
        package['approved']=True
        return {'approved':True,'published':False,'migration_id':m['migration_id']}


def validate_changed_paths(paths,manifest):
    allowed='sync-migrations/photo-names/'+validate_manifest(manifest)['migration_id']+'.json'
    if paths != [allowed]: raise ReviewError('EXCEPTION_PR_PATHS_INVALID')
    return allowed


def create_pull_request(review,body):
    """Dedicated name-only worktree; existing Best/knowledge PR paths unchanged."""
    if body: raise ReviewError('INVALID_INPUT')
    from .git_workflow import run, repository_status
    from .core import ROOT, safe_branch_name
    import shutil
    import subprocess
    import tempfile
    import os
    with LOCK:
        package=review.exception_preview
        if not package or not package['approved']: raise ReviewError('EXPLICIT_MIGRATION_APPROVAL_REQUIRED')
        m=package['manifest'];validate_manifest(m)
        if not repository_status()['gh_authenticated']: raise ReviewError('GITHUB_AUTH_REQUIRED')
        if run(['git','status','--porcelain']).stdout.strip(): raise ReviewError('CLEAN_CHECKOUT_REQUIRED')
        run(['git','fetch','origin','main','gh-pages'])
        base=run(['git','rev-parse','origin/main']).stdout.strip()
        if run(['git','rev-parse','HEAD']).stdout.strip()!=base: raise ReviewError('FRESH_MAIN_CHECKOUT_REQUIRED')
        pub=public_publication();live=live_capture();review.assert_fresh(pub,live)
        if build_manifest(review,next(r['candidate_id'] for r in review.rows if r['observation_id']==m['observation_id']))!=m: raise ReviewError('STALE_REVIEW')
        directory=Path(tempfile.mkdtemp(prefix='kinoko-name-pr-'));work=directory/'work';added=False
        branch=safe_branch_name('photo-name')
        try:
            run(['git','worktree','add','-b',branch,str(work),'origin/main']);added=True
            path=validate_changed_paths(['sync-migrations/photo-names/'+m['migration_id']+'.json'],m)
            target=work/path;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            previous=directory/'previous';previous.mkdir()
            for name in ('portal-data.json','article-sync-snapshot.json','phase3c-production-status.json'):
                (previous/name).write_text(json.dumps(pub[name]),encoding='utf-8')
            # The real generator is imported from the fresh worktree, not a stale
            # server module. Bodies, reports and outputs stay outside git staging.
            import main
            env=os.environ.copy()
            env.update(HATENA_USER=main.HATENA_USER,HATENA_BLOG_ID=main.HATENA_BLOG_ID,HATENA_API_KEY=main.HATENA_API_KEY)
            generated=subprocess.run(['python','-m','article_sync','--previous',str(previous),
                '--output',str(directory/'candidate'),'--report',str(directory/'report.json')],
                cwd=work,env=env,capture_output=True,text=True)
            if generated.returncode: raise ReviewError('EXCEPTION_PR_REAL_GENERATION_BLOCKED')
            for command in (['python','-m','pytest','-q'],['python','-m','compileall','-q','.']):
                if run(command,cwd=work,check=False).returncode: raise ReviewError('EXCEPTION_PR_TEST_FAILED')
            for file in sorted((work/'tests').glob('*.js')):
                if run(['node',str(file)],cwd=work,check=False).returncode: raise ReviewError('EXCEPTION_PR_TEST_FAILED')
            # Remove only test-created, untracked public previews in this fresh,
            # disposable worktree before enforcing the single-file allow-list.
            for relative in run(['git','ls-files','--others','--exclude-standard','--','output'],cwd=work).stdout.splitlines():
                file=work/relative
                if file.is_file() and not file.is_symlink(): file.unlink()
            changed=sorted(set(run(['git','diff','--name-only'],cwd=work).stdout.splitlines()+
                run(['git','ls-files','--others','--exclude-standard'],cwd=work).stdout.splitlines()))
            validate_changed_paths(changed,m)
            run(['git','add','--',path],cwd=work)
            validate_changed_paths(run(['git','diff','--cached','--name-only'],cwd=work).stdout.splitlines(),m)
            run(['git','diff','--cached','--check'],cwd=work)
            # Last freshness check before any write to origin.
            run(['git','fetch','origin','main','gh-pages'])
            if run(['git','rev-parse','origin/main']).stdout.strip()!=base: raise ReviewError('STALE_MAIN')
            review.assert_fresh(public_publication(),live_capture())
            if json.loads(target.read_text(encoding='utf-8')) != m:
                raise ReviewError('EXCEPTION_PR_MANIFEST_CHANGED')
            staged_manifest = json.loads(run(['git','show',':'+path],cwd=work).stdout)
            if staged_manifest != m: raise ReviewError('EXCEPTION_PR_MANIFEST_CHANGED')
            run(['git','commit','-m','Apply explicitly reviewed unique photo name migration'],cwd=work)
            run(['git','push','-u','origin',branch],cwd=work)
            body_file=directory/'pr-body.md'
            body_file.write_text('## 個別の写真名修正\n\n対象ID: `'+m['observation_id']+'`\n\n'
                '同一記事・同一URL・単一出現の写真のみ。元のPhase3C根拠は変更しません。\n'
                '実生成・既存参照・pytest・JavaScript・差分検査済み。\n'
                '初回適用は記録した公開snapshotと一致する場合のみ。更新された場合は再レビューが必要です。\n'
                '通常の高信頼写真の自動追加は承認不要。merge/deployは未実施。\n',encoding='utf-8')
            result=run(['gh','pr','create','--base','main','--head',branch,'--draft',
                '--title','Apply reviewed photo name migration','--body-file',str(body_file)],cwd=work)
            review.audit.append({'event':'name_migration_draft_pr_created','migration_id':m['migration_id'],
                'at':datetime.now(timezone.utc).isoformat(),'application':'DRAFT_PR_NOT_PUBLISHED'})
            review._save();review.exception_preview=None
            return {'branch':branch,'url':result.stdout.strip(),'draft':True,'published':False}
        except (ReviewError,SyncError): raise
        except Exception: raise ReviewError('EXCEPTION_PR_FAILED') from None
        finally:
            if added: run(['git','worktree','remove','--force',str(work)],check=False)
            shutil.rmtree(directory,ignore_errors=True)
