"""Sync-only Draft PR route. Existing best-shot/knowledge allowlists stay intact."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

from article_sync import payload_hash
from sync_review import APPROVAL_PATH
from .core import ROOT, safe_branch_name
from .git_workflow import GitWorkflowError, repository_status, run
from .sync import LOCK, ReviewError, live_capture, public_publication


def validate_paths(paths):
    if set(paths) != {APPROVAL_PATH}: raise ReviewError('SYNC_PR_PATH_NOT_ALLOWED')


def create_sync_pull_request(review):
    with LOCK:
        if not repository_status().get('gh_authenticated'): raise ReviewError('GITHUB_AUTH_REQUIRED')
        if run(['git','status','--porcelain']).stdout.strip(): raise ReviewError('CLEAN_CHECKOUT_REQUIRED')
        run(['git','fetch','origin','main','gh-pages'])
        fresh = run(['git','rev-parse','origin/main']).stdout.strip()
        if run(['git','rev-parse','HEAD']).stdout.strip() != fresh: raise ReviewError('FRESH_MAIN_CHECKOUT_REQUIRED')
        publication = public_publication(); review.assert_fresh(publication,live_capture())
        manifest = review.package()
        if not review.last_preview or review.last_preview.get('manifest_sha256') != payload_hash(manifest):
            raise ReviewError('VALIDATED_PREVIEW_REQUIRED')
        branch=safe_branch_name('sync-review'); directory=Path(tempfile.mkdtemp(prefix='kinoko-sync-pr-')); added=False
        try:
            run(['git','worktree','add','-b',branch,str(directory),'origin/main']); added=True
            destination=directory/APPROVAL_PATH
            if destination.is_symlink(): raise ReviewError('SYNC_PR_PATH_NOT_ALLOWED')
            destination.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            # Execute the actual production wrapper from the fresh worktree.
            with tempfile.TemporaryDirectory(prefix='kinoko-sync-validate-') as temp:
                previous=Path(temp)/'previous'; previous.mkdir()
                for name in ('portal-data.json','article-sync-snapshot.json','phase3c-production-status.json'):
                    (previous/name).write_text(json.dumps(publication[name]),encoding='utf-8')
                run([sys.executable,'article_sync.py','--previous',str(previous),'--output',str(Path(temp)/'site'),
                     '--report',str(Path(temp)/'report.json')],cwd=directory)
            run([sys.executable,'-m','pytest','-q'],cwd=directory)
            for test in sorted((directory/'tests').glob('*.js')): run(['node',str(test)],cwd=directory)
            run([sys.executable,'-m','compileall','-q','.'],cwd=directory)
            # Only the single fixed review manifest can be staged; tests may emit
            # untracked output, never stage it or widen the allow-list.
            tracked=run(['git','diff','--name-only'],cwd=directory).stdout.splitlines()
            validate_paths(tracked)
            run(['git','add','--',APPROVAL_PATH],cwd=directory)
            validate_paths(run(['git','diff','--cached','--name-only'],cwd=directory).stdout.splitlines())
            run(['git','diff','--cached','--check'],cwd=directory)
            # Slow tests and generation are not a licence to use stale approvals.
            run(['git','fetch','origin','main','gh-pages'])
            if fresh != run(['git','rev-parse','origin/main']).stdout.strip(): raise ReviewError('STALE_MAIN')
            review.assert_fresh(public_publication(),live_capture())
            run(['git','commit','-m','Approve reviewed safe new gallery photos'],cwd=directory)
            run(['git','push','-u','origin',branch],cwd=directory)
            body=("## 同期レビュー\n既存Phase 3C高信頼写真の追加だけを人間が承認。\n"
                  "既存写真の名前・URL・ID・削除、知識データは変更しません。\n\n"
                  f"- 基準snapshot: `{publication['article-sync-snapshot.json']['sha256']}`\n"
                  f"- approval manifest: `{payload_hash(manifest)}`\n"
                  "- 実生成・参照保護ゲート・全pytest・全JS・compileall・diff-check: PASS\n"
                  "- merge/deploy/Hatena変更: 未実施\n")
            file=Path(directory)/'.git-sync-pr-body.txt'; file.write_text(body,encoding='utf-8')
            response=run(['gh','pr','create','--draft','--base','main','--head',branch,
                          '--title','Approve reviewed article/photo additions','--body-file',str(file)],cwd=directory)
            url=response.stdout.strip()
            # Receipt is local; avoid accidentally making duplicate PRs.
            review.audit.append({'event':'draft_pr_created','bundle_id':review.bundle_id,'at':__import__('admin.sync',fromlist=['now']).now(),'url':url})
            for cid, decision in list(review.decisions.items()):
                if decision.get('bundle_id')==review.bundle_id and decision.get('decision')=='adopt':
                    review.decisions[cid]={**decision,'application':'draft_pr_created'}
            review._save(); review.last_preview=None
            return {'branch':branch,'url':url,'draft':True}
        except GitWorkflowError: raise ReviewError('SYNC_PR_VALIDATION_OR_GIT_FAILED') from None
        finally:
            if added: run(['git','worktree','remove','--force',str(directory)],check=False)
            shutil.rmtree(directory,ignore_errors=True)
