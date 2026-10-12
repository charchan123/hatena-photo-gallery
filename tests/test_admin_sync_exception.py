"""Explicit local confirmation and independent, production-integrated preview."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from pathlib import Path

import article_sync as sync
from admin.sync import SyncReview,ReviewError
from admin import sync_exception as admin_exc
from test_sync_exceptions import setup
from test_sync_automatic_updates import publication


@pytest.fixture
def reviewed(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path)
    pub=publication(previous)
    live={'portal':deepcopy(pub['portal-data.json']),
        'articles':deepcopy(pub['article-sync-snapshot.json']['payload']['articles']),
        'photos':{},'excluded_draft_hashes':[]}
    review=SyncReview(tmp_path/'review');review.install(pub,live)
    row=next(r for r in review.rows if r['article_hash']==sync.digest('B'))
    review.decide({'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id,
        'decision':'propose_name','proposed_name':'ベニテングタケ','comment':'人間が写真の特徴を確認しました'})
    monkeypatch.setattr(admin_exc,'public_publication',lambda **k:pub)
    monkeypatch.setattr(admin_exc,'live_capture',lambda:live)
    return review,row,pub,live


def test_independent_real_preview_explicit_confirmation_and_persisted_history(reviewed):
    review,row,pub,live=reviewed
    p=admin_exc.preview(review,{'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id})
    assert p['ready'] and p['validation']['name_migration_count']==1
    assert not p['applied'] and not review.exception_preview['approved']
    with pytest.raises(ReviewError,match='MISMATCH'):
        admin_exc.approve(review,{'migration_id':p['migration_id'],'confirm_old_name':'違う写真','confirm_new_name':p['proposed_name']})
    body={'migration_id':p['migration_id'],'confirm_old_name':p['old_name'],'confirm_new_name':p['proposed_name']}
    assert admin_exc.approve(review,body)=={'approved':True,'published':False,'migration_id':p['migration_id']}
    loaded=SyncReview(review.root)
    assert loaded.audit[-1]['event']=='name_migration_explicitly_approved'
    assert loaded.exception_preview is None  # Restart requires a fresh preview.
    review.decide({'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id,'decision':'pending'})
    assert review.exception_preview is None


@pytest.mark.parametrize('damage',['no_live','no_reason','unknown_name','new_auto','arbitrary_input','stale','snapshot'])
def test_approval_boundary_and_unsupported_targets(reviewed,damage,monkeypatch):
    review,row,pub,live=reviewed
    if damage=='no_live':review.live=None
    elif damage=='no_reason':review.decisions[row['candidate_id']]['comment']=''
    elif damage=='unknown_name':review.decisions[row['candidate_id']]['proposed_name']='推測のキノコ'
    elif damage=='new_auto':row['name_migration_available']=False
    elif damage=='stale':review.decisions[row['candidate_id']]['bundle_id']='x'
    elif damage=='snapshot':pub['article-sync-snapshot.json']['sha256']='x'
    body={'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id}
    if damage=='arbitrary_input':body['file']='../../secret'
    with pytest.raises((ReviewError,sync.SyncError)):
        if damage=='snapshot':
            review.publication=deepcopy(pub);review.publication['article-sync-snapshot.json']['sha256']='y'
        admin_exc.preview(review,body)
    assert review.exception_preview is None


def test_single_file_allow_list_and_pr_without_approval_rejected(reviewed):
    review,row,pub,live=reviewed;m=admin_exc.build_manifest(review,row['candidate_id'])
    path='sync-migrations/photo-names/'+m['migration_id']+'.json'
    assert admin_exc.validate_changed_paths([path],m)==path
    for paths in ([],[path,'data/best-shots.json'],['../../secret'],['sync-migrations/photo-names/other.json']):
        with pytest.raises(ReviewError):admin_exc.validate_changed_paths(paths,m)
    with pytest.raises(ReviewError,match='EXPLICIT_MIGRATION_APPROVAL_REQUIRED'):admin_exc.create_pull_request(review,{})
    with pytest.raises(ReviewError,match='INVALID_INPUT'):admin_exc.create_pull_request(review,{'url':'https://attacker.example'})


def test_stale_after_preview_cannot_be_approved(reviewed):
    review,row,pub,live=reviewed
    p=admin_exc.preview(review,{'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id})
    live['articles'][row['article_hash']]['updated_hash']=sync.digest('changed')
    with pytest.raises(ReviewError,match='STALE_LIVE'):
        admin_exc.approve(review,{'migration_id':p['migration_id'],'confirm_old_name':p['old_name'],'confirm_new_name':p['proposed_name']})
    assert not review.exception_preview['approved']


def test_separate_pr_route_requires_fresh_clean_main_and_keeps_existing_allowlist(reviewed,monkeypatch):
    import admin.git_workflow as workflow
    review,row,pub,live=reviewed
    p=admin_exc.preview(review,{'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id})
    admin_exc.approve(review,{'migration_id':p['migration_id'],'confirm_old_name':p['old_name'],'confirm_new_name':p['proposed_name']})
    calls=[]
    monkeypatch.setattr(workflow,'repository_status',lambda:{'gh_authenticated':True})
    def run(args,**kw):
        calls.append(args)
        if args==['git','status','--porcelain']:return SimpleNamespace(stdout='')
        if args==['git','rev-parse','origin/main']:return SimpleNamespace(stdout='a'*40)
        if args==['git','rev-parse','HEAD']:return SimpleNamespace(stdout='b'*40)
        return SimpleNamespace(stdout='',returncode=0)
    monkeypatch.setattr(workflow,'run',run)
    with pytest.raises(ReviewError,match='FRESH_MAIN'):admin_exc.create_pull_request(review,{})
    assert not any('push' in c or 'commit' in c for c in calls)
    source=Path('admin/git_workflow.py').read_text()
    old_path=source[:source.index('def validate_knowledge_changed_paths')]
    assert 'sync-migrations' not in old_path


def test_exceptions_are_not_a_general_new_photo_gate():
    source=Path('sync_exceptions.py').read_text()
    assert 'rename_existing_unique_photo' in source
    assert 'gate_new_photos' not in Path('article_sync.py').read_text()
    assert not Path('sync-reviews/approvals.json').exists()


def test_dedicated_pr_success_order_draft_and_single_file_staging(reviewed,monkeypatch):
    import admin.git_workflow as workflow
    import subprocess
    review,row,pub,live=reviewed
    preview=admin_exc.preview(review,{'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id})
    admin_exc.approve(review,{'migration_id':preview['migration_id'],'confirm_old_name':preview['old_name'],'confirm_new_name':preview['proposed_name']})
    m=deepcopy(review.exception_preview['manifest']);path='sync-migrations/photo-names/'+m['migration_id']+'.json'
    calls=[];monkeypatch.setattr(workflow,'repository_status',lambda:{'gh_authenticated':True})
    def command(args,**kw):
        calls.append(args)
        if args[:3]==['git','worktree','add']:
            work=Path(args[-2]);(work/'tests').mkdir(parents=True);(work/'tests/example.js').write_text('')
        out=''
        if args[:2]==['git','rev-parse']:out='a'*40
        if args[:2]==['git','ls-files']:out=path if '--' not in args else ''
        if args==['git','diff','--cached','--name-only']:out=path
        if args==['git','show',':'+path]:out=json.dumps(m)
        if args[:3]==['gh','pr','create']:out='https://github.com/example/pull/1'
        return SimpleNamespace(stdout=out,returncode=0)
    monkeypatch.setattr(workflow,'run',command)
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0))
    result=admin_exc.create_pull_request(review,{})
    assert result['draft'] and not result['published']
    staged=next(c for c in calls if c[:2]==['git','add']);assert staged==['git','add','--',path]
    assert any(c==['python','-m','pytest','-q'] for c in calls)
    assert any(c[:2]==['node',str(Path(c[1]))] for c in calls if c[0]=='node')
    pr=next(c for c in calls if c[:3]==['gh','pr','create']);assert '--draft' in pr and '--body-file' in pr
    assert sum(c[:3]==['git','fetch','origin'] for c in calls)==2
    assert not any(c[:2]==['git','merge'] or 'workflow_dispatch' in c for c in calls)


def test_invalid_local_manifest_cannot_hide_last_successful_public_state(reviewed,monkeypatch,tmp_path):
    import sync_exceptions as exc
    review,row,pub,live=reviewed
    directory=tmp_path/'corrupt';directory.mkdir();(directory/'bad.json').write_text('{}')
    monkeypatch.setattr(exc,'DIRECTORY',directory)
    review.install(pub,None)
    assert review.dashboard()['available'] and not review.dashboard()['live_review_available']
    assert review.dashboard()['summary']['gallery_photos']==2
    with pytest.raises(sync.SyncError):exc.load_manifests()
