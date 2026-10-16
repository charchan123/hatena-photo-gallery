"""Local UI domain operations: fixtures only, no real approval/publication."""
from copy import deepcopy
from datetime import timedelta
import json
import threading
import urllib.request
import urllib.error

import pytest

import article_sync as sync
from admin import deletions as a
from test_deletion_guard import setup, Store
from test_sync_deletions import T,BASE
import sync_deletions as d


def review(tmp_path,monkeypatch,*,research=False,history_rows=False):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch,research=research,history_rows=history_rows)
    pub={'publication_sha':BASE,'portal-data.json':p,'article-sync-snapshot.json':s}
    live={'articles':current,'portal':d.without_targets(p,rows),'fetch_audit':__import__('test_sync_deletions').audit(current),'excluded_draft_hashes':[]}
    monkeypatch.setattr(a,'public_publication',lambda **kw:deepcopy(pub))
    monkeypatch.setattr(a,'live_capture',lambda:deepcopy(live))
    monkeypatch.setattr(a,'GitHistory',lambda root:Store(h))
    monkeypatch.setattr(a,'open_selections',lambda:[])
    class Clock:
        @staticmethod
        def now(tz=None):return d.instant(T)+timedelta(hours=8)
    monkeypatch.setattr(a,'datetime',Clock)
    r=a.DeletionReview(tmp_path);r.refresh(live=True)
    return r,pub,live


def body(row,action='hold'):
    return {'candidate_id':row['candidate_id'],'fingerprint':row['fingerprint'],'action':action,
        'reason':'人間が対象を確認したfixture','confirm_id':row['observation_id'],'replacement_id':None}


def test_decisions_survive_server_restart_and_do_not_modify_source(tmp_path,monkeypatch):
    r,pub,live=review(tmp_path,monkeypatch)
    before={p:p.read_bytes() for p in (tmp_path/'data').iterdir()}
    r.decide(body(r.rows[0]));again=a.DeletionReview(tmp_path);again.refresh()
    assert again.dashboard()['rows'][0]['decision']['action']=='hold'
    assert all(p.read_bytes()==content for p,content in before.items())
    assert len(pub['portal-data.json']['observations'])==100
    assert r.state['audit'][-1]['event']=='individual_decision'


def test_approval_is_individual_explicit_and_preview_is_read_only(tmp_path,monkeypatch):
    r,pub,live=review(tmp_path,monkeypatch)
    bad=body(r.rows[0],'approve');bad['confirm_id']='wrong'
    with pytest.raises(sync.SyncError,match='EXPLICIT_CONFIRMATION'):r.decide(bad)
    assert not r.state['decisions']
    r.decide(body(r.rows[0],'approve'));preview=r.preview_changes()
    assert preview['published'] is False and len(preview['files'])==1
    path=next(iter(preview['files']));assert path.startswith('sync-migrations/photo-deletions/')
    assert not (tmp_path/path).exists()
    assert len(pub['portal-data.json']['observations'])==100


def test_changed_baseline_source_or_references_rejects_stale_approval(tmp_path,monkeypatch):
    for changed in ('baseline','source','reference'):
        directory=tmp_path/changed;r,pub,live=review(directory,monkeypatch)
        if changed=='baseline':pub['publication_sha']='f'*40
        elif changed=='source':live['articles'][next(iter(live['articles']))]['updated_hash']='f'*64
        else:sync.write_json(directory/'data/curated-photo.json',{'observation_id':'obs-0'})
        with pytest.raises(sync.SyncError,match='REVIEW_STALE'):r.decide(body(r.rows[0],'approve'))
        assert not r.state['decisions']


def test_restart_marks_old_fingerprint_stale(tmp_path,monkeypatch):
    r,pub,live=review(tmp_path,monkeypatch);r.decide(body(r.rows[0]))
    cid=r.rows[0]['candidate_id']
    pub['article-sync-snapshot.json']=sync.seal_snapshot(pub['article-sync-snapshot.json']['payload']['articles'],pub['portal-data.json'],(d.instant(T)+timedelta(hours=1)).isoformat())
    r.refresh(live=True)
    assert r.state['decisions'][cid]['stale'] is True
    assert a.DeletionReview(tmp_path).state['decisions'][cid]['stale'] is True


def test_unique_research_case_requires_archive_and_preserves_identification(tmp_path,monkeypatch):
    r,pub,live=review(tmp_path,monkeypatch,research=True,history_rows=True)
    with pytest.raises(sync.SyncError,match='PROTECTED_REFERENCE_REMAINS'):r.decide(body(r.rows[0],'approve'))
    result=r.decide(body(r.rows[0],'archive_research'))
    assert result['published'] is False
    files=r.files();manifest=next(v for k,v in files.items() if k.startswith('sync-migrations/'))
    assert manifest['archives'][0]['identifications'][0]['note']=='研究記録を保持'
    assert files['data/research-identifications.json']['identifications']==[]
    # This is a proposed file in an isolated future PR. Actual registry unchanged.
    assert len(sync.read_json(tmp_path/'data/research-identifications.json')['identifications'])==1
    assert manifest['archives'][0]['observations'][0]['observation_id']=='obs-0'


def test_replacement_proposal_does_not_change_best_shots_or_delete(tmp_path,monkeypatch):
    r,pub,live=review(tmp_path,monkeypatch);before=sync.read_json(tmp_path/'data/best-shots.json')
    b=body(r.rows[0],'propose_replacement');b['replacement_id']='obs-0'
    with pytest.raises(sync.SyncError,match='APPROVAL_INVALID'):r.decide(b)
    b['replacement_id']='obs-1';r.decide(b)
    assert r.state['decisions'][r.rows[0]['candidate_id']]['replacement_id']=='obs-1'
    assert sync.read_json(tmp_path/'data/best-shots.json')==before
    assert not d.select(r.rows,pub['article-sync-snapshot.json'],r.history,r.protection,(d.instant(T)+timedelta(hours=8)).isoformat(),list(r.files().values()))


def test_no_live_approval_and_input_validation(tmp_path,monkeypatch):
    r,pub,live=review(tmp_path,monkeypatch);r.live=None
    with pytest.raises(sync.SyncError,match='LIVE_REVIEW_REQUIRED'):r.decide(body(r.rows[0],'approve'))
    # Negative decisions remain available without source credentials.
    r.decide(body(r.rows[0],'hold'))
    b=body(r.rows[0]);b['unexpected']='anything'
    with pytest.raises(sync.SyncError,match='APPROVAL_INVALID'):r.decide(b)
    b=body(r.rows[0]);b['reason']=''
    with pytest.raises(sync.SyncError,match='APPROVAL_INVALID'):r.decide(b)


def test_atomic_storage_refuses_symlinks(tmp_path):
    other=tmp_path/'other';other.write_text('preserve')
    path=tmp_path/'link';path.symlink_to(other)
    with pytest.raises(sync.SyncError,match='LOCAL_STORAGE_UNSAFE'):a.atomic_json(path,{'overwrite':True})
    assert other.read_text()=='preserve'


def test_concurrent_console_cannot_overwrite_persisted_decision(tmp_path,monkeypatch):
    first,pub,live=review(tmp_path,monkeypatch)
    second=a.DeletionReview(tmp_path);second.refresh(live=True)
    first.decide(body(first.rows[0],'hold'))
    b=body(second.rows[0],'approve')
    with pytest.raises(sync.SyncError,match='LOCAL_STATE_CONFLICT'):second.decide(b)
    assert a.DeletionReview(tmp_path).state['decisions'][first.rows[0]['candidate_id']]['action']=='hold'
    second.refresh(live=True)
    assert second.dashboard()['rows'][0]['decision']['action']=='hold'


def test_http_routes_keep_origin_csrf_and_japanese_failure_contract(tmp_path,monkeypatch):
    from admin import server as web
    r,pub,live=review(tmp_path,monkeypatch,research=True)
    monkeypatch.setattr(web,'load_portal_data',lambda:(pub['portal-data.json'],'isolated fixture'))
    monkeypatch.setattr(web,'DeletionReview',lambda:r)
    server=web.AdminServer(('127.0.0.1',0),web.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base=f'http://127.0.0.1:{server.server_port}'
    def request(path,data=None,headers=None):
        raw=json.dumps(data).encode() if data is not None else None
        req=urllib.request.Request(base+path,data=raw,headers=headers or {})
        return opener.open(req,timeout=5)
    try:
        assert json.load(request('/api/deletions/state'))['rows'][0]['observation_id']=='obs-0'
        with pytest.raises(urllib.error.HTTPError) as err:request('/api/deletions/decision',body(r.rows[0],'approve'))
        assert err.value.code==403
        headers={'X-CSRF-Token':server.csrf_token,'Content-Type':'application/json'}
        with pytest.raises(urllib.error.HTTPError) as err:request('/api/deletions/decision',body(r.rows[0],'approve'),{**headers,'Origin':'https://external.example'})
        assert err.value.code==403
        with pytest.raises(urllib.error.HTTPError) as err:request('/api/deletions/decision',body(r.rows[0],'approve'),headers)
        error=json.load(err.value)
        assert error['error']=='DELETION_PROTECTED_REFERENCE_REMAINS'
        assert '参照' in error['message'] and not r.state['decisions']
        assert request('/deletions.js').headers['Content-Type'].startswith('text/javascript')
        assert len(server.draft.best_shots['entries'])==3
    finally:server.shutdown();server.server_close();thread.join()


def test_merged_unpublished_archive_can_be_reviewed_and_replaced_with_hold(tmp_path,monkeypatch):
    r,pub,live=review(tmp_path,monkeypatch,research=True,history_rows=True)
    original=sync.read_json(tmp_path/'data/research-identifications.json')
    r.decide(body(r.rows[0],'archive_research'))
    files=r.files();manifest=next(v for k,v in files.items() if k.startswith('sync-migrations/'))
    for path,value in files.items():sync.write_json(tmp_path/path,value)
    # Simulate a reviewed merge while publication is still blocked. The old
    # publication's identification reference must still bind every decision.
    again=a.DeletionReview(tmp_path);again.refresh(live=True)
    assert again.protection==r.protection
    assert again.rows[0]['status']=='manual_eligible'
    class Later:
        @staticmethod
        def now(tz=None):return d.instant(T)+timedelta(hours=9)
    monkeypatch.setattr(a,'datetime',Later)
    again.decide(body(again.rows[0],'hold'));proposed=again.files()
    assert proposed['data/research-identifications.json']==original
    hold=next(v for k,v in proposed.items() if k.startswith('sync-migrations/'))
    assert hold['supersedes']==manifest['approval_id']
    assert sync.read_json(tmp_path/'sync-migrations/photo-deletions'/(manifest['approval_id']+'.json'))==manifest
    assert len(proposed)==2
    for path,value in proposed.items():sync.write_json(tmp_path/path,value)
    guard=__import__('deletion_guard').DeletionGuard(pub['portal-data.json'],pub['article-sync-snapshot.json'],BASE,tmp_path,'three',store=Store(r.history),pending=[])
    with pytest.raises(sync.SyncError,match='CONFIRMATION_OR_APPROVAL_PENDING'):
        guard.prepare(live['articles'],live['fetch_audit'],set())
    assert sync.read_json(tmp_path/'data/research-identifications.json')==original
