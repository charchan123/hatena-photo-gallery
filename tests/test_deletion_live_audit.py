from copy import deepcopy
from pathlib import Path

import article_sync as sync
from deletion_review import audit as live_audit
from test_sync_deletions import fixture,audit,BASE
from test_deletion_guard import config
from test_article_sync import prior,photo,entry


def test_live_audit_reports_identity_without_applying_any_deletion(tmp_path):
    p,s,current=fixture();config(tmp_path);previous=prior(tmp_path,p);sync.write_json(previous/'article-sync-snapshot.json',s)
    candidate=deepcopy(p);candidate['observations']=candidate['observations'][1:]
    candidate['observations'].append(photo('new','new-src','unstable-new'))
    current[sync.digest('new')]=entry('new-src');current[sync.digest('new')]['article_url_hash']=sync.digest('https://blog.example/new')
    before=deepcopy(candidate)
    live={'portal':candidate,'articles':current,'fetch_audit':audit(current),'excluded_draft_hashes':[],'photos':{}}
    report=live_audit(previous,BASE,live,tmp_path,[])
    assert report['identity_simulation']['remaining_existing_ids']==99
    assert report['identity_simulation']['new_gallery_ids']==['obs-'+sync.digest('hatena-photo-v2\0new\0new-src\0'+'0')]
    assert report['identity_simulation']['purpose']=='READ_ONLY_IDENTITY_CHECK_NOT_DELETION_APPROVAL'
    assert report['publication']=='NOT_ATTEMPTED' and report['counts']['deleted_images']==1
    assert candidate==before and len(sync.read_json(previous/'portal-data.json')['observations'])==100
    assert not (tmp_path/'sync-migrations').exists()
