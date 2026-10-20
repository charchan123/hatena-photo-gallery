"""Synthetic localhost-only admin; production files and network are never touched."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from admin import core,server
from admin.draft_store import DraftStore
root=Path(sys.argv[1]).resolve();data=root/'data';data.mkdir(parents=True,exist_ok=True)
initial={'best-shots':{'version':1,'entries':[{'selection_id':'dated-existing','observation_id':'dated','comment':'既存のコメント','order':1}],'annual_best':{}},'update-notices':{'version':1,'events':[]},'research-identifications':{'version':1,'identifications':[]},'mushroom-master':{'version':1,'entries':[]},'sources':{'version':1,'sources':[]},'feature-facets':{'version':1,'entries':[]}}
for name,obj in initial.items():
 p=data/(name+'.json')
 if not p.exists():p.write_text(json.dumps(obj,ensure_ascii=False))
def obs(oid,date):return {'observation_id':oid,'gallery_name':'試験きのこ '+oid,'src':'https://fixture.test/'+oid+'.svg','capture':{'date':date},'article':{'title':'隔離した試験記事','article_id':'article-'+oid}}
portal={'version':1,'observations':[obs('undated',None),obs('dated','2025-10-01'),obs('second',None)]}
core.DATA=server.DATA=data
server.load_portal_data=lambda:(portal,'isolated synthetic fixture')
server.DraftStore=lambda:DraftStore(root)
server.SyncReview=lambda:object()
server.DeletionReview=lambda:object()
server.scan_knowledge_batches=lambda **kw:[]
server.repository_status=lambda:{'branch':'isolated-fixture','dirty':False,'gh_authenticated':False}
class Handler(server.Handler):
 def log_message(self,*args):pass
 def do_POST(self):
  if self.path=='/__fixture/source':
   if not self._local_request():return self._json({},403)
   body=self._body();portal['observations'][0]['capture']['date']=body['date'];return self._json({'ok':True})
  return super().do_POST()
app=server.AdminServer(('127.0.0.1',0),Handler)
print(json.dumps({'port':app.server_port}),flush=True)
app.serve_forever()
