"""Sync review contracts: no network, no real secrets, no remote writes."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import urllib.request
import urllib.error

import pytest

import article_sync as sync
from sync_review import (HEADER, APPROVAL_PATH, gate_new_photos, load_approvals,
                         validate_approvals, occurrence_rows)
from admin.sync import SyncReview, ReviewError, candidates, safe_url, isolated_generator
from admin.sync_git import validate_paths, create_sync_pull_request
from test_article_sync import photo, portal, entry, STAMP


@pytest.fixture
def source(tmp_path):
    before=portal(photo())
    before['observations'][0]['src']='https://cdn-ak.f.st-hatena.com/images/a.jpg'
    before['observations'][0]['article'].update(title='公開記事A',url='https://exsudoporus-ruber.hatenablog.jp/entry/A',published=STAMP,updated=STAMP)
    articles={sync.digest('article-A'):entry(before['observations'][0]['src'])}
    snap=sync.seal_snapshot(articles,before,STAMP)
    published={'portal-data.json':before,'article-sync-snapshot.json':snap,'publication_sha':'a'*40,
               'article-sync-status.json':{'comparison':'UNKNOWN','new_images':None,'classification_review_count':552},
               'phase3c-production-status.json':{'cutover_active':True,'validation':{'valid':True},'production_image_count':1}}
    new=photo('article-B','https://cdn-ak.f.st-hatena.com/images/b.jpg','unstable-B')
    new['article'].update(title='公開記事B',url='https://exsudoporus-ruber.hatenablog.jp/entry/B')
    current=portal(*deepcopy(before['observations']),new)
    current['observations'][0]['observation_id']='unstable-A'
    live={'articles':{**deepcopy(articles),sync.digest('article-B'):entry(new['src'])},'portal':current,'photos':{},'excluded_draft_hashes':[]}
    review=SyncReview(tmp_path/'local-state'); review.install(published,live)
    return published,live,review


def decide(review, choice='adopt', **extra):
    row=next(r for r in review.rows if r['change_type']=='new_gallery_photo')
    review.decide({'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id,'decision':choice,**extra})
    return row


def empty(): return {**HEADER,'approvals':[]}


def test_new_photo_details_are_bound_to_correct_article(source):
    pub,live,r=source; row=r.rows[0]
    assert row['article_title']=='公開記事B' and row['thumbnail'].endswith('b.jpg')
    assert row['candidate_name']=='シイタケ' and row['adoptable']
    assert row['article_hash']==sync.digest('article-B')
    assert r.dashboard()['summary']['new_articles']==1
    assert r.dashboard()['summary']['classification_review_count']==552
    assert r.dashboard()['summary']['last_success_jst'].endswith('+09:00')


def test_unknown_distinct_from_zero_and_no_live_adoption(source):
    pub,live,r=source; r.install(pub)
    assert r.dashboard()['summary']['new_images'] is None
    pub['article-sync-status.json'].update(comparison='KNOWN',new_images=0)
    assert r.dashboard()['summary']['new_images']==0
    assert all(not x['adoptable'] for x in r.rows)
    with pytest.raises(ReviewError,match='LIVE_REVIEW_REQUIRED'): r.package()


def test_old_ambiguous_not_new_blocker(source):
    pub,live,r=source
    pub['portal-data.json']['observations'][0]['classification']['status']='legacy_review'
    ah=sync.digest('article-A');pub['article-sync-snapshot.json']['payload']['articles'][ah]['images'][0]['state']='ambiguous'
    pub['article-sync-snapshot.json']=sync.seal_snapshot(pub['article-sync-snapshot.json']['payload']['articles'],pub['portal-data.json'],STAMP)
    r.install(pub)
    assert r.rows[0]['group']=='legacy' and not r.rows[0]['adoptable']
    r.decide({'candidate_id':r.rows[0]['candidate_id'],'bundle_id':r.bundle_id,'decision':'no_change'})
    assert r.page(group='reviewed')['total']==1


def test_adopt_is_consumed_by_real_gate_and_second_run_no_reapproval(source):
    pub,live,r=source; decide(r,comment='確認しました')
    manifest=r.package(); resolved=sync.reconcile_ids(live['portal'],pub['portal-data.json'])
    result=gate_new_photos(resolved,pub['portal-data.json'],live['articles'],pub['article-sync-snapshot.json']['sha256'],manifest)
    assert result['approved_new_photos']==1
    assert '確認しました' not in json.dumps(manifest,ensure_ascii=False)
    assert 'https://' not in json.dumps(manifest)
    assert gate_new_photos(resolved,resolved,live['articles'],'different-new-snapshot',manifest)['approved_new_photos']==0


@pytest.mark.parametrize('action',['hold','no_change','pending','propose_name','exclude','confirm_url','delete'])
def test_non_adopt_actions_never_authorize_publication(source,action):
    pub,live,r=source;decide(r,action,proposed_name='人間の提案' if action=='propose_name' else '')
    with pytest.raises(ReviewError,match='NO_APPROVED'): r.package()
    with pytest.raises(sync.SyncError,match='HUMAN_APPROVAL_REQUIRED'):
        gate_new_photos(sync.reconcile_ids(live['portal'],pub['portal-data.json']),pub['portal-data.json'],live['articles'],pub['article-sync-snapshot.json']['sha256'],empty())


def test_persist_reload_audit_undo_idempotence(source):
    pub,live,r=source;decide(r)
    loaded=SyncReview(r.root);loaded.install(pub,live)
    assert loaded.package()==r.package()
    assert loaded.package()==loaded.package()
    decide(loaded,'pending')
    with pytest.raises(ReviewError,match='NO_APPROVED'):loaded.package()
    assert len(loaded.audit)==2
    assert (r.root/'review.json').stat().st_mode & 0o077 == 0


@pytest.mark.parametrize('damage',['id','bundle','url','path','name','choice'])
def test_invalid_or_tampered_input_rejected(source,damage):
    _,_,r=source;row=r.rows[0];body={'candidate_id':row['candidate_id'],'bundle_id':r.bundle_id,'decision':'adopt'}
    if damage=='id': body['candidate_id']='../../secret'
    elif damage=='bundle':body['bundle_id']='stale'
    elif damage=='url':body['url']='https://attacker.example'
    elif damage=='path':body['file']='../../data/best-shots.json'
    elif damage=='name':body['proposed_name']=['wrong']
    else:body['decision']='auto_approve'
    with pytest.raises(ReviewError):r.decide(body)
    assert not r.decisions


@pytest.mark.parametrize('damage',['base','article','image','classification'])
def test_stale_approval_rejected_without_changing_ids(source,damage):
    pub,live,r=source;decide(r);manifest=r.package();base=pub['article-sync-snapshot.json']['sha256']
    changed=deepcopy(live)
    if damage=='base':base='b'*64
    elif damage=='article':changed['articles'][sync.digest('article-B')]['updated_hash']=sync.digest('changed')
    elif damage=='image':changed['articles'][sync.digest('article-B')]['images'][0]['label_hash']=sync.digest('other')
    else:changed['portal']['observations'][-1]['classification']['classification_reason']='changed'
    with pytest.raises(sync.SyncError,match='HUMAN_APPROVAL_REQUIRED|STALE_PHOTO_REVIEW'):
        gate_new_photos(sync.reconcile_ids(changed['portal'],pub['portal-data.json']),pub['portal-data.json'],changed['articles'],base,manifest)


def test_refresh_failure_invalidates_live_approval_not_last_success(source,monkeypatch):
    pub,live,r=source;decide(r)
    monkeypatch.setattr('admin.sync.public_publication',lambda **k: (_ for _ in ()).throw(OSError('PRIVATE BODY SECRET')))
    dashboard=r.refresh(with_live=True)
    assert dashboard['summary']['gallery_photos']==1 and not dashboard['live_review_available']
    assert dashboard['summary']['error']=='SYNC_REVIEW_UNAVAILABLE'
    with pytest.raises(ReviewError,match='LIVE_REVIEW_REQUIRED'):r.package()


def test_freshness_binds_all_source_evidence(source):
    pub,live,r=source;r.assert_fresh(pub,live)
    changed=deepcopy(live);changed['portal']['observations'][-1]['gallery_name']='別名'
    with pytest.raises(ReviewError,match='STALE_LIVE'):r.assert_fresh(pub,changed)
    changed=deepcopy(pub);changed['article-sync-snapshot.json']['sha256']='a'*64
    with pytest.raises(ReviewError,match='STALE_PUBLIC'):r.assert_fresh(changed,live)


def test_existing_photo_cannot_be_deleted_renamed_replaced_by_approval(source):
    pub,live,r=source;live['portal']['observations'][0]['gallery_name']='別名';r.install(pub,live)
    old=next(x for x in r.rows if x['protected_existing'])
    assert old['group']=='migration' and not old['adoptable']
    for action in ['delete','exclude','confirm_url','adopt']:
        with pytest.raises(ReviewError):r.decide({'candidate_id':old['candidate_id'],'bundle_id':r.bundle_id,'decision':action})
    with pytest.raises(sync.SyncError,match='NAME_CHANGE'):sync.reconcile_ids(live['portal'],pub['portal-data.json'])


@pytest.mark.parametrize('state',['legacy_review','manual_review_name_conflict','legacy_undetected'])
def test_wrong_name_not_auto_adopted(source,state):
    pub,live,r=source;live['portal']['observations'][-1]['classification']['status']=state;r.install(pub,live)
    assert not next(x for x in r.rows if x['change_type']=='new_gallery_photo')['adoptable']
    with pytest.raises(ReviewError,match='INDIVIDUAL_MIGRATION'):decide(r)


def test_unknown_is_eligible_only_with_confirmed_mushroom_identity(source):
    pub,live,r=source;row=live['portal']['observations'][-1]
    row['gallery_name']='不明';row['classification']['status']='confirmed_mushroom_identity_uncertain'
    r.install(pub,live);assert r.rows[0]['adoptable']
    row['classification']['subject_state_status']='reset_by_rejected_boundary'
    r.install(pub,live);assert not r.rows[0]['adoptable']


def test_same_url_duplicates_have_distinct_ids_and_no_partial_ordinal_guess(source):
    pub,live,r=source;new=live['portal']['observations'][-1]
    duplicate=deepcopy(new);duplicate['observation_id']='duplicate'
    live['portal']['observations'].append(duplicate);live['portal']['summary']['observation_count']=3
    article=live['articles'][sync.digest('article-B')];second=deepcopy(article['images'][0]);second['ordinal']=1;article['images'].append(second)
    r.install(pub,live);assert len(set(x['candidate_id'] for x in r.rows))==2
    for row in r.rows:r.decide({'candidate_id':row['candidate_id'],'bundle_id':r.bundle_id,'decision':'adopt'})
    manifest=r.package()
    assert gate_new_photos(sync.reconcile_ids(live['portal'],pub['portal-data.json']),pub['portal-data.json'],live['articles'],pub['article-sync-snapshot.json']['sha256'],manifest)['approved_new_photos']==2
    extra=deepcopy(second);extra['ordinal']=2;article['images'].append(extra)
    r.install(pub,live);assert not any(x['adoptable'] for x in r.rows)


@pytest.mark.parametrize('bad',['data/best-shots.json','../sync-reviews/approvals.json','audit/foo','sync-reviews/extra.json'])
def test_sync_pr_allowlist_is_not_existing_allowlist(bad):
    validate_paths([APPROVAL_PATH])
    with pytest.raises(ReviewError,match='PATH_NOT_ALLOWED'):validate_paths([APPROVAL_PATH,bad])


def test_pr_no_github_auth_no_side_effect(source,monkeypatch):
    _,_,r=source;monkeypatch.setattr('admin.sync_git.repository_status',lambda:{'gh_authenticated':False})
    with pytest.raises(ReviewError,match='AUTH_REQUIRED'):create_sync_pull_request(r)


def test_safe_urls_and_no_secret_in_browser():
    assert safe_url('https://cdn-ak.f.st-hatena.com/a.jpg',image=True)
    for url in ['javascript:alert(1)','http://127.0.0.1/private','https://user:secret@cdn-ak.f.st-hatena.com/a.jpg','https://evil.example/a.jpg']:
        assert not safe_url(url,image=True)
    static=Path('admin/static/admin.js').read_text()
    assert 'HATENA_API_KEY' not in static and 'innerHTML' not in static


def test_storage_symlink_refused(tmp_path):
    elsewhere=tmp_path/'elsewhere';elsewhere.mkdir();root=tmp_path/'unsafe';root.symlink_to(elsewhere,target_is_directory=True)
    with pytest.raises(ReviewError,match='LOCAL_STATE_UNSAFE'):SyncReview(root)


def test_isolated_paths_restored_even_after_error():
    import main
    originals={k:getattr(main,k) for k in ('OUTPUT_DIR','CACHE_DIR','ARTICLES_DIR','ARTICLE_METADATA_FILE')}
    with pytest.raises(RuntimeError):
        with isolated_generator():
            assert main.OUTPUT_DIR != originals['OUTPUT_DIR']
            raise RuntimeError()
    assert all(getattr(main,k)==v for k,v in originals.items())


def test_filter_paging_no_arbitrary_paths(source):
    _,_,r=source
    assert r.page(query='公開記事B')['total']==1 and r.page(query='no match')['total']==0
    with pytest.raises(ReviewError):r.page(group='../admin')
    with pytest.raises(ReviewError):r.page(page=0)
    with pytest.raises(ReviewError):r.page(query='x'*121)


def test_manifest_missing_tamper_rejected(tmp_path):
    with pytest.raises(sync.SyncError,match='MISSING'):load_approvals(tmp_path)
    value=empty();value['allow_deletion']=True
    with pytest.raises(sync.SyncError,match='INVALID'):validate_approvals(value)


def test_http_localhost_csrf_path_and_secret_errors(source,monkeypatch):
    from admin.server import AdminServer,Handler
    monkeypatch.setattr("admin.sync.public_publication",lambda **k: (_ for _ in ()).throw(OSError("PRIVATE BODY SECRET")))
    pub,live,review=source
    monkeypatch.setattr('admin.server.load_portal_data',lambda:(pub['portal-data.json'],'fixture'))
    monkeypatch.setattr('admin.server.SyncReview',lambda:review)
    server=AdminServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        def request(path,body=None,headers=None):
            return urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers or {}))
        with request('/api/sync/candidates') as response:assert json.load(response)['total']==1
        for headers in ({'Host':'evil.example'},{'Origin':'https://evil.example'}):
            with pytest.raises(urllib.error.HTTPError) as err:request('/api/sync/state',headers=headers)
            assert err.value.code==403
        with pytest.raises(urllib.error.HTTPError) as err:request('/api/sync/decision',{})
        assert err.value.code==403
        with pytest.raises(urllib.error.HTTPError) as err:request('/api/sync/preview',{}, {'X-CSRF-Token':server.csrf_token})
        # Browser must see a safe fixed code, not Git/HTTP error details.
        assert err.value.code==400
        with pytest.raises(urllib.error.HTTPError) as err:request('/%2e%2e/admin/local-state/sync/review.json')
        assert err.value.code==404
    finally:server.shutdown();server.server_close();thread.join()


@pytest.mark.parametrize('bad_paths',[False,True])
def test_pr_success_sequence_or_unexpected_path_blocks_before_push(source,monkeypatch,bad_paths):
    from types import SimpleNamespace
    import admin.sync_git as git
    pub,live,review=source;decide(review)
    review.last_preview={'manifest_sha256':sync.payload_hash(review.package())}
    monkeypatch.setattr(git,'repository_status',lambda:{'gh_authenticated':True})
    monkeypatch.setattr(git,'public_publication',lambda:pub)
    monkeypatch.setattr(git,'live_capture',lambda:live)
    calls=[]
    def command(args,*,cwd=None,check=True):
        calls.append(args)
        output=''
        if args[:3]==['git','rev-parse','origin/main'] or args[:3]==['git','rev-parse','HEAD']:output='a'*40
        if args[:3]==['git','worktree','add']:
            directory=Path(args[-2]);(directory/'sync-reviews').mkdir()
            (directory/'sync-reviews/approvals.json').write_text('{}')
            (directory/'tests').mkdir();(directory/'tests/example.js').write_text('')
        if args[:3]==['git','diff','--name-only']:output=APPROVAL_PATH + ('\ndata/best-shots.json' if bad_paths else '')
        if args[:4]==['git','diff','--cached','--name-only']:output=APPROVAL_PATH
        if args[:3]==['gh','pr','create']:
            assert '--draft' in args and '--body-file' in args
            output='https://github.com/example/repo/pull/999'
        return SimpleNamespace(stdout=output,returncode=0)
    monkeypatch.setattr(git,'run',command)
    if bad_paths:
        with pytest.raises(ReviewError,match='PATH_NOT_ALLOWED'):git.create_sync_pull_request(review)
        assert not any(c[:2]==['git','push'] for c in calls)
    else:
        result=git.create_sync_pull_request(review)
        assert result['draft'] is True
        assert any(c[:2]==['git','push'] and c[-1].startswith('admin/sync-review-') for c in calls)
        assert any('article_sync.py' in c for c in calls)
        assert any(c[:2]==['git','add'] and c[-1]==APPROVAL_PATH for c in calls)
        assert review.last_preview is None
    assert not any(c[:2] in (['git','merge'],['gh','workflow']) for c in calls)


def test_retired_article_never_adoptable_even_if_published_again(source):
    from sync_retirement import load_manifest
    pub,live,r=source;m=load_manifest();oldkey=sync.digest('article-B')
    article=live['articles'].pop(oldkey);live['articles'][m['target_article_sha256']]=article
    # Candidate preparation must withhold an adoption button independently of
    # the production retirement gate (already tested in test_sync_retirement).
    rows=candidates(pub,live)
    retired=next(x for x in rows if x['article_hash']==m['target_article_sha256'])
    assert retired['group']=='migration' and not retired['adoptable']


def test_unclassified_new_non_gallery_is_not_a_fake_approval(source):
    pub,live,r=source;row=live['articles'][sync.digest('article-B')]['images'][0]
    row['state']='unclassified';live['portal']=deepcopy(pub['portal-data.json']);r.install(pub,live)
    assert r.rows[0]['candidate_name'] is None and not r.rows[0]['adoptable']
    with pytest.raises(ReviewError,match='INDIVIDUAL_MIGRATION'):r.decide({'candidate_id':r.rows[0]['candidate_id'],'bundle_id':r.bundle_id,'decision':'adopt'})


def test_failed_action_preserves_public_success_and_sanitizes_report(monkeypatch):
    import admin.sync as review
    from types import SimpleNamespace
    calls=[]
    def command(args,**kwargs):
        calls.append(args)
        if args[:3]==['gh','run','list']:
            return SimpleNamespace(returncode=0,stdout=json.dumps([{'databaseId':123,'status':'completed','conclusion':'failure','url':'https://github.com/example/run/123'}]))
        if args[:2]==['gh','api']:return SimpleNamespace(returncode=0,stdout='1')
        destination=Path(args[args.index('--dir')+1]);(destination/'article-sync-report.json').write_text(json.dumps({'error_code':'NEW_PHOTO_HUMAN_APPROVAL_REQUIRED','raw_body':'PRIVATE DO NOT RETURN','url':'PRIVATE URL'}))
        return SimpleNamespace(returncode=0,stdout='')
    monkeypatch.setattr(review,'run',command);monkeypatch.setattr(review,'ACTION_CACHE',{'at':0,'value':None})
    result=review.latest_actions()
    assert result['error_code']=='NEW_PHOTO_HUMAN_APPROVAL_REQUIRED'
    assert 'PRIVATE' not in json.dumps(result)
    assert all('GET' in c for c in calls if c[:2]==['gh','api'])
    assert review.latest_actions()==result and len(calls)==3


def test_plan_separates_applied_additions_from_held_proposals(source):
    pub,live,r=source;decide(r,'propose_name',proposed_name='人間による仮名')
    plan=r.plan();assert plan['additions']==[] and len(plan['held'])==1
    assert plan['existing_names_changed']==plan['deletions']==plan['url_replacements']==[]
    decide(r);plan=r.plan();assert len(plan['additions'])==1 and plan['held']==[]


def test_preview_failure_never_enables_pr(source,monkeypatch):
    import admin.sync as local
    pub,live,r=source;decide(r)
    monkeypatch.setattr(local,'public_publication',lambda **k:pub)
    monkeypatch.setattr(local,'live_capture',lambda:live)
    monkeypatch.setattr(local,'validate_package',lambda *a:(_ for _ in ()).throw(ReviewError('PROTECTED_REFERENCE_ERROR')))
    result=r.preview();assert not result['ready'] and result['error_code']=='PROTECTED_REFERENCE_ERROR'
    assert len(result['plan']['additions'])==1 and r.last_preview is None


def test_manifest_parent_symlink_is_not_a_valid_review_boundary(tmp_path):
    parent=tmp_path/'outside';parent.mkdir();(parent/'approvals.json').write_text(json.dumps(empty()))
    root=tmp_path/'repo';root.mkdir();(root/'sync-reviews').symlink_to(parent,target_is_directory=True)
    with pytest.raises(sync.SyncError):load_approvals(root)


def test_recent_local_history_and_no_duplicate_pr(source):
    _,_,r=source;decide(r)
    assert r.dashboard()['history'][-1]['decision']=='adopt'
    r.audit.append({'event':'draft_pr_created','bundle_id':r.bundle_id,'at':STAMP})
    with pytest.raises(ReviewError,match='ALREADY_HAS_DRAFT_PR'):r.package()


def test_no_safe_visible_photo_means_no_adoption_even_with_safe_classifier(source):
    pub,live,r=source;live['portal']['observations'][-1]['article']['url']='https://untrusted.example/article'
    r.install(pub,live);row=r.rows[0]
    assert not row['adoptable'] and row['group']=='blocker'
    with pytest.raises(ReviewError,match='INDIVIDUAL_MIGRATION'):decide(r)
