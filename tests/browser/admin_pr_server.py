"""Synthetic localhost admin; git/gh publication boundary is intercepted."""
from pathlib import Path
import json
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from admin import core,server
from admin.draft_store import DraftStore
from admin.git_workflow import GitWorkflowError
root=Path(sys.argv[1]).resolve();data=root/'data';data.mkdir(parents=True,exist_ok=True)
initial={'best-shots':{'version':1,'entries':[{'selection_id':'fixture-best','observation_id':'fixture','comment':'元のコメント','order':1}],'annual_best':{}},'update-notices':{'version':1,'events':[]},'research-identifications':{'version':1,'identifications':[]},'mushroom-master':{'version':1,'entries':[]},'sources':{'version':1,'sources':[]},'feature-facets':{'version':1,'entries':[]}}
for name,obj in initial.items():
    path=data/(name+'.json')
    if not path.exists():path.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
portal={'version':1,'observations':[{'observation_id':'fixture','gallery_name':'架空のきのこ','src':'https://fixture.test/photo.svg','capture':{'date':'2024-01-01'},'article':{'title':'架空の記事'}}]}
core.DATA=server.DATA=data
server.load_portal_data=lambda:(portal,'synthetic localhost')
server.DraftStore=lambda:DraftStore(root)
server.SyncReview=server.DeletionReview=lambda:object()
server.scan_knowledge_batches=lambda **kw:[]
server.repository_status=lambda:{'branch':'synthetic','dirty':False,'gh_authenticated':True}
state={'mode':'success','calls':0,'state_error':False}
def publish(files,validation,operation,*,baseline):
    assert files==json.loads(app.draft_store.path.read_text(encoding='utf-8'))['files']
    assert baseline['data/best-shots.json']['entries'][0]['comment']=='元のコメント'
    state['calls']+=1
    time.sleep(.4)
    if state['mode']=='stale':raise GitWorkflowError('最新mainと元データが不一致です。下書きをバックアップして手動照合してください')
    if state['mode']=='auth':raise GitWorkflowError('GitHub認証が必要です。gh auth loginで再認証してください')
    if state['mode']=='validation':raise GitWorkflowError('入力検証に失敗しました。変更内容を確認してください')
    if state['mode']=='refresh':state['state_error']=True
    return {'url':'https://github.com/fixture/test/pull/123','draft':True,'ci_status':'pending'}
server.create_pull_request=publish
class Handler(server.Handler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/api/state' and state['state_error']:
            state['state_error']=False
            return self._json({'error':'isolated refresh failure'},500)
        if self.path=='/__fixture/state' and self._local_request():
            return self._json({**state,'saved':json.loads(app.draft_store.path.read_text(encoding='utf-8')) if app.draft_store.path.exists() else None})
        return super().do_GET()
    def do_POST(self):
        if self.path=='/__fixture/mode' and self._local_request():
            state['mode']=self._body()['mode'];return self._json({'ok':True})
        return super().do_POST()
app=server.AdminServer(('127.0.0.1',0),Handler)
save=app.draft_store.verify_saved
def durable(draft):
    if state['mode']=='save':raise OSError('disk full (isolated fixture)')
    return save(draft)
app.draft_store.verify_saved=durable
print(json.dumps({'port':app.server_port}),flush=True)
app.serve_forever()
