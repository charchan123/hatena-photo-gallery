"""Read-only protection evidence, pinned to the audited publication and PR heads."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from article_sync import read_json,validate_snapshot
from best_shot_ui import validate_best_shot_config
from research_ui import build_research_cases
from feature_overlay import validate_feature_production_state

MAIN='4f953c7f0723f8ab44d72a12fcaf00579776ee66'
PUBLICATION='757cbfc868452d3bb892849fce0e2122cd8c566e'
PR111='4448c3431a1c275ca686e9e2a0a7736fc67f0841'


def blob(ref,path):return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)
def object_(ref,path):return json.loads(blob(ref,path))


def verify():
    portal=object_(PUBLICATION,'portal-data.json');snapshot=object_(PUBLICATION,'article-sync-snapshot.json')
    validate_snapshot(snapshot,portal)
    live=read_json(Path(__file__).parent/'live-audit-38742041771.json')
    assert live['baseline_commit']==PUBLICATION and live['snapshot_sha256']==snapshot['sha256']
    assert len(live['removed'])==16 and len(live['added_source'])==20
    old={r['observation_id']:r for r in portal['observations']};missing={r['observation_id'] for r in live['removed']}
    main_config=object_(MAIN,'data/best-shots.json');pending=object_(PR111,'data/best-shots.json')
    validate_best_shot_config(main_config,portal);validate_best_shot_config(pending,portal)
    assert not missing & {r['observation_id'] for r in main_config['entries']+pending['entries']}
    cases=[c for c in build_research_cases(portal) if any(p['observation_id'] in missing for p in c['photos'])]
    assert {c['case_id'] for c in cases}=={'research-940496f1ccdb136f','research-f9cb62e956fa8604'}
    assert {c['case_id']:len(c['photos']) for c in cases}=={'research-940496f1ccdb136f':1,'research-f9cb62e956fa8604':6}
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',MAIN,'data'],cwd=ROOT,text=True).splitlines()
    names+=['sync_retirement.py','sync_exceptions.py','sync_adoptions.py','main.py','best_shot_ui.py',
        'research_ui.py','research_identifications.py','admin/core.py','admin/git_workflow.py',
        'sync-migrations/hatena-draft-photo-retirement-2026-10-12.json']
    unchanged=[]
    for name in names:
        data=(ROOT/name).read_bytes();assert data==blob(MAIN,name),name
        unchanged.append({'path':name,'sha256':hashlib.sha256(data).hexdigest()})
    production=validate_feature_production_state()
    counts={'mushrooms':len(production['mushroom_master']['entries']),
        'sources':len(production['sources']['sources']),
        'assignments':sum(len(e['assignments']) for e in production['feature_facets']['entries']),'overlays':production['overlay_count']}
    assert counts=={'mushrooms':141,'sources':419,'assignments':373,'overlays':0}
    result={'result':'PASS','main_sha':MAIN,'publication_sha':PUBLICATION,'snapshot_sha256':snapshot['sha256'],
        'published_photos':len(old),'published_articles':len(snapshot['payload']['articles']),
        'main_best_shots':len(main_config['entries']),'pending_best_shots':len(pending['entries']),
        'best_shot_missing_conflicts':[],'affected_research_cases':[{'case_id':c['case_id'],'name':c['gallery_name'],'photo_count':len(c['photos']),'missing_photo_count':sum(p['observation_id'] in missing for p in c['photos'])} for c in cases],
        'counts':counts,'unchanged_files':unchanged,'existing_retirement_receipt':snapshot['payload']['retirement'],
        'publication':'NOT_ATTEMPTED','actual_deletion_approvals_added':0}
    destination=Path(__file__).parent/'protection-verification.json'
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    fields=['observation_id','gallery_name','article_title','article_url','article_id','src','kind','author_approved','protected_reasons']
    with (destination.parent/'missing-photos.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n");writer.writeheader()
        for row in live['removed']:
            writer.writerow({**{k:row.get(k) for k in fields if k not in {'author_approved','protected_reasons'}},
                'author_approved':row['article_hash']=='f4c1c839abafe71eb16494d0d921cd96df6cbf32aefce8eee19a8807a90a923e',
                'protected_reasons':json.dumps(row['protection'],ensure_ascii=False)})
    print(json.dumps({k:v for k,v in result.items() if k not in {'unchanged_files','existing_retirement_receipt'}},ensure_ascii=False))


if __name__=='__main__':verify()
