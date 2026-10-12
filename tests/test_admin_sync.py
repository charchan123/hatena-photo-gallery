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
from sync_review import occurrence_rows
from admin.sync import SyncReview, ReviewError, candidates, safe_url, isolated_generator
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


def decide(review, choice='confirmed', **extra):
    row=next(r for r in review.rows if r['change_type']=='new_gallery_photo')
    review.decide({'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id,'decision':choice,**extra})
    return row


def test_new_photo_details_are_bound_to_correct_article(source):
    pub,live,r=source; row=r.rows[0]
    assert row['article_title']=='公開記事B' and row['thumbnail'].endswith('b.jpg')
    assert row['candidate_name']=='シイタケ' and row['auto_eligible']
    assert row['article_hash']==sync.digest('article-B')
    assert r.dashboard()['summary']['new_articles']==1
    assert r.dashboard()['summary']['classification_review_count']==552
    assert r.dashboard()['summary']['last_success_jst'].endswith('+09:00')


def test_unknown_distinct_from_zero_without_live_capture(source):
    pub,live,r=source; r.install(pub)
    assert r.dashboard()['summary']['new_images'] is None
    pub['article-sync-status.json'].update(comparison='KNOWN',new_images=0)
    assert r.dashboard()['summary']['new_images']==0
    assert all(not x['auto_eligible'] for x in r.rows)


def test_old_ambiguous_not_new_blocker(source):
    pub,live,r=source
    pub['portal-data.json']['observations'][0]['classification']['status']='legacy_review'
    ah=sync.digest('article-A');pub['article-sync-snapshot.json']['payload']['articles'][ah]['images'][0]['state']='ambiguous'
    pub['article-sync-snapshot.json']=sync.seal_snapshot(pub['article-sync-snapshot.json']['payload']['articles'],pub['portal-data.json'],STAMP)
    r.install(pub)
    assert r.rows[0]['group']=='legacy' and not r.rows[0]['auto_eligible']
    r.decide({'candidate_id':r.rows[0]['candidate_id'],'bundle_id':r.bundle_id,'decision':'no_change'})
    assert r.page(group='reviewed')['total']==1


def test_persist_reload_audit_undo_idempotence(source):
    pub,live,r=source;decide(r)
    loaded=SyncReview(r.root);loaded.install(pub,live)
    assert loaded.decisions==r.decisions
    before=deepcopy(pub)
    assert loaded.dashboard()['history'][-1]['decision']=='confirmed'
    assert pub==before
    decide(loaded,'pending')
    assert len(loaded.audit)==2
    assert (r.root/'review.json').stat().st_mode & 0o077 == 0


@pytest.mark.parametrize('damage',['id','bundle','url','path','name','choice'])
def test_invalid_or_tampered_input_rejected(source,damage):
    _,_,r=source;row=r.rows[0];body={'candidate_id':row['candidate_id'],'bundle_id':r.bundle_id,'decision':'confirmed'}
    if damage=='id': body['candidate_id']='../../secret'
    elif damage=='bundle':body['bundle_id']='stale'
    elif damage=='url':body['url']='https://attacker.example'
    elif damage=='path':body['file']='../../data/best-shots.json'
    elif damage=='name':body['proposed_name']=['wrong']
    else:body['decision']='auto_approve'
    with pytest.raises(ReviewError):r.decide(body)
    assert not r.decisions


def test_refresh_failure_invalidates_live_approval_not_last_success(source,monkeypatch):
    pub,live,r=source;decide(r)
    monkeypatch.setattr('admin.sync.public_publication',lambda **k: (_ for _ in ()).throw(OSError('PRIVATE BODY SECRET')))
    dashboard=r.refresh(with_live=True)
    assert dashboard['summary']['gallery_photos']==1 and not dashboard['live_review_available']
    assert dashboard['summary']['error']=='SYNC_REVIEW_UNAVAILABLE'


def test_freshness_binds_all_source_evidence(source):
    pub,live,r=source;r.assert_fresh(pub,live)
    changed=deepcopy(live);changed['portal']['observations'][-1]['gallery_name']='別名'
    with pytest.raises(ReviewError,match='STALE_LIVE'):r.assert_fresh(pub,changed)
    changed=deepcopy(pub);changed['article-sync-snapshot.json']['sha256']='a'*64
    with pytest.raises(ReviewError,match='STALE_PUBLIC'):r.assert_fresh(changed,live)


def test_existing_photo_cannot_be_deleted_renamed_replaced_by_approval(source):
    pub,live,r=source;live['portal']['observations'][0]['gallery_name']='別名';r.install(pub,live)
    old=next(x for x in r.rows if x['protected_existing'])
    assert old['group']=='migration' and not old['auto_eligible']
    for action in ['delete','exclude','confirm_url','adopt']:
        with pytest.raises(ReviewError):r.decide({'candidate_id':old['candidate_id'],'bundle_id':r.bundle_id,'decision':action})
    with pytest.raises(sync.SyncError,match='NAME_CHANGE'):sync.reconcile_ids(live['portal'],pub['portal-data.json'])


@pytest.mark.parametrize('state',['legacy_review','manual_review_name_conflict','legacy_undetected'])
def test_uncertain_classification_not_changed_by_confirmation(source,state):
    pub,live,r=source;live['portal']['observations'][-1]['classification']['status']=state;r.install(pub,live)
    assert not next(x for x in r.rows if x['change_type']=='new_gallery_photo')['auto_eligible']
    decide(r)
    assert r.rows[0]['classification']['status']==state


def test_unknown_is_eligible_only_with_confirmed_mushroom_identity(source):
    pub,live,r=source;row=live['portal']['observations'][-1]
    row['gallery_name']='不明';row['classification']['status']='confirmed_mushroom_identity_uncertain'
    r.install(pub,live);assert r.rows[0]['auto_eligible']
    row['classification']['subject_state_status']='reset_by_rejected_boundary'
    r.install(pub,live);assert not r.rows[0]['auto_eligible']


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
        with request('/api/sync/candidates') as response:assert json.load(response)['total']==2
        with request('/api/sync/candidates?group=published') as response:assert json.load(response)['total']==1
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


def test_retired_article_never_auto_eligible_even_if_published_again(source):
    from sync_retirement import load_manifest
    pub,live,r=source;m=load_manifest();oldkey=sync.digest('article-B')
    article=live['articles'].pop(oldkey);live['articles'][m['target_article_sha256']]=article
    # Candidate preparation must mark retirement exceptions independently of
    # the production retirement gate (already tested in test_sync_retirement).
    rows=candidates(pub,live)
    retired=next(x for x in rows if x['article_hash']==m['target_article_sha256'])
    assert retired['group']=='migration' and not retired['auto_eligible']


def test_unclassified_new_non_gallery_is_not_a_fake_approval(source):
    pub,live,r=source;row=live['articles'][sync.digest('article-B')]['images'][0]
    row['state']='unclassified';live['portal']=deepcopy(pub['portal-data.json']);r.install(pub,live)
    assert r.rows[0]['candidate_name'] is None and not r.rows[0]['auto_eligible']
    decide_body={'candidate_id':r.rows[0]['candidate_id'],'bundle_id':r.bundle_id,'decision':'confirmed'}
    r.decide(decide_body)
    assert live['portal']==pub['portal-data.json']


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
    plan=r.plan();assert len(plan['automatic_addition_candidates'])==1 and len(plan['held'])==1
    assert plan['existing_names_changed']==plan['deletions']==plan['url_replacements']==[]
    decide(r);plan=r.plan();assert len(plan['automatic_addition_candidates'])==1 and plan['held']==[]


def test_preview_failure_never_enables_pr(source,monkeypatch):
    import admin.sync as local
    pub,live,r=source;decide(r)
    monkeypatch.setattr(local,'public_publication',lambda **k:pub)
    monkeypatch.setattr(local,'live_capture',lambda:live)
    monkeypatch.setattr(local,'validate_package',lambda *a:(_ for _ in ()).throw(ReviewError('PROTECTED_REFERENCE_ERROR')))
    result=r.preview();assert not result['ready'] and result['error_code']=='PROTECTED_REFERENCE_ERROR'
    assert len(result['plan']['automatic_addition_candidates'])==1 and r.last_preview is None


def test_display_url_restriction_does_not_stop_normal_automatic_sync(source):
    pub,live,r=source;live['portal']['observations'][-1]['article']['url']='https://untrusted.example/article'
    r.install(pub,live);row=r.rows[0]
    assert row['auto_eligible'] and row['article_url'] is None
    result=sync.reconcile_ids(live['portal'],pub['portal-data.json'])
    assert len(result['observations'])==2
