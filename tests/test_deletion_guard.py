"""The deletion adapter composes with unchanged production safety contracts."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

import pytest

import article_sync as sync
import deletion_guard as g
import sync_deletions as d
from deletion_protection import collect
from deletion_approvals import validate,archive_context
from research_ui import build_research_cases
from test_sync_deletions import fixture,audit,T,BASE
from test_article_sync import prior,photo,portal,entry


class Store:
    def __init__(self,history):self.history=deepcopy(history);self.writes=0;self.fail=False
    def load(self,anchor=None):d.validate_history(self.history,anchor);return deepcopy(self.history)
    def save(self,history):
        if self.fail:raise sync.SyncError('DELETION_HISTORY_STORAGE_UNAVAILABLE')
        self.history=deepcopy(history);self.writes+=1;return 'persisted'


def config(root):
    sync.write_json(root/'data/best-shots.json',{'version':1,'entries':[],'annual_best':{}})
    sync.write_json(root/'data/research-identifications.json',{'version':1,'identifications':[]})
    sync.write_json(root/'data/mushroom-master.json',{'version':1,'entries':[]})


def setup(tmp_path,monkeypatch,*,research=False,history_rows=False):
    p,s,current=fixture();config(tmp_path)
    if research:
        p['observations'][0]['gallery_name']='不明'
        if history_rows:
            case=build_research_cases(p)[0]
            registry={'version':1,'identifications':[{'identification_id':'identified-1','case_id':case['case_id'],
                'article':case['article'],'original_gallery_name':'不明','identified_name':'シイタケ',
                'identified_at':T,'mushroom_master_id':None,'status':'identified','note':'研究記録を保持'}]}
            sync.write_json(tmp_path/'data/research-identifications.json',registry)
        s=sync.seal_snapshot(s['payload']['articles'],p,T)
    prot=collect(p,s,tmp_path,[])
    rows=d.plan(s,p,current,audit(current),set(),prot)
    h=[]
    for run,hour in [('one',0),('two',7)]:h=d.append_event(h,d.event_for(rows,s,BASE,prot,current,run,(d.instant(T)+timedelta(hours=hour)).isoformat()))
    class Clock:
        @staticmethod
        def now(tz=None):return d.instant(T)+timedelta(hours=8)
    monkeypatch.setattr(g,'datetime',Clock)
    return p,s,current,prot,rows,h


def test_guard_must_persist_before_authorizing_and_failed_publication_keeps_history(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    store=Store(h);store.fail=True
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=store,pending=[])
    with pytest.raises(sync.SyncError,match='STORAGE_UNAVAILABLE'):guard.prepare(current,audit(current),set())
    assert guard.targets==[] and store.history==h
    store.fail=False
    effective=guard.prepare(current,audit(current),set())
    assert store.writes==1 and len(effective['observations'])==99
    guard.failure('OUTPUT_INTEGRITY_ERROR')
    assert store.writes==2 and len(store.history)==4


def test_preview_does_not_write_or_count_as_an_independent_fetch(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    for count,expected in [(1,False),(2,True)]:
        store=Store(h[:count]);guard=g.DeletionGuard(p,s,BASE,tmp_path,'preview',store=store,pending=[],preview=True)
        if expected:assert len(guard.prepare(current,audit(current),set())['observations'])==99
        else:
            with pytest.raises(sync.SyncError,match='CONFIRMATION_OR_APPROVAL_PENDING'):guard.prepare(current,audit(current),set())
        guard.failure('anything');assert store.writes==0


def test_protected_case_blocks_all_publication_but_persists_detection(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch,research=True)
    store=Store(h);guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=store,pending=[])
    with pytest.raises(sync.SyncError,match='CONFIRMATION_OR_APPROVAL_PENDING'):guard.prepare(current,audit(current),set())
    assert guard.targets==[] and len(store.history)==3
    assert store.history[-1]['event']['findings'][0]['protection'][0]['kind']=='research'
    assert len(build_research_cases(p)[0]['photos'])==1


def test_failed_fetch_invalidates_streak_and_remains_durable(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    store=Store(h);guard=g.DeletionGuard(p,s,BASE,tmp_path,'outage',store=store,pending=[])
    guard.failure('API_PAGINATION_INCOMPLETE')
    assert store.history[-2]['event']['healthy'] is False
    assert store.history[-2]['event']['candidates']=={}
    assert store.history[-1]['event']['outcome']=='BLOCKED'
    assert not d.confirmed(store.history,rows[0],s['sha256'],prot['sha256'],(d.instant(T)+timedelta(hours=9)).isoformat())


def test_receipt_replay_reappearance_and_output_isolation(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    effective=guard.prepare(current,audit(current),set());output=tmp_path/'output';output.mkdir()
    ledger=guard.finish(effective,current,output,(d.instant(T)+timedelta(hours=8)).isoformat())
    sealed=sync.seal_snapshot(current,effective,T,deletions=ledger,deletion_history_head=d.validate_history(guard.history))
    sync.validate_snapshot(sealed,effective)
    again=g.DeletionGuard(effective,sealed,BASE,tmp_path,'four',store=Store(guard.history),pending=[])
    assert again.prepare(current,audit(current),set())==effective
    assert again.finish(effective,current,output,(d.instant(T)+timedelta(hours=9)).isoformat())==ledger
    returned=deepcopy(current);returned[sync.digest('article-0')]=entry('url-0')
    with pytest.raises(sync.SyncError,match='REAPPEARED'):again.prepare(returned,audit(returned),set())
    (output/'research.html').write_text('<img src="url-0">'+rows[0]['observation_id'])
    with pytest.raises(sync.SyncError,match='RETIRED_REFERENCE_IN_OUTPUT'):again.finish(effective,current,output,T)
    sealed['payload']['deletions'][0]['mode']='manual'
    sealed['sha256']=sync.payload_hash(sealed['payload'])
    with pytest.raises(sync.SyncError,match='SNAPSHOT_CORRUPT'):sync.validate_snapshot(sealed,effective)


def approval(row,s,prot,case,p,registry,action='archive_research'):
    m={'version':1,'candidate_id':row['candidate_id'],'fingerprint':row['fingerprint'],'baseline':s['sha256'],
       'protection':prot['sha256'],'action':action,'approved_at':T,'reason_sha256':sync.digest('人間が明示確認'),
       'case_ids':[case['case_id']],'registry_before':registry,'replacement_id':None,'supersedes':None,
       'archives':[{'case':case,'observations':[r for r in p['observations'] if r['observation_id'] in {x['observation_id'] for x in case['photos']}],
            'identifications':[r for r in registry['identifications'] if r['case_id']==case['case_id']]}]}
    m['approval_id']=sync.payload_hash(m);return validate(m)


@pytest.mark.parametrize('history_rows',[False,True])
@pytest.mark.parametrize('action',['archive_research','retire_research'])
def test_explicit_archive_keeps_original_history_in_manifest_only(tmp_path,monkeypatch,history_rows,action):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch,research=True,history_rows=history_rows)
    registry=sync.read_json(tmp_path/'data/research-identifications.json');case=build_research_cases(p)[0]
    m=approval(rows[0],s,prot,case,p,registry,action)
    sync.write_json(tmp_path/'sync-migrations/photo-deletions'/ (m['approval_id']+'.json'),m)
    after={**registry,'identifications':[]};sync.write_json(tmp_path/'data/research-identifications.json',after)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    effective=guard.prepare(current,audit(current),set())
    assert len(effective['observations'])==99 and guard.targets[0]['mode']=='manual'
    assert build_research_cases(effective)==[]
    assert len(m['archives'][0]['identifications'])==int(history_rows)
    output=tmp_path/'output';output.mkdir();(output/'research.html').write_text('公開研究室：このケースは非表示')
    receipts=guard.finish(effective,current,output,(d.instant(T)+timedelta(hours=8)).isoformat())
    assert receipts[0]['approval_id']==m['approval_id']
    assert 'archives' not in receipts[0]
    assert sync.read_json(tmp_path/'sync-migrations/photo-deletions'/(m['approval_id']+'.json'))==m
    # Entire old capsule remains immutable across subsequent daily runs.
    sealed=sync.seal_snapshot(current,effective,T,deletions=receipts,deletion_history_head=d.validate_history(guard.history))
    next_run=g.DeletionGuard(effective,sealed,BASE,tmp_path,'four',store=Store(guard.history),pending=[])
    assert next_run.prepare(current,audit(current),set())==effective


def test_archive_cannot_discard_history_or_live_case_photo(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch,research=True,history_rows=True)
    registry=sync.read_json(tmp_path/'data/research-identifications.json');case=build_research_cases(p)[0]
    m=approval(rows[0],s,prot,case,p,registry)
    with pytest.raises(sync.SyncError,match='REGISTRY_NOT_EXACT'):archive_context([m],p,registry,{'entries':[]},rows)
    bad=deepcopy(m);bad['archives'][0]['identifications']=[]
    with pytest.raises(sync.SyncError,match='HISTORY_CHANGED'):archive_context([bad],p,{'version':1,'identifications':[]},{'entries':[]},rows)
    with pytest.raises(sync.SyncError,match='STILL_HAS_LIVE_PHOTOS'):archive_context([m],p,{'version':1,'identifications':[]},{'entries':[]},[])


def test_article_url_move_and_zero_image_article_are_not_deletions(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    current[sync.digest('other')]=entry('different');current[sync.digest('other')]['article_url_hash']=sync.digest(p['observations'][0]['article']['url'])
    rows=d.plan(s,p,current,audit(current),set(),prot)
    assert 'ARTICLE_URL_MOVED_OR_CHANGED' in rows[0]['identity_issues']
    s['payload']['articles'][sync.digest('no-image')]={'updated_hash':'a'*64,'article_url_hash':'b'*64,'images':[]};s['sha256']=sync.payload_hash(s['payload'])
    with pytest.raises(sync.SyncError,match='ARTICLE_IDENTITY_UNAVAILABLE'):d.plan(s,p,current,audit(current),set(),prot)


def test_sync_adapter_runs_original_identity_and_reference_validators(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    previous=prior(tmp_path,p);sync.write_json(previous/'article-sync-snapshot.json',s)
    run=sync.SyncRun(previous,tmp_path/'report.json')
    run.deletions=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    files=[];metadata={};shadows=[]
    (tmp_path/'articles').mkdir()
    for row in p['observations'][1:]:
        file=tmp_path/'articles'/(row['observation_id']+'.html');file.write_text('<img src="'+row['src']+'">');files.append(file)
        metadata[str(file)]={**row['article'],'updated':'1'}
        shadows.append({'article_path':str(file),'src':row['src'],'subject_type':'mushroom','gallery_name':row['gallery_name'],
                        'detected_label':row['gallery_name'],'classification_reason':'taxonomy_mushroom'})
    run.capture(files,metadata);run.status['fetch_audit']=audit(current)
    candidate=d.without_targets(p,rows)
    result=run.reconcile(candidate,shadows)
    assert result==candidate
    output=tmp_path/'output';output.mkdir()
    sync.write_json(output/'portal-data.json',result)
    sync.write_json(output/'phase3c-production-status.json',{'cutover_active':True,'validation':{'valid':True},'production_image_count':99})
    sync.write_json(output/'portal-data-status.json',{'build_ok':True})
    for file in ['index','new-top','records','season','features','research','best-shots','favorite']:(output/(file+'.html')).write_text('validated fixture')
    run.finalize(output,[True],tmp_path/'data')
    sealed=sync.read_json(output/'article-sync-snapshot.json');sync.validate_snapshot(sealed,result)
    assert sealed['payload']['deletions'][0]['observation_id']=='obs-0'
    assert run.status['preserved_photo_ids']==99
    with pytest.raises(sync.SyncError,match='GUARD_REQUIRED'):sync.SyncRun(output,tmp_path/'again.json')


def test_automatic_addition_receipt_is_retained_after_safe_retirement(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    old=p['observations'][0]
    receipt={'observation_id':old['observation_id'],'article_hash':sync.digest(old['article']['article_id']),
        'url_hash':sync.digest(old['src']),'ordinal':0,'classification_status':'confirmed_named_mushroom',
        'reason':'taxonomy_mushroom','added_at':T}
    s['payload']['automatic_additions']=[receipt];s['sha256']=sync.payload_hash(s['payload'])
    sync.validate_snapshot(s,p)
    prot=collect(p,s,tmp_path,[]);rows=d.plan(s,p,current,audit(current),set(),prot)
    assert not rows[0]['protection']
    history=[]
    for run,hour in [('one',0),('two',7)]:history=d.append_event(history,d.event_for(rows,s,BASE,prot,current,run,(d.instant(T)+timedelta(hours=hour)).isoformat()))
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(history),pending=[])
    effective=guard.prepare(current,audit(current),set());output=tmp_path/'output';output.mkdir()
    ledger=guard.finish(effective,current,output,(d.instant(T)+timedelta(hours=8)).isoformat())
    assert ledger[0]['automatic_addition_receipt']==receipt
    sealed=sync.seal_snapshot(current,effective,T,automatic_additions=[],deletions=ledger,deletion_history_head=d.validate_history(guard.history))
    sync.validate_snapshot(sealed,effective)


def multi_case(tmp_path,monkeypatch,*,all_missing):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch,research=True)
    ah=sync.digest('article-0')
    for n in (1,2):
        row=photo('article-0','research-extra-'+str(n),'obs-research-extra-'+str(n),name='不明')
        row['article']=deepcopy(p['observations'][0]['article']);p['observations'].append(row)
        s['payload']['articles'][ah]['images'].extend(entry(row['src'])['images'])
    p['summary']['observation_count']=len(p['observations'])
    s=sync.seal_snapshot(s['payload']['articles'],p,T)
    if not all_missing:
        current[ah]=deepcopy(s['payload']['articles'][ah]);current[ah]['images'].pop(0)
    prot=collect(p,s,tmp_path,[]);rows=d.plan(s,p,current,audit(current),set(),prot);history=[]
    for run,hour in [('one',0),('two',7)]:history=d.append_event(history,d.event_for(rows,s,BASE,prot,current,run,(d.instant(T)+timedelta(hours=hour)).isoformat()))
    return p,s,current,prot,rows,history


def test_research_single_photo_removal_preserves_case_and_its_history(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=multi_case(tmp_path,monkeypatch,all_missing=False)
    case=build_research_cases(p)[0];assert len(case['photos'])==3
    registry=sync.read_json(tmp_path/'data/research-identifications.json')
    m=approval(rows[0],s,prot,case,p,registry,'approve_research_photo')
    sync.write_json(tmp_path/'sync-migrations/photo-deletions'/(m['approval_id']+'.json'),m)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    effective=guard.prepare(current,audit(current),set());remaining=build_research_cases(effective)
    assert remaining[0]['case_id']==case['case_id'] and len(remaining[0]['photos'])==2
    assert len(m['archives'][0]['observations'])==3
    assert sync.read_json(tmp_path/'data/research-identifications.json')==registry


def test_multi_photo_case_retirement_requires_individual_approval_of_every_photo(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=multi_case(tmp_path,monkeypatch,all_missing=True)
    case=build_research_cases(p)[0];registry=sync.read_json(tmp_path/'data/research-identifications.json')
    first=approval(rows[0],s,prot,case,p,registry)
    sync.write_json(tmp_path/'sync-migrations/photo-deletions'/(first['approval_id']+'.json'),first)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    with pytest.raises(sync.SyncError,match='CONFIRMATION_OR_APPROVAL_PENDING'):guard.prepare(current,audit(current),set())
    for row in rows[1:]:
        m=approval(row,s,prot,case,p,registry);sync.write_json(tmp_path/'sync-migrations/photo-deletions'/(m['approval_id']+'.json'),m)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'four',store=Store(h),pending=[])
    effective=guard.prepare(current,audit(current),set())
    assert build_research_cases(effective)==[] and len(guard.targets)==3
    assert all(t['mode']=='manual' for t in guard.targets)


def test_case_continuation_cannot_remove_the_only_research_photo(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch,research=True)
    m=approval(rows[0],s,prot,build_research_cases(p)[0],p,sync.read_json(tmp_path/'data/research-identifications.json'),'approve_research_photo')
    sync.write_json(tmp_path/'sync-migrations/photo-deletions'/(m['approval_id']+'.json'),m)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    with pytest.raises(sync.SyncError,match='CASE_WOULD_DISAPPEAR'):guard.prepare(current,audit(current),set())


@pytest.mark.parametrize('leak',['article','escaped_image'])
def test_generated_tree_cannot_retain_deleted_article_or_escaped_photo_url(tmp_path,monkeypatch,leak):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    # Use real URLs, as a generated public page would.
    old=p['observations'][0];old['src']='https://photos.example/deleted.jpg'
    aid=sync.digest(old['article']['article_id'])
    s['payload']['articles'][aid]['images'][0]['url_hash']=sync.digest(old['src'])
    s=sync.seal_snapshot(s['payload']['articles'],p,T)
    prot=collect(p,s,tmp_path,[]);rows=d.plan(s,p,current,audit(current),set(),prot);h=[]
    for run,hour in [('one',0),('two',7)]:h=d.append_event(h,d.event_for(rows,s,BASE,prot,current,run,(d.instant(T)+timedelta(hours=hour)).isoformat()))
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    effective=guard.prepare(current,audit(current),set());output=tmp_path/'out';output.mkdir()
    value=old['article']['url'] if leak=='article' else old['src'].replace('/','\\/')
    (output/'old.json').write_text('"'+value+'"')
    with pytest.raises(sync.SyncError,match='RETIRED_REFERENCE_IN_OUTPUT'):guard.finish(effective,current,output,T)


def test_retired_article_url_reuse_under_new_atom_id_is_blocked(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    effective=guard.prepare(current,audit(current),set());output=tmp_path/'out';output.mkdir()
    ledger=guard.finish(effective,current,output,(d.instant(T)+timedelta(hours=8)).isoformat())
    sealed=sync.seal_snapshot(current,effective,T,deletions=ledger,deletion_history_head=d.validate_history(guard.history))
    reappeared=deepcopy(current)
    # Different Atom ID and different photograph, but the same retired article URL.
    reappeared[sync.digest('replacement-atom')]=entry('different-image')
    reappeared[sync.digest('replacement-atom')]['article_url_hash']=s['payload']['articles'][sync.digest('article-0')]['article_url_hash']
    again=g.DeletionGuard(effective,sealed,BASE,tmp_path,'four',store=Store(guard.history),pending=[])
    with pytest.raises(sync.SyncError,match='REAPPEARED'):
        again.prepare(reappeared,audit(reappeared),set())


def test_retired_article_link_is_still_rejected_on_later_publication(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    effective=guard.prepare(current,audit(current),set());output=tmp_path/'out';output.mkdir()
    ledger=guard.finish(effective,current,output,(d.instant(T)+timedelta(hours=8)).isoformat())
    sealed=sync.seal_snapshot(current,effective,T,deletions=ledger,deletion_history_head=d.validate_history(guard.history))
    again=g.DeletionGuard(effective,sealed,BASE,tmp_path,'four',store=Store(guard.history),pending=[])
    again.prepare(current,audit(current),set())
    (output/'stale.html').write_text('<a href="'+p['observations'][0]['article']['url']+'">old</a>')
    with pytest.raises(sync.SyncError,match='RETIRED_REFERENCE_IN_OUTPUT'):
        again.finish(effective,current,output,(d.instant(T)+timedelta(hours=8)).isoformat())


def test_each_receipt_must_anchor_its_actual_candidate_in_persisted_history(tmp_path,monkeypatch):
    p,s,current,prot,rows,h=setup(tmp_path,monkeypatch)
    guard=g.DeletionGuard(p,s,BASE,tmp_path,'three',store=Store(h),pending=[])
    effective=guard.prepare(current,audit(current),set());output=tmp_path/'out';output.mkdir()
    ledger=guard.finish(effective,current,output,(d.instant(T)+timedelta(hours=8)).isoformat())
    # Even a freshly resealed snapshot cannot excuse a bogus per-target anchor.
    ledger[0]['history_head']='f'*64
    ledger[0]['sha256']=sync.payload_hash({k:v for k,v in ledger[0].items() if k!='sha256'})
    sealed=sync.seal_snapshot(current,effective,T,deletions=ledger,deletion_history_head=d.validate_history(guard.history))
    with pytest.raises(sync.SyncError,match='RECEIPT_HISTORY_MISMATCH'):
        g.DeletionGuard(effective,sealed,BASE,tmp_path,'four',store=Store(guard.history),pending=[])
