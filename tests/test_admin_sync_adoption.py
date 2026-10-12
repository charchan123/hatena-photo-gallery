"""Local UI/API boundaries plus independent real generation preview."""
from copy import deepcopy
from pathlib import Path
import pytest

import article_sync as sync
from admin.sync import SyncReview,ReviewError
from admin import sync_adoption as app
from test_sync_adoptions import setup,sources
from test_sync_automatic_updates import publication


@pytest.fixture
def reviewed(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path)
    pub=publication(previous);occ=sources(main,pub)
    live={'portal':deepcopy(pub['portal-data.json']),'articles':deepcopy(pub['article-sync-snapshot.json']['payload']['articles']),
        'photos':{k:{'thumbnail':v['src'],'article_title':v['article'].get('title'),'published':v['article'].get('published')} for k,v in occ.items()},
        'source_occurrences':occ,'excluded_draft_hashes':[]}
    review=SyncReview(tmp_path/'local');review.install(pub,live)
    row=next(r for r in review.rows if r['unlisted_public_image'])
    monkeypatch.setattr(app,'public_publication',lambda **k:pub);monkeypatch.setattr(app,'live_capture',lambda:live)
    monkeypatch.setattr(app,'image_hash',lambda src:sync.digest('fixture bytes '+src))
    return review,row,pub,live


def classify(review,row,decision='classify_named',name='ヒラタケ'):
    return review.decide({'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id,
        'decision':decision,'proposed_name':name,'comment':'人間が写真で確認した根拠'})


def test_unlisted_is_distinct_from_published_unknown_and_legacy_count(reviewed):
    r,row,pub,live=reviewed
    assert row['adoption_available'] and row['current_name'] is None and not row['protected_existing']
    assert row['group']=='unlisted' and not row['is_new_occurrence']
    assert r.dashboard()['summary']['unlisted_image_count']==1
    assert r.dashboard()['summary']['new_unlisted_image_count']==0
    assert r.page(group='published')['total']==1


@pytest.mark.parametrize('decision,name',[('classify_named','ヒラタケ'),('classify_unknown','')])
def test_human_classification_real_preview_explicit_approval_and_next_state(reviewed,decision,name):
    r,row,pub,live=reviewed;classify(r,row,decision,name)
    persisted=SyncReview(r.root);persisted.install(pub,live)
    assert persisted.decisions==r.decisions
    p=app.preview(r,{'candidate_id':row['candidate_id'],'bundle_id':r.bundle_id})
    assert p['ready'] and p['validation']['manual_adoptions_applied_this_run']==1
    assert p['validation']['added_photos']==0 and not r.adoption_preview['approved']
    with pytest.raises(ReviewError):app.approve(r,{'migration_id':p['migration_id'],'confirm_name':'違う写真','confirm_adoption':True})
    assert app.approve(r,{'migration_id':p['migration_id'],'confirm_name':p['gallery_name'],'confirm_adoption':True})['approved']
    assert r.audit[-1]['event']=='manual_photo_adoption_explicitly_approved'
    classify(r,row,'hold','');assert r.adoption_preview is None
    assert r.dashboard()['groups']['held']==1


def test_non_mushroom_hold_confirmation_never_allow_adoption(reviewed):
    r,row,pub,live=reviewed
    for decision in ('classify_non_mushroom','hold','confirmed','no_change','pending'):
        classify(r,row,decision,'')
        with pytest.raises(ReviewError):app.build_manifest(r,row['candidate_id'])
    assert live['portal']==pub['portal-data.json']
    assert not r.adoption_preview


@pytest.mark.parametrize('damage',['id','body_path','url','taxonomy','no_reason','published_photo','stale'])
def test_invalid_classification_input_is_rejected(reviewed,damage):
    r,row,pub,live=reviewed
    b={'candidate_id':row['candidate_id'],'bundle_id':r.bundle_id,'decision':'classify_named','proposed_name':'ヒラタケ','comment':'根拠'}
    if damage=='id':b['candidate_id']='../../secret'
    elif damage=='body_path':b['path']='../../data/sources.json'
    elif damage=='url':b['src']='https://attacker.example/image'
    elif damage=='taxonomy':b['proposed_name']='推測で新登録'
    elif damage=='no_reason':b['comment']=''
    elif damage=='published_photo':b['candidate_id']=next(x['candidate_id'] for x in r.rows if x['protected_existing'])
    else:b['bundle_id']='a'*64
    with pytest.raises(ReviewError):r.decide(b)
    assert not r.decisions


def test_stale_after_preview_and_content_change_after_review_are_rejected(reviewed,monkeypatch):
    r,row,pub,live=reviewed;classify(r,row)
    p=app.preview(r,{'candidate_id':row['candidate_id'],'bundle_id':r.bundle_id})
    monkeypatch.setattr(app,'image_hash',lambda _:sync.digest('different bytes'))
    with pytest.raises(ReviewError,match='IMAGE_OR_REVIEW_CHANGED'):
        app.approve(r,{'migration_id':p['migration_id'],'confirm_name':p['gallery_name'],'confirm_adoption':True})
    assert not r.adoption_preview['approved']
    live['articles'][row['article_hash']]['updated_hash']=sync.digest('new timestamp')
    with pytest.raises(ReviewError,match='STALE_LIVE'):
        app.approve(r,{'migration_id':p['migration_id'],'confirm_name':p['gallery_name'],'confirm_adoption':True})


def test_adoption_pr_one_file_path_type_and_explicit_approval_required(reviewed):
    r,row,pub,live=reviewed;classify(r,row);m=app.build_manifest(r,row['candidate_id'])
    path='sync-migrations/photo-adoptions/'+m['migration_id']+'.json'
    assert app.validate_changed_paths([path],m)==path
    for files in (['sync-migrations/photo-names/'+m['migration_id']+'.json'],[path,'data/best-shots.json'],['../../path'],[]):
        with pytest.raises(ReviewError):app.validate_changed_paths(files,m)
    with pytest.raises(ReviewError):app.create_pull_request(r,{})
    with pytest.raises(ReviewError):app.create_pull_request(r,{'path':path})
    assert '--adoption-only' not in Path('admin/sync_adoption.py').read_text()


def test_dedicated_adoption_pr_stages_one_file_rechecks_and_stays_draft(reviewed,monkeypatch):
    import admin.git_workflow as workflow
    import subprocess
    from types import SimpleNamespace
    r,row,pub,live=reviewed;classify(r,row)
    p=app.preview(r,{'candidate_id':row['candidate_id'],'bundle_id':r.bundle_id})
    app.approve(r,{'migration_id':p['migration_id'],'confirm_name':p['gallery_name'],'confirm_adoption':True})
    m=deepcopy(r.adoption_preview['manifest']);path='sync-migrations/photo-adoptions/'+m['migration_id']+'.json';calls=[]
    monkeypatch.setattr(workflow,'repository_status',lambda:{'gh_authenticated':True})
    def run(args,**kw):
        calls.append(args);out=''
        if args[:3]==['git','worktree','add']:
            work=Path(args[-2]);(work/'tests').mkdir(parents=True);(work/'tests/test.js').write_text('')
        if args[:2]==['git','rev-parse']:out='a'*40
        if args[:2]==['git','ls-files']:out='' if '--' in args else path
        if args==['git','diff','--cached','--name-only']:out=path
        if args==['git','show',':'+path]:out=__import__('json').dumps(m)
        if args[:3]==['gh','pr','create']:out='https://github.com/example/pull/1'
        return SimpleNamespace(stdout=out,returncode=0)
    monkeypatch.setattr(workflow,'run',run);monkeypatch.setattr(subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0))
    result=app.create_pull_request(r,{})
    assert result['draft'] and not result['published']
    assert next(c for c in calls if c[:2]==['git','add'])==['git','add','--',path]
    assert '--draft' in next(c for c in calls if c[:3]==['gh','pr','create'])
    assert ['python','-m','pytest','-q'] in calls and ['git','diff','--cached','--check'] in calls
    assert r.audit[-1]['event']=='manual_photo_adoption_draft_pr_created'
    assert not r.adoption_preview


def test_http_adoption_paths_reject_csrf_foreign_origin_and_arbitrary_fields(reviewed,monkeypatch):
    import json,threading,urllib.request,urllib.error
    from admin.server import AdminServer,Handler
    r,row,pub,live=reviewed
    monkeypatch.setattr('admin.server.load_portal_data',lambda:(pub['portal-data.json'],'fixture'))
    monkeypatch.setattr('admin.server.SyncReview',lambda:r)
    server=AdminServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    try:
        for endpoint in ('adoption-preview','adoption-approve','adoption-pr'):
            for headers in ({},{'X-CSRF-Token':server.csrf_token,'Origin':'https://attacker.example'}):
                request=urllib.request.Request(base+'/api/sync/'+endpoint,data=b'{}',headers=headers)
                with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
                assert e.value.code==403
            request=urllib.request.Request(base+'/api/sync/'+endpoint,data=json.dumps({'path':'../../secret','url':'https://attacker.example'}).encode(),headers={'X-CSRF-Token':server.csrf_token})
            with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
            assert e.value.code==400 and 'secret' not in e.value.read().decode()
    finally:server.shutdown();server.server_close();thread.join()


def test_numeric_confirmation_is_not_explicit_boolean_consent(reviewed):
    r,row,pub,live=reviewed;classify(r,row)
    p=app.preview(r,{'candidate_id':row['candidate_id'],'bundle_id':r.bundle_id})
    with pytest.raises(ReviewError):app.approve(r,{'migration_id':p['migration_id'],'confirm_name':p['gallery_name'],'confirm_adoption':1})
    assert not r.adoption_preview['approved']


def test_private_validation_code_uses_real_generator_but_no_source_bodies_escape(reviewed,monkeypatch,tmp_path):
    from admin.sync import PRIVATE_VALIDATION_CODE
    import sys
    r,row,pub,live=reviewed;classify(r,row)
    # The reviewed manifest has been independently validated; install it in the
    # fixture migration directory. Execute the SAME fixed validation code used
    # by the fresh-worktree subprocess, with transport fixtures only.
    m=app.build_manifest(r,row['candidate_id'])
    import sync_adoptions
    sync.write_json(sync_adoptions.DIRECTORY/(m['migration_id']+'.json'),m)
    previous=tmp_path/'private-previous';previous.mkdir()
    for name in ('portal-data.json','article-sync-snapshot.json','phase3c-production-status.json'):
        sync.write_json(previous/name,pub[name])
    candidate=tmp_path/'candidate';report=tmp_path/'report.json'
    import main
    article_path=main.ARTICLES_DIR;metadata_path=main.ARTICLE_METADATA_FILE
    original_files={p:p.read_bytes() for p in Path(article_path).rglob('*') if p.is_file()}
    monkeypatch.setattr(sys,'argv',['validator',str(previous),str(candidate),str(report)])
    with pytest.raises(SystemExit) as e:exec(compile(PRIVATE_VALIDATION_CODE,'private-validation','exec'),{})
    assert e.value.code==0 and sync.read_json(report)['manual_adoptions_applied_this_run']==1
    assert main.ARTICLES_DIR==article_path and main.ARTICLE_METADATA_FILE==metadata_path
    assert original_files=={p:p.read_bytes() for p in Path(article_path).rglob('*') if p.is_file()}
    assert (candidate/'portal-data.json').exists() and not (candidate/'articles').exists()
