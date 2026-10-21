"""Real Windows-compatible localhost admin; synthetic API endpoint only."""
import json,sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from admin import server,core,comments_client
from admin.draft_store import DraftStore
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True);data=root/'data';data.mkdir(exist_ok=True)
for path in (Path(__file__).resolve().parents[2]/'data').glob('*.json'):
    shutil.copy2(path,data/path.name)
portal=json.loads((root/'portal-data.json').read_text(encoding='utf-8'))
core.DATA=server.DATA=data
server.load_portal_data=lambda:(portal,'read-only local fixture')
server.DraftStore=lambda:DraftStore(root)
server.SyncReview=server.DeletionReview=lambda:object()
server.scan_knowledge_batches=lambda **kw:[]
server.repository_status=lambda:{'gh_authenticated':False,'branch':'isolated-fixture','dirty':False}
comments_client.settings=lambda:('http://127.0.0.1:'+sys.argv[2],'isolated-browser-secret-'*3,True)
class Handler(server.Handler):
    def log_message(self,*args):pass
app=server.AdminServer(('127.0.0.1',0),Handler)
print(json.dumps({'port':app.server_port}),flush=True);app.serve_forever()
