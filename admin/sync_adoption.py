"""Human classification and explicit adoption; independent from name corrections."""
from datetime import datetime,timezone
from pathlib import Path
import json
from article_sync import digest,payload_hash,SyncError
from sync_adoptions import validate_manifest,stable_id,check_target,image_hash,pending_replacement
from .sync import LOCK,ReviewError,public_publication,live_capture,validate_package


def row_for(review,candidate_id):
    return next((r for r in review.rows if r['candidate_id']==candidate_id),None)


def build_manifest(review,candidate_id):
    row=row_for(review,candidate_id);d=review.decisions.get(candidate_id)
    if not review.live or not row or not row.get('adoption_available') or not d or d['decision'] not in {'classify_named','classify_unknown'}:
        raise ReviewError('EXPLICIT_UNLISTED_CLASSIFICATION_REQUIRED')
    if d['bundle_id']!=review.bundle_id or d['fingerprint']!=row['fingerprint']:raise ReviewError('STALE_REVIEW')
    if not d.get('comment','').strip():raise ReviewError('CLASSIFICATION_REASON_REQUIRED')
    source=review.live['source_occurrences'].get((row['article_hash'],row['url_hash'],row['ordinal']))
    if not source:raise ReviewError('ADOPTION_PUBLIC_SOURCE_MISSING')
    decision='named_mushroom' if d['decision']=='classify_named' else 'unknown_mushroom'
    fields={'version':1,'operation':'adopt_unique_public_mushroom_photo',
        'baseline_snapshot_sha256':review.publication['article-sync-snapshot.json']['sha256'],
        'article_hash':row['article_hash'],'url_hash':row['url_hash'],'ordinal':row['ordinal'],
        'observation_id':stable_id(row['article_hash'],row['url_hash'],row['ordinal']),
        'decision':decision,'gallery_name':d['proposed_name'],'raw_fingerprint':source['fingerprint'],
        'image_content_sha256':image_hash(source['src']),'approved_at':d['decided_at'],
        'reason_sha256':digest(d['comment']),'approval':'explicit_human_photo_adoption'}
    m=validate_manifest({**fields,'migration_id':payload_hash(fields)})
    check_target(m,review.live['portal'],review.publication['portal-data.json'],review.live['source_occurrences'],verify_image=False)
    return m


def preview(review,body):
    if not isinstance(body,dict) or set(body)!={'candidate_id','bundle_id'}:raise ReviewError('INVALID_INPUT')
    with LOCK:
        review.adoption_preview=None
        if body['bundle_id']!=review.bundle_id:raise ReviewError('STALE_REVIEW')
        pub=public_publication(refresh=True);live=live_capture();review.assert_fresh(pub,live)
        m=build_manifest(review,body['candidate_id'])
        replacement=pending_replacement(m,pub['portal-data.json'],pub['article-sync-snapshot.json']['payload'])
        result=validate_package(pub,adoption=m,replacement=replacement)
        review.adoption_preview={'manifest':m,'candidate_id':body['candidate_id'],'bundle_id':review.bundle_id,'validation':result,'approved':False,'replacement':replacement}
        return {'ready':True,'migration_id':m['migration_id'],'decision':m['decision'],
            'gallery_name':m['gallery_name'],'observation_id':m['observation_id'],
            'validation':result,'published':False,'replaces_unapplied_instruction':replacement['migration_id'] if replacement else None,'affected_pages':['図鑑','五十音','季節','特徴','詳細','観察記録']}


def approve(review,body):
    if not isinstance(body,dict) or set(body)!={'migration_id','confirm_name','confirm_adoption'}:raise ReviewError('INVALID_INPUT')
    with LOCK:
        p=review.adoption_preview
        if not p or not p['validation']['ready']:raise ReviewError('ADOPTION_PREVIEW_REQUIRED')
        m=p['manifest']
        if body.get('confirm_adoption') is not True or body!={'migration_id':m['migration_id'],'confirm_name':m['gallery_name'],'confirm_adoption':True}:raise ReviewError('ADOPTION_EXPLICIT_CONFIRMATION_MISMATCH')
        pub=public_publication(refresh=True);live=live_capture();review.assert_fresh(pub,live)
        if build_manifest(review,p['candidate_id'])!=m:raise ReviewError('ADOPTION_IMAGE_OR_REVIEW_CHANGED')
        if pending_replacement(m,pub['portal-data.json'],pub['article-sync-snapshot.json']['payload'])!=p['replacement']:raise ReviewError('ADOPTION_PENDING_REPLACEMENT_CHANGED')
        p['approved']=False
        review.audit.append({'event':'manual_photo_adoption_explicitly_approved','candidate_id':p['candidate_id'],
            'migration_id':m['migration_id'],'at':datetime.now(timezone.utc).isoformat(),'application':'DRAFT_PR_REQUIRED_NOT_PUBLISHED'})
        review._save();p['approved']=True
        return {'approved':True,'published':False,'migration_id':m['migration_id']}


def validate_changed_paths(paths,m,replacement=None):
    path='sync-migrations/photo-adoptions/'+validate_manifest(m)['migration_id']+'.json'
    allowed=[path]
    if replacement is not None:
        validate_manifest(replacement)
        if replacement['observation_id']!=m['observation_id'] or replacement['migration_id']==m['migration_id']:raise ReviewError('ADOPTION_PR_PATHS_INVALID')
        allowed.append('sync-migrations/photo-adoptions/'+replacement['migration_id']+'.json')
    if sorted(paths)!=sorted(allowed):raise ReviewError('ADOPTION_PR_PATHS_INVALID')
    return path


def create_pull_request(review,body):
    """Dedicated adoption-only worktree; existing Best/knowledge PR paths unchanged."""
    if body: raise ReviewError('INVALID_INPUT')
    from .git_workflow import run, repository_status
    from .core import ROOT, safe_branch_name
    import shutil
    import subprocess
    import tempfile
    import os
    with LOCK:
        package=review.adoption_preview
        if not package or not package['approved']: raise ReviewError('EXPLICIT_MIGRATION_APPROVAL_REQUIRED')
        m=package['manifest'];validate_manifest(m)
        if not repository_status()['gh_authenticated']: raise ReviewError('GITHUB_AUTH_REQUIRED')
        if run(['git','status','--porcelain']).stdout.strip(): raise ReviewError('CLEAN_CHECKOUT_REQUIRED')
        run(['git','fetch','origin','main','gh-pages'])
        base=run(['git','rev-parse','origin/main']).stdout.strip()
        if run(['git','rev-parse','HEAD']).stdout.strip()!=base: raise ReviewError('FRESH_MAIN_CHECKOUT_REQUIRED')
        pub=public_publication();live=live_capture();review.assert_fresh(pub,live)
        if build_manifest(review,package['candidate_id'])!=m: raise ReviewError('STALE_REVIEW')
        replacement=pending_replacement(m,pub['portal-data.json'],pub['article-sync-snapshot.json']['payload'])
        if replacement!=package['replacement']:raise ReviewError('ADOPTION_PENDING_REPLACEMENT_CHANGED')
        directory=Path(tempfile.mkdtemp(prefix='kinoko-adoption-pr-'));work=directory/'work';added=False
        branch=safe_branch_name('photo-adoption')
        try:
            run(['git','worktree','add','-b',branch,str(work),'origin/main']);added=True
            paths=['sync-migrations/photo-adoptions/'+m['migration_id']+'.json']
            if replacement is not None: paths.append('sync-migrations/photo-adoptions/'+replacement['migration_id']+'.json')
            path=validate_changed_paths(paths,m,replacement)
            if replacement is not None:
                old_file=work/('sync-migrations/photo-adoptions/'+replacement['migration_id']+'.json')
                if json.loads(old_file.read_text(encoding='utf-8'))!=replacement:raise ReviewError('ADOPTION_PENDING_REPLACEMENT_CHANGED')
                old_file.unlink()
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
            from .sync import generate_in_worktree
            generated=generate_in_worktree(work,previous,directory/'candidate',directory/'report.json',env)
            if generated.returncode: raise ReviewError('ADOPTION_PR_REAL_GENERATION_BLOCKED')
            for command in (['python','-m','pytest','-q'],['python','-m','compileall','-q','.']):
                if run(command,cwd=work,check=False).returncode: raise ReviewError('ADOPTION_PR_TEST_FAILED')
            for file in sorted((work/'tests').glob('*.js')):
                if run(['node',str(file)],cwd=work,check=False).returncode: raise ReviewError('ADOPTION_PR_TEST_FAILED')
            # Remove only test-created, untracked public previews in this fresh,
            # disposable worktree before enforcing the single-file allow-list.
            for relative in run(['git','ls-files','--others','--exclude-standard','--','output'],cwd=work).stdout.splitlines():
                file=work/relative
                if file.is_file() and not file.is_symlink(): file.unlink()
            changed=sorted(set(run(['git','diff','--name-only'],cwd=work).stdout.splitlines()+
                run(['git','ls-files','--others','--exclude-standard'],cwd=work).stdout.splitlines()))
            validate_changed_paths(changed,m,replacement)
            run(['git','add','--',*paths],cwd=work)
            validate_changed_paths(run(['git','diff','--cached','--name-only'],cwd=work).stdout.splitlines(),m,replacement)
            run(['git','diff','--cached','--check'],cwd=work)
            # Last freshness check before any write to origin.
            run(['git','fetch','origin','main','gh-pages'])
            if run(['git','rev-parse','origin/main']).stdout.strip()!=base: raise ReviewError('STALE_MAIN')
            review.assert_fresh(public_publication(),live_capture())
            if build_manifest(review,package['candidate_id'])!=m: raise ReviewError('ADOPTION_IMAGE_OR_REVIEW_CHANGED')
            if pending_replacement(m,review.publication['portal-data.json'],review.publication['article-sync-snapshot.json']['payload'])!=replacement:raise ReviewError('ADOPTION_PENDING_REPLACEMENT_CHANGED')
            if json.loads(target.read_text(encoding='utf-8')) != m:
                raise ReviewError('ADOPTION_PR_MANIFEST_CHANGED')
            staged_manifest = json.loads(run(['git','show',':'+path],cwd=work).stdout)
            if staged_manifest != m: raise ReviewError('ADOPTION_PR_MANIFEST_CHANGED')
            run(['git','commit','-m','Apply explicitly reviewed unique public photo adoption'],cwd=work)
            run(['git','push','-u','origin',branch],cwd=work)
            body_file=directory/'pr-body.md'
            body_file.write_text('## 個別の未収録写真採用\n\n対象ID: `'+m['observation_id']+'`\n\n'
                '同一記事・同一URL・単一出現の写真のみ。画像本体のハッシュも検証します。元のPhase3C根拠は変更しません。\n'
                '実生成・既存参照・pytest・JavaScript・差分検査済み。\n'
                '初回適用は記録した公開snapshotと一致する場合のみ。更新された場合は再レビューが必要です。\n'
                '通常の高信頼写真の自動追加は承認不要。merge/deployは未実施。\n',encoding='utf-8')
            result=run(['gh','pr','create','--base','main','--head',branch,'--draft',
                '--title','Adopt explicitly reviewed public mushroom photo','--body-file',str(body_file)],cwd=work)
            review.audit.append({'event':'manual_photo_adoption_draft_pr_created','migration_id':m['migration_id'],
                'at':datetime.now(timezone.utc).isoformat(),'application':'DRAFT_PR_NOT_PUBLISHED','replaced_unapplied_migration':replacement['migration_id'] if replacement else None})
            review._save();review.adoption_preview=None
            return {'branch':branch,'url':result.stdout.strip(),'draft':True,'published':False}
        except (ReviewError,SyncError): raise
        except Exception: raise ReviewError('ADOPTION_PR_FAILED') from None
        finally:
            if added: run(['git','worktree','remove','--force',str(work)],check=False)
            shutil.rmtree(directory,ignore_errors=True)
