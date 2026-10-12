"""Actual generator tests; never touch the real Hatena API or publication."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

import article_sync as sync
import sync_exceptions as exc
from test_article_sync import atom_entry,feed
from test_sync_automatic_updates import configure,publication


def setup(monkeypatch,tmp_path,changes=None):
    original=atom_entry()+atom_entry('B',src='https://images.example/B.jpg')
    responses=[feed(original)]+[feed(changes or original)]*12
    main,calls,previous=configure(monkeypatch,tmp_path,responses)
    directory=tmp_path/'name-migrations';directory.mkdir()
    monkeypatch.setattr(exc,'DIRECTORY',directory)
    protect=exc.protected_ids
    monkeypatch.setattr(exc,'protected_ids',lambda p,data=None:protect(p,tmp_path/'data'))
    output=tmp_path/'bootstrap';report=tmp_path/'report.json'
    assert sync.run(previous,output,report)==0,sync.read_json(report)
    return main,output,directory,report


def manifest(output,directory,target='B',new='ベニテングタケ'):
    pub=publication(output);portal=pub['portal-data.json'];snap=pub['article-sync-snapshot.json']
    row=next(r for r in portal['observations'] if r['article']['article_id']==target)
    ah=sync.digest(target);uh=sync.digest(row['src'])
    image=next(i for i in snap['payload']['articles'][ah]['images'] if i['url_hash']==uh)
    payload={'version':1,'operation':'rename_existing_unique_photo',
        'baseline_snapshot_sha256':snap['sha256'],'article_hash':ah,'url_hash':uh,
        'observation_id':row['observation_id'],'old_name':row['gallery_name'],'proposed_name':new,
        'raw_fingerprint':exc.raw_fingerprint(row,image),'approved_at':'2026-10-12T12:00:00+00:00',
        'reason_sha256':sync.digest('人間による写真確認'),'approval':'explicit_human_name_confirmation'}
    m={**payload,'migration_id':sync.payload_hash(payload)};store(directory,m)
    return m


def store(directory,m):
    sync.write_json(directory/(m['migration_id']+'.json'),m)


def test_actual_rename_preserves_id_full_pages_and_next_daily_sync(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path)
    before=sync.read_json(previous/'portal-data.json');m=manifest(previous,directory)
    first=tmp_path/'first';second=tmp_path/'second'
    assert sync.run(previous,first,report)==0,sync.read_json(report)
    assert sync.run(first,second,report)==0,sync.read_json(report)
    for root in (first,second):
        p=sync.read_json(root/'portal-data.json');rows={r['observation_id']:r for r in p['observations']}
        assert set(rows)=={r['observation_id'] for r in before['observations']}
        assert rows[m['observation_id']]['gallery_name']==m['proposed_name']
        assert rows['obs-published-A']['gallery_name']=='シイタケ'
        assert rows[m['observation_id']]['classification']['shadow_gallery_name']=='シイタケ'
        assert rows[m['observation_id']]['classification']['status']=='manual_review_name_conflict'
        assert rows[m['observation_id']]['src']==next(r['src'] for r in before['observations'] if r['observation_id']==m['observation_id'])
        snap=sync.read_json(root/'article-sync-snapshot.json');sync.validate_snapshot(snap,p)
        assert len(snap['payload']['name_migrations'])==1
        assert snap['payload']['articles'][m['article_hash']]['images'][0]['name_hash']==sync.digest('シイタケ')
        assert sync.read_json(root/'phase3c-production-status.json')['validation']['valid']
        assert (root/'ベニテングタケ.html').exists()
        assert 'ベニテングタケ' in (root/'index.html').read_text()
        assert not (root/'sync-migrations').exists() and not (root/'admin').exists()
    status=sync.read_json(report)
    assert status['name_migrations_applied_this_run']==0 and status['best_shot_references_preserved']==1
    assert status['preserved_photo_ids']==2
    # Removal of an applied approval is never silently interpreted as "no change".
    (directory/(m['migration_id']+'.json')).unlink()
    files={f.relative_to(second):f.read_bytes() for f in second.rglob('*') if f.is_file()}
    assert sync.run(second,second,report)==1
    assert sync.read_json(report)['error_code']=='NAME_MIGRATION_MANIFEST_MISSING_OR_CHANGED'
    assert files=={f.relative_to(second):f.read_bytes() for f in second.rglob('*') if f.is_file()}


@pytest.mark.parametrize('damage',['stale','tamper','path','name','source','protected','duplicates'])
def test_narrow_approval_invalid_or_unproved_fails_closed(tmp_path,monkeypatch,damage):
    changes=None
    if damage=='source':changes=atom_entry()+atom_entry('B',src='https://images.example/B.jpg').replace('シイタケ','ヒラタケ')
    if damage=='duplicates':changes=atom_entry()+atom_entry('B',src='https://images.example/B.jpg')+atom_entry('C',src='https://images.example/B.jpg')
    main,previous,directory,report=setup(monkeypatch,tmp_path,changes)
    m=manifest(previous,directory,target='A' if damage=='protected' else 'B')
    file=directory/(m['migration_id']+'.json')
    if damage in {'stale','tamper','name'}:
        file.unlink()
        if damage=='stale':m['baseline_snapshot_sha256']='b'*64
        elif damage=='name':m['proposed_name']='架空のキノコ名'
        else:m['operation']='delete'
        m['migration_id']=sync.payload_hash({k:v for k,v in m.items() if k!='migration_id'});store(directory,m)
    if damage=='path':file.rename(directory/'wrong.json')
    sentinel=tmp_path/'old-site';sentinel.mkdir();(sentinel/'index.html').write_text('old healthy site')
    assert sync.run(previous,sentinel,report)==1
    assert sync.read_json(report)['error_code'].startswith('NAME_MIGRATION')
    assert list(sentinel.iterdir())==[sentinel/'index.html'] and (sentinel/'index.html').read_text()=='old healthy site'


@pytest.mark.parametrize('change',['name','url','delete'])
def test_unapproved_other_photo_change_still_blocked(tmp_path,monkeypatch,change):
    a=atom_entry()
    if change=='name':a=a.replace('シイタケ','ヒラタケ')
    elif change=='url':a=a.replace('https://images.example/A.jpg','https://images.example/replaced.jpg')
    else:a=''
    main,previous,directory,report=setup(monkeypatch,tmp_path,a+atom_entry('B',src='https://images.example/B.jpg'))
    manifest(previous,directory)
    assert sync.run(previous,tmp_path/'candidate',report)==1
    assert sync.read_json(report)['error_code'] in {'DELETION_OR_URL_CHANGE_REQUIRES_REVIEW','PUBLISHED_NAME_CHANGE_REQUIRES_REVIEW','ABNORMAL_ARTICLE_DECREASE'}


def test_high_confidence_new_photo_remains_automatic_alongside_migration(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path,atom_entry()+atom_entry('B',src='https://images.example/B.jpg')+atom_entry('C',src='https://images.example/C.jpg'))
    m=manifest(previous,directory)
    first=tmp_path/'first';second=tmp_path/'second'
    assert sync.run(previous,first,report)==0,sync.read_json(report)
    assert sync.read_json(report)['automatic_added_photo_count']==1
    assert sync.run(first,second,report)==0,sync.read_json(report)
    assert sync.read_json(report)['automatic_added_photo_count']==0
    a=sync.read_json(first/'portal-data.json');b=sync.read_json(second/'portal-data.json')
    assert {r['observation_id'] for r in a['observations']}=={r['observation_id'] for r in b['observations']}


def test_manifest_unknown_fields_symlinks_duplicates_and_ledger_tamper(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path)
    m=manifest(previous,directory);bad=deepcopy(m);bad['url']='https://attacker.example'
    with pytest.raises(sync.SyncError,match='INVALID'):exc.validate_manifest(bad)
    (directory/'evil.json').symlink_to(directory/(m['migration_id']+'.json'))
    with pytest.raises(sync.SyncError):exc.load_manifests(directory)
    (directory/'evil.json').unlink()
    bad=deepcopy(m);bad['approved_at']='2026-10-13T12:00:00+00:00';bad['migration_id']=sync.payload_hash({k:v for k,v in bad.items() if k!='migration_id'});store(directory,bad)
    with pytest.raises(sync.SyncError,match='DUPLICATE'):exc.load_manifests(directory)


def test_research_identity_protected(tmp_path,monkeypatch):
    from test_article_sync import portal,photo
    data=tmp_path/'data';sync.write_json(data/'best-shots.json',{'version':1,'entries':[]})
    sync.write_json(data/'research-identifications.json',{'version':1,'identifications':[]})
    p=portal(photo(name='不明'))
    assert 'obs-published-A' in exc.protected_ids(p,data)


def test_applied_migration_blocks_later_source_change_but_unrelated_update_is_allowed(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path)
    manifest(previous,directory);first=tmp_path/'first'
    assert sync.run(previous,first,report)==0
    original=atom_entry()+atom_entry('B',src='https://images.example/B.jpg')
    # Exact image evidence remains identical when only update timestamps change.
    main.requests.get=lambda *a,**k:type('Response',(),{'status_code':200,'text':feed(original.replace('2026-10-11T00:00:00Z','2026-10-12T00:00:00Z'))})()
    second=tmp_path/'second';assert sync.run(first,second,report)==0,sync.read_json(report)
    main.requests.get=lambda *a,**k:type('Response',(),{'status_code':200,'text':feed(atom_entry()+atom_entry('B',src='https://images.example/B.jpg').replace('シイタケ','ヒラタケ'))})()
    assert sync.run(second,tmp_path/'third',report)==1
    assert sync.read_json(report)['error_code']=='NAME_MIGRATION_SOURCE_CHANGED'


def test_applied_ledger_and_manifest_modification_cannot_be_reauthorized(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path)
    m=manifest(previous,directory);first=tmp_path/'first'
    assert sync.run(previous,first,report)==0
    snap=sync.read_json(first/'article-sync-snapshot.json')
    bad=deepcopy(snap);bad['payload']['name_migrations'][0]['name_sha256']='a'*64;bad['sha256']=sync.payload_hash(bad['payload'])
    with pytest.raises(sync.SyncError):sync.validate_snapshot(bad,sync.read_json(first/'portal-data.json'))
    file=directory/(m['migration_id']+'.json');file.unlink();m['reason_sha256']='a'*64
    m['migration_id']=sync.payload_hash({k:v for k,v in m.items() if k!='migration_id'});store(directory,m)
    assert sync.run(first,tmp_path/'second',report)==1
    assert sync.read_json(report)['error_code']=='NAME_MIGRATION_MANIFEST_MISSING_OR_CHANGED'


def test_existing_unclassified_legacy_photo_can_receive_human_name_without_detector_rewrite(tmp_path,monkeypatch):
    from test_article_sync import portal,photo
    xml=feed(atom_entry()+atom_entry('B',src='https://images.example/B.jpg').replace('シイタケ','テスト未分類タケ'))
    main,calls,previous=configure(monkeypatch,tmp_path,[xml]*10)
    old=portal(photo(aid='A'),photo(aid='B',src='https://images.example/B.jpg',oid='obs-legacy-B',name='テスト未分類タケ',state='legacy_review'))
    sync.write_json(previous/'portal-data.json',old)
    sync.write_json(previous/'phase3c-production-status.json',{'cutover_active':True,'validation':{'valid':True},'production_image_count':2})
    directory=tmp_path/'migrations';directory.mkdir();monkeypatch.setattr(exc,'DIRECTORY',directory)
    protect=exc.protected_ids;monkeypatch.setattr(exc,'protected_ids',lambda p,data=None:protect(p,tmp_path/'data'))
    bootstrap=tmp_path/'bootstrap';report=tmp_path/'report.json'
    assert sync.run(previous,bootstrap,report)==0,sync.read_json(report)
    raw=next(r for r in sync.read_json(bootstrap/'portal-data.json')['observations'] if r['observation_id']=='obs-legacy-B')
    assert raw['classification']['status'] not in sync.SAFE_NEW
    manifest(bootstrap,directory,new='ヒラタケ')
    corrected=tmp_path/'corrected';assert sync.run(bootstrap,corrected,report)==0,sync.read_json(report)
    row=next(r for r in sync.read_json(corrected/'portal-data.json')['observations'] if r['observation_id']=='obs-legacy-B')
    assert row['gallery_name']=='ヒラタケ'
    assert row['classification']['status']==raw['classification']['status']
    assert row['classification']['detected_label']==raw['classification']['detected_label']
    assert sync.run(corrected,tmp_path/'next',report)==0,sync.read_json(report)
