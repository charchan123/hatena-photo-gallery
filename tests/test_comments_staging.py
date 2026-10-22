"""Synthetic transport and offline build checks; never contacts Cloudflare."""
import hashlib
import json
import runpy
import urllib.error
from email.message import Message
from pathlib import Path
import pytest
from admin import comments_client as client

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://kinoko-comments-staging-test.fixture.workers.dev'
SECRET='synthetic-admin-key-'*3
ACCESS_SECRET='synthetic-access-key-'*3

@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('KINOKO_COMMENTS_API_URL',ORIGIN)
    monkeypatch.setenv('KINOKO_COMMENTS_ADMIN_TOKEN',SECRET)
    monkeypatch.setenv('KINOKO_COMMENTS_TRANSPORT','staging-access')
    monkeypatch.setenv('KINOKO_COMMENTS_STAGING_ORIGIN',ORIGIN)
    monkeypatch.setenv('KINOKO_COMMENTS_ACCESS_CLIENT_ID','synthetic-id.access')
    monkeypatch.setenv('KINOKO_COMMENTS_ACCESS_CLIENT_SECRET',ACCESS_SECRET)
    return monkeypatch

@pytest.mark.parametrize('name,value',[
    ('KINOKO_COMMENTS_API_URL','https://production.example.test'),
    ('KINOKO_COMMENTS_API_URL','http://kinoko-comments-staging-test.fixture.workers.dev'),
    ('KINOKO_COMMENTS_API_URL',ORIGIN+'/admin'),
    ('KINOKO_COMMENTS_STAGING_ORIGIN','https://other.fixture.workers.dev'),
    ('KINOKO_COMMENTS_ACCESS_CLIENT_SECRET',''),
    ('KINOKO_COMMENTS_ACCESS_CLIENT_ID',''),
    ('KINOKO_COMMENTS_ACCESS_CLIENT_SECRET','x'*40+'\r\nX:evil'),
    ('KINOKO_COMMENTS_ADMIN_TOKEN','x'*40+'\n'),
    ('KINOKO_COMMENTS_TRANSPORT','invalid'),
    ('KINOKO_COMMENTS_TRANSPORT','direct'),
    ('KINOKO_COMMENTS_API_URL','https://[broken'),
])
def test_misconfiguration_is_closed_without_network(configured,name,value):
    configured.setenv(name,value)
    configured.setattr(client.urllib.request,'build_opener',lambda *a:pytest.fail('network forbidden'))
    assert not client.status()['configured']
    with pytest.raises(client.CommentsError):client.request('cases')


def test_service_keys_only_in_server_headers(configured):
    calls=[]
    class Response:
        status=200
        headers=Message();headers['Content-Type']='application/json'
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,n):return b'{"cases":[]}'
    class Opener:
        def open(self,req,timeout):calls.append((req,timeout));return Response()
    configured.setattr(client.urllib.request,'build_opener',lambda *a:Opener())
    assert client.request('cases')=={'cases':[]}
    req,timeout=calls[0];headers={k.lower():v for k,v in req.header_items()}
    assert timeout==10 and req.full_url.startswith(ORIGIN+'/admin/cases?')
    assert headers['cf-access-client-id']=='synthetic-id.access'
    assert headers['cf-access-client-secret']==ACCESS_SECRET
    assert headers['authorization']=='Bearer '+SECRET
    assert not req.has_header('Origin') and not req.has_header('Cookie')
    assert SECRET not in str(client.status()) and ACCESS_SECRET not in str(client.status())
    assert 'client-id' not in str(client.status()).lower()


@pytest.mark.parametrize('code',[301,302,303,307,308,401,403,429,500,503])
def test_access_redirect_auth_and_service_errors_are_sanitized(configured,code):
    class Opener:
        def open(self,*a,**kw):raise urllib.error.HTTPError(ORIGIN,code,SECRET+ACCESS_SECRET,{},None)
    configured.setattr(client.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(client.CommentsError) as e:client.request('cases')
    assert SECRET not in str(e.value) and ACCESS_SECRET not in str(e.value)
    if code in {301,302,303,307,308}:assert '転送を拒否' in str(e.value)
    assert client.NoRedirect().redirect_request(None,None,code,'',{},'https://evil.test') is None


@pytest.mark.parametrize('kind',['html','timeout','invalid-json','too-large'])
def test_failure_is_not_success_and_never_leaks_secret(configured,kind):
    class Response:
        status=200
        headers=Message();headers['Content-Type']='text/html' if kind=='html' else 'application/json'
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,n):return b'x'*(n if kind=='too-large' else 1)
    class Opener:
        def open(self,*a,**kw):
            if kind=='timeout':raise TimeoutError(ACCESS_SECRET)
            return Response()
    configured.setattr(client.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(client.CommentsError) as e:client.request('cases')
    assert ACCESS_SECRET not in str(e.value)


def test_offline_build_only_changes_staging_transport(tmp_path):
    before=(ROOT/'assets/research-comments.js').read_bytes()
    build=runpy.run_path(str(ROOT/'comments/staging/build.py'))['build']
    build(tmp_path)
    js=(tmp_path/'assets/research-comments.js').read_text(encoding="utf-8")
    assert 'credentials: "same-origin"' in js and 'redirect: "error"' in js
    assert 'config.api_url !== location.origin' in js
    assert 'location.protocol !== "https:"' in js
    assert before==(ROOT/'assets/research-comments.js').read_bytes()
    assert 'credentials: "omit"' in before.decode()
    assert (tmp_path/'research.html').read_text(encoding="utf-8").count('data-research-thread=')==66
    assert json.loads((ROOT/'comments/public-config.json').read_text(encoding="utf-8"))=={'version':1,'enabled':False,'api_url':'','turnstile_site_key':'','release_approval':None}
    for name,sha in json.loads((tmp_path/'build-hashes.json').read_text(encoding="utf-8")).items():
        assert hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()==sha


def test_disabled_deployment_templates_have_separate_entry_and_db():
    staging=json.loads((ROOT/'comments/staging/wrangler.example.jsonc').read_text(encoding="utf-8"))
    prod=json.loads((ROOT/'comments/wrangler.jsonc').read_text(encoding="utf-8"))
    assert staging['main']=='worker.mjs' and staging['assets']['run_worker_first'] is True
    assert staging['name']!=prod['name'] and staging['d1_databases'][0]['database_name']!=prod['d1_databases'][0]['database_name']
    for c in [staging,prod]:
        assert c['workers_dev'] is False and c['preview_urls'] is False
        assert c['vars']['PUBLIC_READ_ENABLED']==c['vars']['PUBLIC_WRITE_ENABLED']=='false'
        assert c['vars']['RELEASE_APPROVAL']=='not-approved'
        assert c['d1_databases'][0]['remote'] is False
