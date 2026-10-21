from copy import deepcopy
import hashlib,hmac,json
from pathlib import Path
from types import SimpleNamespace
import pytest
from research_ui import build_research_cases,build_research_model,render_research_page
from research_comments import validate_bindings,prepare,registry_digest,public_config
from admin import comments_client

def source(name='不明',oid='photo-1',article='article-1'):
    return {'observation_id':oid,'gallery_name':name,'src':'https://fixture.test/'+oid+'.jpg','capture':{'date':'2025-10-01'},'article':{'article_id':article,'url':'https://example.test/article'}}
def registry_for(portal):
    cases=build_research_cases(portal)
    return {'version':1,'cases':[{'id':c['case_id'],'label':c['gallery_name'],'article_identity':['article_id',c['article']['article_id']],'observation_ids':[p['observation_id'] for p in c['photos']],'render_ids':[c['case_id']]}for c in cases]}
def test_initial_ids_remain_exact_and_names_never_auto_reassign():
    p={'version':1,'observations':[source()]};cases=build_research_cases(p);r=registry_for(p)
    assert prepare(cases,r)['bindings']=={cases[0]['case_id']:cases[0]['case_id']}
    p['observations'][0]['gallery_name']='候補？'
    changed=build_research_cases(p);state=prepare(changed,r)
    assert not state['bindings'] and state['pending']==[changed[0]['case_id']]
    assert state['archived'][0]['id']==cases[0]['case_id']
    # An explicitly reviewed alias with the SAME exact photo/article proof works.
    r['cases'][0]['render_ids'].append(changed[0]['case_id'])
    assert prepare(changed,r)['bindings'][changed[0]['case_id']]==cases[0]['case_id']

def test_split_merge_changed_photos_or_article_require_review():
    p={'version':1,'observations':[source(),source(oid='photo-2')]};r=registry_for(p)
    for mutate in [lambda p:p['observations'].pop(),lambda p:p['observations'].append(source(oid='new-photo')),lambda p:p['observations'][0]['article'].update(article_id='different'),lambda p:p['observations'][0].update(gallery_name='候補？')]:
        c=deepcopy(p);mutate(c);assert prepare(build_research_cases(c),r)['pending']

def test_registry_collisions_and_unknown_fields_fail_closed():
    p={'version':1,'observations':[source()]};r=registry_for(p)
    for change in [lambda c:c['cases'].append(deepcopy(c['cases'][0])),lambda c:c['cases'][0].update(extra=True),lambda c:c['cases'][0].update(render_ids=[]),lambda c:c['cases'][0].update(observation_ids=['photo-1','photo-1'])]:
        value=deepcopy(r);change(value)
        with pytest.raises(ValueError):validate_bindings(value)

def test_identified_archive_keeps_same_thread_and_config_is_closed():
    p={'version':1,'observations':[source()]};case=build_research_cases(p)[0];r=registry_for(p);state=prepare([case],r)
    page=render_research_page({'cases':[],'case_count':0,'photo_count':0},[{'case':case,'identification':{'identified_name':'シイタケ','note':'同定'}}],state)
    assert 'data-research-thread="'+case['case_id']+'"' in page and '管理人' not in r['cases'][0]['label']
    assert public_config()['enabled'] is False
    assert 'release_approval' in public_config() and not public_config()['api_url']

def test_comment_bindings_extend_deletion_protection_without_relaxing_gates(tmp_path):
    from deletion_protection import curated_path,collect
    from test_sync_deletions import fixture,audit,T
    from test_deletion_guard import config
    import sync_deletions as deletion
    p,s,current=fixture();config(tmp_path)
    # A previously unknown case now has a confirmed label; its historical
    # photo still remains protected solely by the explicit comment binding.
    original=deepcopy(p);original['observations'][0]['gallery_name']='不明'
    binding=registry_for(original)
    path=tmp_path/'comments/cases.json';path.parent.mkdir();path.write_text(json.dumps(binding),encoding='utf-8')
    protection=collect(p,s,tmp_path,[])
    assert {'kind':'curated_history','id':'comments/cases.json'} in protection['references']['obs-0']
    rows=deletion.plan(s,p,current,audit(current),set(),protection)
    assert rows[0]['protection'] and not deletion.select(rows,s,[],protection,T)
    assert curated_path('comments/cases.json') and not curated_path('comments/untrusted.json')

def test_admin_config_does_not_expose_secret_and_rejects_unsafe_endpoints(monkeypatch):
    monkeypatch.setenv('KINOKO_COMMENTS_ADMIN_TOKEN','a'*40)
    for base in ['http://example.test','https://x:y@example.test','https://example.test/path','https://example.test?q=1']:
        monkeypatch.setenv('KINOKO_COMMENTS_API_URL',base);assert not comments_client.status()['configured']
    monkeypatch.setenv('KINOKO_COMMENTS_API_URL','https://example.test')
    assert comments_client.status()['configured'] and 'a'*40 not in str(comments_client.status())
    with pytest.raises(comments_client.CommentsError):comments_client.request('sql',{'sql':'DELETE'})

def test_admin_proxy_fixed_routes_no_redirect_and_timeout(monkeypatch):
    monkeypatch.setenv('KINOKO_COMMENTS_API_URL','https://comments.example.test')
    monkeypatch.setenv('KINOKO_COMMENTS_ADMIN_TOKEN','synthetic-secret-'*4)
    calls=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'{"cases":[]}'
    class Opener:
        def open(self,req,timeout):calls.append((req,timeout));return Response()
    monkeypatch.setattr(comments_client.urllib.request,'build_opener',lambda handler:Opener())
    assert comments_client.request('cases',{'q':'不明'})=={'cases':[]}
    req,timeout=calls[0];assert timeout==10 and req.full_url.startswith('https://comments.example.test/admin/cases?')
    assert req.headers['Authorization'].startswith('Bearer ') and not req.has_header('Origin')
    assert comments_client.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.test') is None

def test_backup_integrity_failure_is_not_success():
    secret='a'*40;body={'version':1,'created_at':1,'data':{}}
    raw=comments_client.canonical(body);backup={**body,'sha256':hashlib.sha256(raw).hexdigest(),'signature':hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()}
    assert comments_client.verify_backup(backup,secret)==backup
    backup['data']['tampered']=True
    with pytest.raises(comments_client.CommentsError):comments_client.verify_backup(backup,secret)


def test_current_render_id_collision_never_mounts_one_thread_on_two_mushrooms():
    p={'version':1,'observations':[source()]};r=registry_for(p);one=build_research_cases(p)[0]
    second=deepcopy(one);second['photos'][0]['observation_id']='different-photo'
    state=prepare([one,second],r)
    assert state['bindings']=={} and len(state['pending'])==2
