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
    snapshot = sync.seal_snapshot(articles, p, T)
    current = deepcopy(articles); current.pop(sync.digest('article-0'))
    return p, snapshot, current


def audit(articles):
    return dict(pagination_complete=True, pages_completed=10, published_articles=len(articles),
        html_articles=len(articles), entries_received=len(articles), drafts_excluded=0,
        html_image_representation_difference_articles=0, content_type_counts={'text/html': len(articles)},
        html_source_counts={'content_html': len(articles)})


def ready(p, s, current, refs=None):
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
        return prs if path.startswith('pulls?') else {'encoding':'base64','size':100,'content':base64.b64encode(json.dumps(config).encode()).decode()}
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
