"""Real localhost API; only the GitHub publication boundary is intercepted."""
from copy import deepcopy
import json
import threading
import urllib.error
import urllib.request

import pytest
from admin import server as web
from admin.core import ChangeSet
from admin.draft_store import DraftStore
from admin.git_workflow import GitWorkflowError


@pytest.fixture
def api(tmp_path, monkeypatch):
    draft=ChangeSet.__new__(ChangeSet)
    draft.portal={'version':1,'observations':[{'observation_id':'fixture','gallery_name':'試験写真',
                 'src':'https://example.test/fixture.jpg','capture':{'date':'2024-01-01'},'article':{}}]}
    draft.best_shots={'version':1,'entries':[],'annual_best':{}}
    draft.notices={'version':1,'events':[]}
    draft.identifications={'version':1,'identifications':[]};draft.master={'entries':[]}
    monkeypatch.setattr(web,'load_portal_data',lambda:(draft.portal,'isolated test'))
    monkeypatch.setattr(web,'ChangeSet',lambda portal:draft)
    monkeypatch.setattr(web,'DraftStore',lambda:DraftStore(tmp_path))
    monkeypatch.setattr(web,'SyncReview',lambda:object())
    monkeypatch.setattr(web,'DeletionReview',lambda:object())
    app=web.AdminServer(('127.0.0.1',0),web.Handler)
    thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
    calls=[]
    def publish(files,validation,operation,*,baseline):
        saved=json.loads(app.draft_store.path.read_text(encoding='utf-8'))
        assert saved['files']==files and baseline==app.draft_store.baseline
        assert validation['best_shots']==1
        calls.append(deepcopy(files))
        return {'url':'https://github.com/fixture/test/pull/1','draft':True,'ci_status':'pending'}
    monkeypatch.setattr(web,'create_pull_request',publish)
    def post(path,body):
        request=urllib.request.Request(f'http://127.0.0.1:{app.server_port}'+path,
            data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-CSRF-Token':app.csrf_token})
        try:
            with urllib.request.urlopen(request) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)
    yield app,post,calls
    app.shutdown();app.server_close();thread.join()


def add(post):
    assert post('/api/best-shot/add',{'entry':{'selection_id':'fixture-best','observation_id':'fixture','comment':'本人の選択','order':1},'add_notice':True})[0]==200


def test_pr_success_uses_validated_durable_snapshot_and_original_baseline(api):
    app,post,calls=api;add(post);before=app.draft_store.path.read_bytes()
    status,result=post('/api/pr',{})
    assert status==200 and result['draft'] and result['ci_status']=='pending'
    assert result['url']=='https://github.com/fixture/test/pull/1'
    assert len(calls)==1 and len(calls[0]['data/update-notices.json']['events'])==1
    assert app.draft_store.path.is_file()
    assert app.draft_store.path.read_bytes()==before
    restored=deepcopy(app.draft)
    restored.best_shots=deepcopy(app.draft_store.baseline['data/best-shots.json'])
    restored.notices=deepcopy(app.draft_store.baseline['data/update-notices.json'])
    assert DraftStore(app.draft_store.path.parents[2]).recover(restored).files()==app.draft.files()


@pytest.mark.parametrize('cause',['最新mainの変更','gh auth loginで再認証','push permission denied'])
def test_pr_failure_returns_actionable_message_and_retains_snapshot(api,monkeypatch,cause):
    app,post,calls=api;add(post);saved=json.loads(app.draft_store.path.read_bytes())
    def fail(*args,**kwargs):raise GitWorkflowError(cause+'。下書きは保持しています')
    monkeypatch.setattr(web,'create_pull_request',fail)
    status,result=post('/api/pr',{})
    assert status==400 and result['error']=='PR_CREATION_FAILED' and cause in result['message']
    assert json.loads(app.draft_store.path.read_bytes())==saved
    assert not calls


def test_pr_save_failure_stops_before_github_and_keeps_previous_draft(api,monkeypatch):
    app,post,calls=api;add(post);before=app.draft_store.path.read_bytes()
    def fail(draft):raise OSError('disk full')
    monkeypatch.setattr(app.draft_store,'verify_saved',fail)
    status,result=post('/api/pr',{})
    assert status==400 and 'disk full' in result['message'] and '空き容量' in result['message']
    assert not calls and app.draft_store.path.read_bytes()==before


def test_pr_input_validation_failure_stops_before_save_and_github(api,monkeypatch):
    app,post,calls=api;add(post);before=app.draft_store.path.read_bytes()
    app.draft.best_shots['entries'][0]['order']=0
    status,result=post('/api/pr',{})
    assert status==400 and result['error']=='PR_CREATION_FAILED'
    assert not calls and app.draft_store.path.read_bytes()==before


def test_no_changes_does_not_touch_draft_or_create_pr(api):
    app,post,calls=api
    assert post('/api/pr',{})[0]==400
    assert not calls and not app.draft_store.path.exists()


@pytest.mark.parametrize('value',[None,'{broken', '{"version":1,"files":{},"base":{}}'])
def test_missing_or_changed_disk_draft_is_preserved_and_cannot_publish(api,value):
    app,post,calls=api;add(post)
    if value is None:app.draft_store.path.unlink()
    else:app.draft_store.path.write_text(value,encoding='utf-8')
    status,result=post('/api/pr',{})
    assert status==400 and '上書き・削除していません' in result['message']
    assert not calls
    assert not app.draft_store.path.exists() if value is None else app.draft_store.path.read_text(encoding='utf-8')==value
