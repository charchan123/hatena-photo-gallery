"""Real generator daily scenarios. Only Atom HTTP and EXIF transport are fixtures."""
from copy import deepcopy
import inspect
import json
from pathlib import Path

import pytest

import article_sync as sync
from admin.sync import SyncReview, ReviewError
from test_article_sync import api_fixture, atom_entry, feed, photo, portal, prior, STAMP


def configure(monkeypatch,tmp_path,responses):
    main,calls=api_fixture(monkeypatch,tmp_path,responses)
    data=tmp_path/'data'
    sync.write_json(data/'best-shots.json',{'version':1,'entries':[{'selection_id':'best-A',
        'observation_id':'obs-published-A','comment':'kept','order':1}],'annual_best':{}})
    sync.write_json(data/'research-identifications.json',{'version':1,'identifications':[]})
    sync.write_json(data/'mushroom-master.json',main.load_mushroom_master())
    monkeypatch.setattr(main,'BEST_SHOTS_FILE',str(data/'best-shots.json'))
    monkeypatch.setattr(main,'CACHE_FILE',str(tmp_path/'cache/exif.json'))
    monkeypatch.setattr(main,'build_exif_cache',lambda entries,cache:{x['src']:{'date':'2025/05/01'} for x in entries})
    original=sync.validate_references
    monkeypatch.setattr(sync,'validate_references',lambda p,b,d:original(p,b,data))
    baseline=prior(tmp_path,portal(photo(aid='A')))
    return main,calls,baseline


def publication(path):
    value={name:sync.read_json(path/name) for name in ('portal-data.json','article-sync-snapshot.json',
        'article-sync-status.json','phase3c-production-status.json')}
    value['publication_sha']='a'*40
    return value


def test_daily_article_update_single_multiple_new_photos_and_next_ids_without_approval(tmp_path,monkeypatch):
    a=atom_entry(); updated=a.replace('2026-10-11T00:00:00Z','2026-10-12T00:00:00Z')
    b=atom_entry('B',src='https://images.example/B.jpg')
    c=atom_entry('C',src='https://images.example/C.jpg')
    d=atom_entry('D',src='https://images.example/D.jpg')
    main,calls,previous=configure(monkeypatch,tmp_path,[feed(a),feed(updated),feed(b+updated),
        feed(c+d+b+updated),feed(updated+b+d+c)])
    # A stale/empty legacy approval file has no authority and is never required.
    empty_manifest=tmp_path/'sync-reviews/approvals.json'
    sync.write_json(empty_manifest,{'approvals':[]})
    report=tmp_path/'report.json';outputs=[]
    for index in range(5):
        output=tmp_path/f'out-{index}'
        assert sync.run(previous,output,report)==0,sync.read_json(report)
        outputs.append(output);previous=output
    records=[sync.read_json(p/'article-sync-status.json') for p in outputs]
    assert records[1]['updated_articles']==1
    assert records[1]['automatic_added_photo_count']==0
    assert records[2]['automatic_added_photo_count']==1
    assert records[3]['automatic_added_photo_count']==2
    assert records[4]['automatic_added_photo_count']==records[4]['new_images']==0
    assert records[4]['preserved_photo_ids']==records[4]['gallery_photo_count']==4
    third=sync.read_json(outputs[3]/'portal-data.json');fourth=sync.read_json(outputs[4]/'portal-data.json')
    assert {x['observation_id'] for x in third['observations']}=={x['observation_id'] for x in fourth['observations']}
    assert all(r['best_shot_references_preserved']==1 for r in records)
    p=publication(outputs[-1]);history=p['article-sync-snapshot.json']['payload']['automatic_additions']
    assert len(history)==3 and all(r['added_at'] for r in history)
    assert sync.validate_snapshot(p['article-sync-snapshot.json'],p['portal-data.json'])
    # Previously added records survive zero-addition days and remain reviewable.
    review=SyncReview(tmp_path/'local-review');review.install(p)
    assert review.page(group='auto_added')['total']==3
    assert review.dashboard()['summary']['automatic_added_photo_count']==0
    assert review.dashboard()['summary']['automatic_history_count']==3
    row=review.page(group='auto_added')['rows'][0]
    review.decide({'candidate_id':row['candidate_id'],'bundle_id':review.bundle_id,'decision':'confirmed'})
    assert review.page(group='reviewed')['total']==1
    assert empty_manifest.read_text()==json.dumps({'approvals':[]},ensure_ascii=False,indent=2)+'\n'
    assert 'review_manifest' not in inspect.signature(sync.run).parameters
    assert len(calls)==5
    # Every successful candidate includes the normal site pages and JSON.
    for p in outputs:
        for name in ('index.html','new-top.html','records.html','features.html','portal-data.json'):
            assert (p/name).is_file()


@pytest.mark.parametrize('change,code',[('ambiguous','CLASSIFICATION_REQUIRES_REVIEW'),
    ('url','DELETION_OR_URL_CHANGE'),('name','NAME_CHANGE'),('delete','ABNORMAL_ARTICLE_DECREASE')])
def test_uncertain_new_and_existing_destructive_changes_still_block_real_generator(tmp_path,monkeypatch,change,code):
    a=atom_entry();b=atom_entry('B',src='https://images.example/B.jpg')
    old=a+b
    if change=='ambiguous':changed=old+atom_entry('X',src='https://images.example/X.jpg').replace('シイタケ','スーパーテスト曖昧タケ')
    elif change=='url':changed=a.replace('https://images.example/A.jpg','https://images.example/replaced.jpg')+b
    elif change=='name':changed=a.replace('シイタケ','ベニテングタケ')+b
    else:changed=a
    main,calls,previous=configure(monkeypatch,tmp_path,[feed(old),feed(changed)])
    # The existing B in this fixture is a prior photo, not a silently approved addition.
    old_portal=portal(photo(aid='A'),photo(aid='B',src='https://images.example/B.jpg',oid='obs-old-B'))
    sync.write_json(previous/'portal-data.json',old_portal)
    sync.write_json(previous/'phase3c-production-status.json',{'cutover_active':True,'validation':{'valid':True},'production_image_count':2})
    output=tmp_path/'output';report=tmp_path/'report.json'
    assert sync.run(previous,output,report)==0,sync.read_json(report)
    before={p.relative_to(output):p.read_bytes() for p in output.rglob('*') if p.is_file()}
    assert sync.run(output,output,report)==1
    assert code in sync.read_json(report)['error_code'],sync.read_json(report)
    assert before=={p.relative_to(output):p.read_bytes() for p in output.rglob('*') if p.is_file()}


def test_confirm_hold_cannot_override_existing_name_gate(tmp_path):
    # Review decisions are local audit only, including old HTTP clients' "adopt".
    assert not hasattr(sync,'gate_new_photos')
    assert not Path('sync-reviews/approvals.json').exists()
    import sync_review
    assert not hasattr(sync_review,'gate_new_photos') and not hasattr(sync_review,'validate_approvals')


def test_read_only_receipt_corruption_cannot_create_an_approval(tmp_path):
    p=portal();articles={sync.digest('article-A'):{'updated_hash':sync.digest('1'),'images':[{
        'url_hash':sync.digest(p['observations'][0]['src']),'ordinal':0,'state':'named_mushroom',
        'reason':'taxonomy_mushroom','name_hash':sync.digest('シイタケ'),'label_hash':sync.digest('シイタケ')}]}}
    bad=[{'observation_id':'invented'}]
    snap=sync.seal_snapshot(articles,p,STAMP,automatic_additions=bad)
    with pytest.raises(sync.SyncError,match='SNAPSHOT_CORRUPT'):sync.validate_snapshot(snap,p)
