"""Real localhost handler/proxy with a test-only HTTPS-to-loopback adapter."""
import json,sys,shutil,os,urllib.request,urllib.parse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from admin import server,core,comments_client
from admin.draft_store import DraftStore
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True);data=root/'data';data.mkdir(exist_ok=True)
for path in (Path(__file__).resolve().parents[2]/'data').glob('*.json'):shutil.copy2(path,data/path.name)
portal=json.loads((root/'portal-data.json').read_text(encoding='utf-8'))
core.DATA=server.DATA=data
server.load_portal_data=lambda:(portal,'read-only local fixture')
server.DraftStore=lambda:DraftStore(root)
server.SyncReview=server.DeletionReview=lambda:object()
server.scan_knowledge_batches=lambda **kw:[]
server.repository_status=lambda:{'gh_authenticated':False,'branch':'isolated-fixture','dirty':False}
origin='https://kinoko-comments-staging-test.fixture.workers.dev'
os.environ.update(KINOKO_COMMENTS_API_URL=origin,KINOKO_COMMENTS_ADMIN_TOKEN='synthetic-admin-secret-'*3,
    KINOKO_COMMENTS_TRANSPORT='staging-access',KINOKO_COMMENTS_STAGING_ORIGIN=origin,
    KINOKO_COMMENTS_ACCESS_CLIENT_ID='synthetic-test-id.access',KINOKO_COMMENTS_ACCESS_CLIENT_SECRET='synthetic-service-key-'*3)
real_build=urllib.request.build_opener
class LocalTransport:
    def open(self,req,timeout):
        assert req.full_url.startswith(origin+'/admin/')
        local=urllib.request.Request('http://127.0.0.1:'+sys.argv[2]+req.full_url[len(origin):],data=req.data,method=req.method,headers=dict(req.header_items()))
        return real_build(comments_client.NoRedirect()).open(local,timeout=timeout)
comments_client.urllib.request.build_opener=lambda handler:LocalTransport()
class Handler(server.Handler):
    def log_message(self,*args):pass
app=server.AdminServer(('127.0.0.1',0),Handler)
print(json.dumps({'port':app.server_port}),flush=True);app.serve_forever()
