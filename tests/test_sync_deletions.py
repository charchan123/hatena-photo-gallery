"""Independent fixtures: no production edits, network, or source credentials."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import subprocess

import pytest

import article_sync as sync
import sync_deletions as d
from deletion_history import GitHistory
from deletion_protection import open_selections, collect
from test_article_sync import photo, portal, entry

T = '2026-10-15T00:00:00+00:00'
BASE = '1' * 40


def protection(refs=None):
    result = {'version': 1, 'complete': True, 'references': refs or {}, 'sources': {}}
    return {**result, 'sha256': sync.payload_hash(result)}


def fixture():
    p = portal(*(photo('article-' + str(i), 'url-' + str(i), 'obs-' + str(i)) for i in range(100)))
    articles = {sync.digest('article-' + str(i)): entry('url-' + str(i)) for i in range(100)}
    for row in p['observations']: row['article']['url']='https://blog.example/'+sync.digest(row['article']['article_id'])
    for ah,a in articles.items(): a['article_url_hash']=sync.digest('https://blog.example/'+ah)
    snapshot = sync.seal_snapshot(articles, p, T)
    current = deepcopy(articles); current.pop(sync.digest('article-0'))
    return p, snapshot, current


def audit(articles):
    return dict(pagination_complete=True, pages_completed=10, published_articles=len(articles),
        html_articles=len(articles), entries_received=len(articles), drafts_excluded=0,
        html_image_representation_difference_articles=0, content_type_counts={'text/html': len(articles)},
        html_source_counts={'content_html': len(articles)})


def ready(p, s, current, refs=None):
    for ah,a in current.items(): a.setdefault('article_url_hash',sync.digest('https://blog.example/'+ah))
    prot = protection(refs); rows = d.plan(s, p, current, audit(current), set(), prot)
    history = []
    for run, hour in [('run-1', 0), ('run-2', 7)]:
        at = (d.instant(T) + timedelta(hours=hour)).isoformat()
        history = d.append_event(history, d.event_for(rows, s, BASE, prot, current, run, at))
    return rows, history, prot, at


def test_complete_independent_article_deletion_and_remaining_ids():
    p, s, current = fixture(); rows, history, prot, at = ready(p, s, current)
    selected = d.select(rows, s, history, prot, at)
    assert len(selected) == 1 and selected[0]['mode'] == 'automatic'
    assert selected[0]['kind'] == 'article_deleted' and selected[0]['observation_id'] == 'obs-0'
    effective = d.without_targets(p, selected)
    assert len(effective['observations']) == 99
    candidate = deepcopy(effective)
    for row in candidate['observations']: row['observation_id'] = 'temporary-' + row['observation_id']
    assert sync.reconcile_ids(candidate, effective) == effective
    assert len(p['observations']) == 100


def test_new_images_and_articles_do_not_invalidate_independent_deletion():
    p, s, current = fixture(); current[sync.digest('brand-new')] = entry('brand-new-photo')
    rows, history, prot, at = ready(p, s, current)
    assert len(d.select(rows, s, history, prot, at)) == 1
    new = d.without_targets(p, rows); new['observations'].append(photo('brand-new', 'brand-new-photo', 'temporary'))
    new['summary']['observation_count'] += 1
    reconciled = sync.reconcile_ids(new, d.without_targets(p, rows))
    assert reconciled['observations'][-1]['observation_id'].startswith('obs-')
    assert all(r['observation_id'] == p['observations'][i+1]['observation_id'] for i,r in enumerate(reconciled['observations'][:-1]))


def test_individual_photo_deletion_preserves_exact_survivor_sequence():
    p, s, current = fixture(); ah = sync.digest('article-0')
    s['payload']['articles'][ah]['images'].append(entry('second')['images'][0]); s['sha256'] = sync.payload_hash(s['payload'])
    current[ah] = deepcopy(s['payload']['articles'][ah]); current[ah]['images'].pop(0)
    rows, history, prot, at = ready(p, s, current)
    assert d.select(rows, s, history, prot, at)[0]['kind'] == 'photo_deleted'


@pytest.mark.parametrize('field,value', [('pagination_complete',False), ('pages_completed',0), ('html_articles',98), ('entries_received',100), ('drafts_excluded',1), ('html_image_representation_difference_articles',1)])
def test_incomplete_api_never_plans(field,value):
    p,s,current=fixture(); a=audit(current);a[field]=value
    with pytest.raises(sync.SyncError,match='DELETION_FETCH_NOT_COMPLETE'): d.plan(s,p,current,a,set(),protection())


@pytest.mark.parametrize('hours',[0,1,5,73])
def test_confirmation_interval_and_independence(hours):
    p,s,current=fixture();prot=protection();rows=d.plan(s,p,current,audit(current),set(),prot)
    h=[]
    for run,hour in [('first',0),('second',hours)]:
        at=(d.instant(T)+timedelta(hours=hour)).isoformat();h=d.append_event(h,d.event_for(rows,s,BASE,prot,current,run,at))
    assert not d.select(rows,s,h,prot,at)


def test_transient_missing_reappeared_outage_and_context_change_reset():
    p,s,current=fixture();rows,h,prot,at=ready(p,s,current)
    for middle in ('outage','reappeared','changed'):
        first=h[:1];ev=d.event_for(rows,s,BASE,prot,current,'middle',(d.instant(T)+timedelta(hours=3)).isoformat())
        if middle=='outage':ev['healthy']=False;ev['candidates']={}
        if middle=='reappeared':ev['candidates']={}
        if middle=='changed':ev['protection']='f'*64
        first=d.append_event(first,ev);first=d.append_event(first,h[-1]['event'])
        assert not d.select(deepcopy(rows),s,first,prot,at)


def test_duplicate_run_does_not_count_or_silently_replace():
    p,s,current=fixture();rows,h,prot,at=ready(p,s,current)
    assert d.append_event(h,h[0]['event'])==h
    changed=deepcopy(h[0]['event']);changed['healthy']=False
    with pytest.raises(sync.SyncError,match='RUN_ALREADY_RECORDED'):d.append_event(h,changed)


@pytest.mark.parametrize('kind',['best_shot','annual_best','pending_best_shot','research','identification','curated_history','curated_page','receipt'])
def test_protected_photos_cannot_be_auto_deleted_or_plain_approved(kind):
    p,s,current=fixture();rows,h,prot,at=ready(p,s,current,{'obs-0':[{'kind':kind,'id':'important'}]})
    assert not d.select(rows,s,h,prot,at)
    decision=dict(candidate_id=rows[0]['candidate_id'],fingerprint=rows[0]['fingerprint'],baseline=s['sha256'],protection=prot['sha256'],action='approve')
    assert not d.select(rows,s,h,prot,at,[decision])
    assert rows[0]['status']=='approval_pending'


@pytest.mark.parametrize('scenario',['replacement','moved','duplicate','reordered','labels','draft'])
def test_uncertain_identity_is_not_approvable(scenario):
    p,s,current=fixture(); ah=sync.digest('article-0');excluded=set()
    if scenario=='replacement':current[ah]=entry('replacement')
    elif scenario=='moved':current[sync.digest('moved')]=entry('url-0')
    elif scenario=='duplicate':
        s['payload']['articles'][ah]['images'].append({**s['payload']['articles'][ah]['images'][0],'ordinal':1})
    elif scenario in {'reordered','labels'}:
        for src in ('survivor-1','survivor-2'):s['payload']['articles'][ah]['images'].extend(entry(src)['images'])
        current[ah]=deepcopy(s['payload']['articles'][ah]);current[ah]['images'].pop(0)
        if scenario=='reordered':current[ah]['images'].reverse()
        else:current[ah]['images'][0]['label_hash']='f'*64
    elif scenario=='draft':excluded={ah}
    for key,a in current.items(): a.setdefault('article_url_hash',sync.digest('https://blog.example/'+key))
    s['sha256']=sync.payload_hash(s['payload']);a=audit(current)
    if excluded:a.update(entries_received=len(current)+1,drafts_excluded=1)
    prot=protection();rows=d.plan(s,p,current,a,excluded,prot)
    assert rows and rows[0]['identity_issues']
    _,h,_,at=ready(p,s,current) if not excluded else (None,[],None,T)
    assert not d.select(rows,s,h,prot,at)


def test_mass_deletion_is_manual_review_even_with_stable_ids():
    p,s,current=fixture()
    for n in range(1,4):current.pop(sync.digest('article-'+str(n)))
    rows,h,prot,at=ready(p,s,current)
    assert all(r['mass_review'] for r in rows)
    assert not d.select(rows,s,h,prot,at)


@pytest.mark.parametrize('mutation',['payload','previous','sequence','truncate'])
def test_history_tampering_is_detected(mutation):
    p,s,current=fixture();rows,h,prot,at=ready(p,s,current);anchor=h[-1]['sha256']
    if mutation=='payload':h[0]['event']['healthy']=False
    if mutation=='previous':h[1]['previous']='0'*64
    if mutation=='sequence':h[0]['seq']=2
    if mutation=='truncate':h=h[:1]
    with pytest.raises(sync.SyncError,match='HISTORY_CORRUPT'):d.validate_history(h,anchor)


def test_snapshot_and_reference_tampering():
    p,s,current=fixture();s['payload']['articles'].pop(sync.digest('article-1'))
    with pytest.raises(sync.SyncError,match='SNAPSHOT_CORRUPT'):d.plan(s,p,current,audit(current),set(),protection())
    p,s,current=fixture();prot=protection();prot['references']['obs-0']=[]
    with pytest.raises(sync.SyncError,match='PROTECTION_CORRUPT'):d.plan(s,p,current,audit(current),set(),prot)
    with pytest.raises(sync.SyncError,match='REFERENCES_UNAVAILABLE'):d.plan(s,p,current,audit(current),set(),{'complete':False})


def test_stale_approval_cannot_authorize_changed_source():
    p,s,current=fixture();rows,h,prot,at=ready(p,s,current)
    decision={'candidate_id':rows[0]['candidate_id'],'fingerprint':'f'*64}
    with pytest.raises(sync.SyncError,match='APPROVAL_STALE'):d.select(rows,s,h,prot,at,[decision])


def test_open_prs_are_dynamic_complete_and_head_bound():
    import base64
    prs=[{'number':n,'head':{'sha':str(n)*40,'repo':{'full_name':'charchan123/hatena-photo-gallery'}}} for n in (1,2)]
    config={'version':1,'entries':[],'annual_best':{}}
    def api(path):
        if '/files?' in path:return []
        if path.startswith('pulls?'): return prs
        if path.startswith('git/trees/'): return {'truncated':False,'tree':[{'path':'data/best-shots.json','type':'blob','mode':'100644','sha':'blob'}]}
        return {'sha':'blob','encoding':'base64','size':100,'content':base64.b64encode(json.dumps(config).encode()).decode()}
    assert [x['number'] for x in open_selections(api)]==[1,2]
    with pytest.raises(sync.SyncError,match='REFERENCES_UNAVAILABLE'):open_selections(lambda path:None)
    prs[0]['head']['repo']['full_name']='someone/fork'
    with pytest.raises(sync.SyncError,match='PENDING_FORK'):open_selections(api)


def test_history_durable_on_failed_job_and_git_race(tmp_path):
    def git(*args,cwd=tmp_path):return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
    bare=tmp_path/'remote.git';git('init','--bare',str(bare))
    work=tmp_path/'work';git('init',str(work));git('remote','add','origin',str(bare),cwd=work)
    p,s,current=fixture();rows,h,prot,at=ready(p,s,current)
    store=GitHistory(work);assert store.load()==[];store.save(h[:1])
    other=GitHistory(work);assert other.load()==h[:1]
    stale=GitHistory(work);stale.load();other.save(h)
    changed=d.append_event(h[:1],d.event_for(rows,s,BASE,prot,current,'racing',at))
    with pytest.raises(sync.SyncError,match='STORAGE_UNAVAILABLE'):stale.save(changed)
    assert GitHistory(work).load(h[-1]['sha256'])==h
    # No publication/main branch was created in the audit-only repository.
    assert git('for-each-ref','--format=%(refname)',cwd=bare)=='refs/heads/sync-deletion-audit'


def test_absent_best_file_requires_complete_tree_proof():
    prs=[{'number':2,'head':{'sha':'2'*40,'repo':{'full_name':'charchan123/hatena-photo-gallery'}}}]
    def api(path):
        if '/files?' in path:return []
        return prs if path.startswith('pulls?') else {'truncated':False,'tree':[]}
    result=open_selections(api)
    assert result[0]['file_absent_verified'] and result[0]['config']['entries']==[]
    def truncated(path):return prs if path.startswith('pulls?') else {'truncated':True,'tree':[]}
    with pytest.raises(sync.SyncError,match='TREE_INCOMPLETE'):open_selections(truncated)


def test_old_hold_is_superseded_without_overwriting_history():
    from deletion_approvals import validate,latest
    m={'version':1,'candidate_id':'a'*64,'fingerprint':'b'*64,'baseline':'c'*64,'protection':'d'*64,
        'action':'hold','approved_at':T,'reason_sha256':'e'*64,'case_ids':[],'archives':[],
        'registry_before':None,'replacement_id':None,'supersedes':None}
    m['approval_id']=sync.payload_hash(m);validate(m)
    changed={**m,'action':'approve','approved_at':(d.instant(T)+timedelta(hours=1)).isoformat(),'supersedes':m['approval_id']}
    changed['approval_id']=sync.payload_hash({k:v for k,v in changed.items() if k!='approval_id'});validate(changed)
    assert latest([m,changed])==[changed] and m['action']=='hold'
    fork={**changed,'reason_sha256':'f'*64};fork['approval_id']=sync.payload_hash({k:v for k,v in fork.items() if k!='approval_id'})
    with pytest.raises(sync.SyncError,match='CHAIN_INVALID'):latest([m,changed,fork])


def test_unmerged_hold_protects_source_occurrence(tmp_path):
    from test_deletion_guard import config
    p,s,current=fixture();config(tmp_path)
    basic=protection();rows=d.plan(s,p,current,audit(current),set(),basic)
    hold={'candidate_id':rows[0]['candidate_id'],'baseline':s['sha256']}
    pending=[{'number':400,'head':'4'*40,'config':{'version':1,'entries':[],'annual_best':{}},'deletion_holds':[hold]}]
    prot=collect(p,s,tmp_path,pending);row=d.plan(s,p,current,audit(current),set(),prot)[0]
    assert row['protection']==[{'kind':'pending_deletion_hold','id':'PR #400'}]


def test_workflow_retry_is_recordable_but_not_independent_confirmation():
    p,s,current=fixture();prot=protection();rows=d.plan(s,p,current,audit(current),set(),prot)
    h=[]
    for run,hour in [('actions:123:attempt:1',0),('actions:123:attempt:2',8)]:
        at=(d.instant(T)+timedelta(hours=hour)).isoformat();h=d.append_event(h,d.event_for(rows,s,BASE,prot,current,run,at))
    assert len(h)==2 and not d.select(rows,s,h,prot,at)
    at=(d.instant(T)+timedelta(hours=15)).isoformat()
    h=d.append_event(h,d.event_for(rows,s,BASE,prot,current,'actions:456:attempt:1',at))
    assert len(d.select(rows,s,h,prot,at))==1


def test_retry_cannot_erase_an_already_independent_confirmation_pair():
    p,s,current=fixture();prot=protection();rows=d.plan(s,p,current,audit(current),set(),prot);h=[]
    for run,hour in [('actions:123:attempt:1',0),('actions:456:attempt:1',7),('actions:123:attempt:2',8)]:
        at=(d.instant(T)+timedelta(hours=hour)).isoformat();h=d.append_event(h,d.event_for(rows,s,BASE,prot,current,run,at))
    assert len(d.select(rows,s,h,prot,at))==1


@pytest.mark.parametrize('by_key',[True,False])
def test_curated_id_mapping_keys_and_unlisted_image_urls_are_protected(tmp_path,by_key):
    from test_deletion_guard import config
    p,s,current=fixture();config(tmp_path)
    if by_key:sync.write_json(tmp_path/'data/curated.json',{'obs-0':{'caption':'重要な参照'}})
    else:
        # An old DOM image need not have a gallery observation. URL/hash refs
        # still protect it, even though by-observation lookup is impossible.
        p['observations']=p['observations'][1:];p['summary']['observation_count']-=1
        s=sync.seal_snapshot(s['payload']['articles'],p,T)
        sync.write_json(tmp_path/'data/curated.json',{'feature_photo':'url-0'})
    prot=collect(p,s,tmp_path,[]);row=d.plan(s,p,current,audit(current),set(),prot)[0]
    assert row['protection']==[{'kind':'curated_history','id':'data/curated.json'}]
    assert row['observation_id']==('obs-0' if by_key else None)


def test_shared_url_deleted_from_every_article_is_still_ambiguous():
    p,s,current=fixture()
    # Both occurrences disappear together; the URL still cannot identify a
    # unique source photograph or prove that it was not moved/replaced.
    s['payload']['articles'][sync.digest('article-1')]['images']=deepcopy(s['payload']['articles'][sync.digest('article-0')]['images'])
    p['observations'][1]['src']='url-0'
    s=sync.seal_snapshot(s['payload']['articles'],p,T);current.pop(sync.digest('article-1'))
    rows=d.plan(s,p,current,audit(current),set(),protection())
    assert len(rows)==2
    assert all('URL_MOVED_OR_SHARED' in r['identity_issues'] for r in rows)


def test_git_history_network_timeout_is_bounded_and_sanitized(tmp_path,monkeypatch):
    import deletion_history
    def timeout(*args,**kwargs):
        assert kwargs['timeout']==60
        raise subprocess.TimeoutExpired(args[0],60,stderr='PRIVATE_TRANSPORT_BODY')
    monkeypatch.setattr(deletion_history.subprocess,'run',timeout)
    with pytest.raises(sync.SyncError,match='^DELETION_HISTORY_STORAGE_UNAVAILABLE$'):GitHistory(tmp_path).load()


def test_git_history_rejects_non_regular_event_blobs(tmp_path):
    def git(*args,cwd=None,data=None):
        return subprocess.check_output(['git',*args],cwd=cwd or tmp_path,text=True,input=data,stderr=subprocess.DEVNULL).strip()
    bare=tmp_path/'remote.git';git('init','--bare',str(bare))
    work=tmp_path/'work';git('init',str(work));git('remote','add','origin',str(bare),cwd=work)
    p,s,current=fixture();rows,h,prot,at=ready(p,s,current)
    store=GitHistory(work);store.load();store.save(h[:1])
    event='events/00000001-'+h[0]['sha256']+'.json'
    original=store.commit;git('read-tree',original,cwd=work)
    blob=git('rev-parse',original+':'+event,cwd=work)
    git('update-index','--cacheinfo','120000',blob,event,cwd=work)
    tree=git('write-tree',cwd=work)
    bad=git('-c','user.name=fixture','-c','user.email=fixture@example.test','commit-tree',tree,cwd=work,data='Fixture storage mode corruption\n')
    git('fetch',str(work),bad,cwd=bare)
    git('update-ref','refs/heads/sync-deletion-audit',bad,original,cwd=bare)
    with pytest.raises(sync.SyncError,match='STORAGE_UNSAFE'):GitHistory(work).load()


@pytest.mark.parametrize('reference',['observation','url','hash'])
def test_unmerged_curated_json_references_block_automatic_deletion(tmp_path,reference):
    from test_deletion_guard import config
    p,s,current=fixture();config(tmp_path)
    value={'observation':'obs-0','url':'url-0','hash':sync.digest('url-0')}[reference]
    pending=[{'number':401,'config':{'version':1,'entries':[],'annual_best':{}},
              'curated':[{'path':'data/future-feature.json','text':json.dumps({'cover':value})}]}]
    prot=collect(p,s,tmp_path,pending);rows=d.plan(s,p,current,audit(current),set(),prot)
    assert rows[0]['protection']==[{'kind':'pending_curated_reference','id':'PR #401:data/future-feature.json'}]


def test_unmerged_static_feature_image_is_protected(tmp_path):
    from test_deletion_guard import config
    p,s,current=fixture();config(tmp_path)
    src='https://photos.example/protected.jpg';p['observations'][0]['src']=src
    s['payload']['articles'][sync.digest('article-0')]['images'][0]['url_hash']=sync.digest(src)
    s=sync.seal_snapshot(s['payload']['articles'],p,T)
    pending=[{'number':402,'config':{'version':1,'entries':[],'annual_best':{}},
              'curated':[{'path':'feature.html','text':'<img src="'+src+'">'}]}]
    prot=collect(p,s,tmp_path,pending);row=d.plan(s,p,current,audit(current),set(),prot)[0]
    assert row['protection']==[{'kind':'pending_curated_reference','id':'PR #402:feature.html'}]


@pytest.mark.parametrize('files',['complete','unavailable','truncated'])
def test_open_pr_curated_content_requires_complete_changed_file_enumeration(files):
    import base64
    prs=[{'number':401,'head':{'sha':'1'*40,'repo':{'full_name':'charchan123/hatena-photo-gallery'}}}]
    node={'path':'data/feature.json','type':'blob','mode':'100644','sha':'curated'}
    text=json.dumps({'cover':'obs-0'})
    def api(path):
        if path.startswith('pulls?'):return prs
        if path.startswith('git/trees/'):return {'truncated':False,'tree':[node]}
        if '/files?' in path:
            row={'filename':node['path'],'status':'added'}
            return [row] if files=='complete' else [row]*100 if files=='truncated' else None
        return {'sha':'curated','encoding':'base64','size':len(text),'content':base64.b64encode(text.encode()).decode()}
    if files=='complete':
        result=open_selections(api)
        assert result[0]['curated']==[{'path':'data/feature.json','text':text}]
    else:
        with pytest.raises(sync.SyncError,match='REFERENCES_UNAVAILABLE|PAGINATION_INCOMPLETE'):open_selections(api)


@pytest.mark.parametrize('hours',[6,72])
def test_exact_confirmation_interval_limits_are_inclusive(hours):
    p,s,current=fixture();prot=protection();rows=d.plan(s,p,current,audit(current),set(),prot);history=[]
    for run,hour in [('first',0),('second',hours)]:
        at=(d.instant(T)+timedelta(hours=hour)).isoformat()
        history=d.append_event(history,d.event_for(rows,s,BASE,prot,current,run,at))
    assert len(d.select(rows,s,history,prot,at))==1
