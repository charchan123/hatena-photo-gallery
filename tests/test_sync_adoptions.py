"""Real generator with fixture Atom/EXIF/image transports; no live writes."""
from copy import deepcopy
from pathlib import Path
import html
import re
import pytest

import article_sync as sync
import sync_adoptions as adoption
from test_article_sync import atom_entry,feed
from test_sync_automatic_updates import configure,publication


def unlisted(aid='U',src='https://cdn-ak.f.st-hatena.com/images/fixture-U.jpg',draft='no'):
    entry=atom_entry(aid,src=src,draft=draft)
    return re.sub(r'<content type="text/html">.*?</content>',
        '<content type="text/html">'+html.escape('<img src="'+src+'">')+'</content>',entry)


def setup(monkeypatch,tmp_path,extra=None):
    xml=feed(atom_entry()+(extra or unlisted()))
    main,calls,previous=configure(monkeypatch,tmp_path,[xml]*60)
    directory=tmp_path/'adoptions';directory.mkdir();monkeypatch.setattr(adoption,'DIRECTORY',directory)
    monkeypatch.setattr(adoption,'image_hash',lambda src:sync.digest('fixture bytes '+src))
    output=tmp_path/'bootstrap';report=tmp_path/'report.json'
    assert sync.run(previous,output,report)==0,sync.read_json(report)
    return main,output,directory,report


def sources(main,pub):
    metadata=main.load_article_metadata();files=[Path(p) for p in metadata]
    shadows=main.extract_shadow_metadata(files,taxonomy=main.load_subject_taxonomy())
    return adoption.source_occurrences(files,metadata,shadows,pub['article-sync-snapshot.json']['payload']['articles'])


def manifest(main,published,directory,aid='U',name='ヒラタケ'):
    pub=publication(published);occ=sources(main,pub)
    key=next(k for k in occ if k[0]==sync.digest(aid));source=occ[key]
    fields={'version':1,'operation':'adopt_unique_public_mushroom_photo',
        'baseline_snapshot_sha256':pub['article-sync-snapshot.json']['sha256'],
        'article_hash':key[0],'url_hash':key[1],'ordinal':key[2],
        'observation_id':adoption.stable_id(*key),'decision':'unknown_mushroom' if name=='不明' else 'named_mushroom',
        'gallery_name':name,'raw_fingerprint':source['fingerprint'],
        'image_content_sha256':adoption.image_hash(source['src']),
        'approved_at':'2026-10-12T09:00:00+00:00','reason_sha256':sync.digest('human verified fixture photo'),
        'approval':'explicit_human_photo_adoption'}
    m={**fields,'migration_id':sync.payload_hash(fields)};store(directory,m);return m


def store(directory,m):sync.write_json(directory/(m['migration_id']+'.json'),m)


def test_one_adoption_named_full_generation_next_day_stable_id_and_original_evidence(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path)
    old=sync.read_json(previous/'portal-data.json');assert len(old['observations'])==1
    m=manifest(main,previous,directory);first=tmp_path/'first';second=tmp_path/'second'
    assert sync.run(previous,first,report)==0,sync.read_json(report)
    one=sync.read_json(report)
    assert one['manual_adoptions_applied_this_run']==1 and one['automatic_added_photo_count']==0
    assert one['preserved_photo_ids']==1 and one['best_shot_references_preserved']==1
    assert sync.run(first,second,report)==0,sync.read_json(report)
    for path in (first,second):
        p=sync.read_json(path/'portal-data.json');row=next(r for r in p['observations'] if r['observation_id']==m['observation_id'])
        assert row['gallery_name']=='ヒラタケ' and row['classification']['status']==adoption.STATUS
        assert row['classification']['detected_label'] is None and row['classification']['classification_confidence']=='low'
        assert row['human_review']['decision']=='named_mushroom'
        assert next(r for r in p['observations'] if r['observation_id']=='obs-published-A')['gallery_name']=='シイタケ'
        snap=sync.read_json(path/'article-sync-snapshot.json');sync.validate_snapshot(snap,p)
        assert len(snap['payload']['manual_adoptions'])==1
        assert snap['payload']['articles'][m['article_hash']]['images'][0]['state']=='unclassified'
        phase=sync.read_json(path/'phase3c-production-status.json')
        assert phase['validation']['valid'] and phase['raw_phase3c_image_count']==1
        assert phase['manual_adoption_count']==1 and phase['production_image_count']==2
        assert (path/'ヒラタケ.html').exists()
        for file in ('index.html','new-top.html','season.html','features.html','records.html'):
            assert (path/file).is_file()
        assert not (path/'admin').exists() and not (path/'sync-migrations').exists()
    assert sync.read_json(report)['manual_adoptions_applied_this_run']==0
    assert sync.read_json(report)['preserved_photo_ids']==2


def test_multiple_adoptions_known_and_unknown_plus_automatic_new_photo(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path,unlisted()+unlisted('V','https://cdn-ak.f.st-hatena.com/images/fixture-V.jpg'))
    named=manifest(main,previous,directory);unknown=manifest(main,previous,directory,'V','不明')
    xml=feed(atom_entry()+atom_entry('N',src='https://images.example/auto-N.jpg')+unlisted()+unlisted('V','https://cdn-ak.f.st-hatena.com/images/fixture-V.jpg'))
    main.requests.get=lambda *a,**k:type('Response',(),{'status_code':200,'text':xml})()
    first=tmp_path/'first';second=tmp_path/'second'
    assert sync.run(previous,first,report)==0,sync.read_json(report)
    assert sync.read_json(report)['manual_adoptions_applied_this_run']==2 and sync.read_json(report)['automatic_added_photo_count']==1
    assert sync.run(first,second,report)==0,sync.read_json(report)
    one=sync.read_json(first/'portal-data.json');two=sync.read_json(second/'portal-data.json')
    assert len(two['observations'])==4 and {r['observation_id'] for r in one['observations']}=={r['observation_id'] for r in two['observations']}
    assert sync.read_json(report)['manual_adoptions_applied_this_run']==sync.read_json(report)['automatic_added_photo_count']==0
    from research_ui import build_research_cases
    case=build_research_cases(two)[0]
    assert case['photos'][0]['observation_id']==unknown['observation_id']


def test_no_human_approval_does_not_adopt_unclassified_and_normal_updates_still_succeed(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path)
    current=tmp_path/'next';assert sync.run(previous,current,report)==0
    assert len(sync.read_json(current/'portal-data.json')['observations'])==1
    assert not sync.read_json(current/'article-sync-snapshot.json')['payload'].get('manual_adoptions')


@pytest.mark.parametrize('damage',['stale','name','hash','content','path','tamper','duplicate','draft','delete','url','raw_gallery'])
def test_invalid_or_changed_adoption_is_blocked_and_old_site_kept(tmp_path,monkeypatch,damage):
    main,previous,directory,report=setup(monkeypatch,tmp_path);m=manifest(main,previous,directory)
    if damage in {'stale','name','hash','tamper'}:
        (directory/(m['migration_id']+'.json')).unlink()
        if damage=='stale':m['baseline_snapshot_sha256']='a'*64
        elif damage=='name':m['gallery_name']='推測未登録タケ'
        elif damage=='hash':m['raw_fingerprint']='b'*64
        else:m['operation']='delete'
        m['migration_id']=sync.payload_hash({k:v for k,v in m.items() if k!='migration_id'});store(directory,m)
    if damage=='path':(directory/(m['migration_id']+'.json')).rename(directory/'wrong.json')
    if damage=='content':monkeypatch.setattr(adoption,'image_hash',lambda _:sync.digest('changed bytes'))
    if damage in {'duplicate','draft','delete','url','raw_gallery'}:
        u=unlisted()
        if damage=='duplicate':u+=unlisted('V')
        elif damage=='draft':u=unlisted(draft='yes')
        elif damage=='delete':u=''
        elif damage=='url':u=unlisted(src='https://cdn-ak.f.st-hatena.com/images/replaced.jpg')
        else:u=atom_entry('U',src='https://cdn-ak.f.st-hatena.com/images/fixture-U.jpg')
        xml=feed(atom_entry()+u);main.requests.get=lambda *a,**k:type('Response',(),{'status_code':200,'text':xml})()
    sentinel=tmp_path/'site';sentinel.mkdir();(sentinel/'index.html').write_text('last healthy publication')
    assert sync.run(previous,sentinel,report)==1
    assert sync.read_json(report)['error_code'].startswith(('ADOPTION_','DELETION_','ABNORMAL_'))
    assert len(list(sentinel.iterdir()))==1 and (sentinel/'index.html').read_text()=='last healthy publication'


def test_applied_manifest_missing_and_future_source_changes_are_blocked(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path);m=manifest(main,previous,directory)
    first=tmp_path/'first';assert sync.run(previous,first,report)==0
    (directory/(m['migration_id']+'.json')).unlink()
    assert sync.run(first,tmp_path/'second',report)==1
    assert sync.read_json(report)['error_code']=='ADOPTION_MANIFEST_MISSING_OR_CHANGED'


def test_name_migration_and_manual_adoption_are_independent_and_both_persist(tmp_path,monkeypatch):
    from test_sync_exceptions import manifest as name_manifest
    import sync_exceptions
    main,previous,directory,report=setup(monkeypatch,tmp_path,atom_entry('B',src='https://images.example/B.jpg')+unlisted())
    names=tmp_path/'names';names.mkdir();monkeypatch.setattr(sync_exceptions,'DIRECTORY',names)
    protect=sync_exceptions.protected_ids;monkeypatch.setattr(sync_exceptions,'protected_ids',lambda p,data=None:protect(p,tmp_path/'data'))
    nm=name_manifest(previous,names);am=manifest(main,previous,directory)
    first=tmp_path/'first';assert sync.run(previous,first,report)==0,sync.read_json(report)
    assert sync.run(first,tmp_path/'second',report)==0,sync.read_json(report)
    snap=sync.read_json(tmp_path/'second/article-sync-snapshot.json')
    assert len(snap['payload']['name_migrations'])==len(snap['payload']['manual_adoptions'])==1


def test_image_transport_is_bounded_read_only_no_redirect_no_auth_and_decode_checked(monkeypatch):
    import io
    from PIL import Image
    buffer=io.BytesIO();Image.new('RGB',(2,2),'green').save(buffer,format='PNG');data=buffer.getvalue()
    calls=[]
    class Response:
        status_code=200;headers={'Content-Type':'image/png'};closed=False
        def iter_content(self,n):yield data
        def close(self):self.closed=True
    response=Response()
    def get(url,**kwargs):calls.append((url,kwargs));return response
    monkeypatch.setattr(adoption.requests,'get',get)
    src='https://cdn-ak.f.st-hatena.com/images/public.jpg'
    import hashlib
    assert adoption.image_hash(src)==hashlib.sha256(data).hexdigest()
    args=calls[0][1];assert args['stream'] is True and args['allow_redirects'] is False and args['timeout']==(10,30)
    request=type('Request',(),{'headers':{'Authorization':'must disappear'}})()
    args['auth'](request);assert 'Authorization' not in request.headers and response.closed
    for url in ('http://127.0.0.1/secret','https://user:secret@cdn-ak.f.st-hatena.com/images/p.jpg','https://evil.example/images/p.jpg'):
        with pytest.raises(sync.SyncError):adoption.image_hash(url)
    assert len(calls)==1
    response.headers['Content-Type']='text/html'
    with pytest.raises(sync.SyncError,match='FETCH_FAILED'):adoption.image_hash(src)


def test_image_changes_between_projection_and_final_gate_are_blocked(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path);m=manifest(main,previous,directory)
    calls=[]
    def changing(src):
        calls.append(src)
        return m['image_content_sha256'] if len(calls)==1 else sync.digest('changed after projection')
    monkeypatch.setattr(adoption,'image_hash',changing)
    assert sync.run(previous,tmp_path/'candidate',report)==1
    assert sync.read_json(report)['error_code']=='ADOPTION_IMAGE_CONTENT_CHANGED'


def test_manifests_and_snapshot_ledger_reject_unknown_fields_symlinks_and_tamper(tmp_path,monkeypatch):
    main,previous,directory,report=setup(monkeypatch,tmp_path);m=manifest(main,previous,directory)
    bad=deepcopy(m);bad['url']='https://arbitrary.example'
    with pytest.raises(sync.SyncError):adoption.validate_manifest(bad)
    (directory/'evil.json').symlink_to(directory/(m['migration_id']+'.json'))
    with pytest.raises(sync.SyncError):adoption.load_manifests()
    (directory/'evil.json').unlink()
    first=tmp_path/'first';assert sync.run(previous,first,report)==0
    snap=sync.read_json(first/'article-sync-snapshot.json');p=sync.read_json(first/'portal-data.json')
    snap['payload']['manual_adoptions'][0]['url_hash']='a'*64;snap['sha256']=sync.payload_hash(snap['payload'])
    with pytest.raises(sync.SyncError):sync.validate_snapshot(snap,p)
