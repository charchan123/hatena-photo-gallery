"""Published-only, authenticated, isolated acceptance audit. No publication/ref writes.

Run with the same secrets and read-only GH_TOKEN as deletion-audit.yml.
The previous directory must be an immutable gh-pages checkout.
"""
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from admin.sync import isolated_generator, live_capture, SyncReview
from article_sync import SyncRun
from multi_subject import build_multi_subject_photo_overlays


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def capture(previous, destination):
    previous, destination = Path(previous).resolve(), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    sync = SyncRun(previous, destination/'guarded-preview.json', safe_deletions=True, deletion_preview=True)
    with isolated_generator() as (main, temporary):
        main.build_gallery(sync_run=sync)
        portal = json.loads(Path(main.PORTAL_DATA_FILE).read_text())
        shadows = json.loads(Path(main.SHADOW_METADATA_FILE).read_text())
        metadata = main.load_article_metadata()
        entries = [{'alt': r['gallery_name'], 'src': r['src']} for r in portal['observations']]
        overlays = build_multi_subject_photo_overlays(shadows, main.load_subject_taxonomy(), entries, main.match_subject_taxonomy)
        shutil.copytree(main.OUTPUT_DIR, destination/'site')
        dates = ('2026年9月12日','2026年9月13日','2026年9月17日','2026年9月18日','2026年9月19日','2026年9月22日','2026年10月3日')
        recent_ids = {m['article_id'] for m in metadata.values() if any(d in m.get('title','').replace(' ', '').replace('　','') for d in dates)}
        recent = [{k:r.get(k) for k in ('article_id','article_title','src','detected_label','gallery_name','subject_state_status','last_rejected_boundary_text','last_rejected_boundary_reason','taxonomy_match_type')} for r in shadows if r.get('article_id') in recent_ids]
        save(destination/'recent-public-photos.json', recent)
    old = {r['observation_id']: r for r in sync.previous['observations']}
    current = {r['observation_id']: r for r in portal['observations']}
    assert len(old) == 893 and len(current) == 933
    assert all(oid in current and all(current[oid][k] == r[k] for k in ('gallery_name','src')) for oid,r in old.items())
    assert len({r['src'] for r in portal['observations']}) == len(portal['observations'])
    assert sync.status['best_shot_references_preserved'] == 12
    assert sync.status['research_cases_preserved'] == 66
    assert sync.status['retirement']['retired_total'] == 7
    assert sync.status['deletions']['history_persisted'] is False
    assert sync.status['deletions']['candidate_count'] == 0
    assert Counter(r['gallery_name'] for r in old.values())['アンズタケ'] == 4
    assert Counter(r['gallery_name'] for r in current.values())['アンズタケ'] == 4
    assert not any('アンズアケ' in r['gallery_name'] or r['gallery_name']=='フジアザミ' for r in current.values())
    old_src = {r['src'] for r in old.values()}
    new_rows = [r for oid,r in current.items() if oid not in old]
    assert len(recent_ids) == 7 and len(recent) == 73
    assert sum(r['src'] in old_src for r in recent) == 23
    assert {r['src'] for r in new_rows} <= {r['src'] for r in recent}
    shared = sorted({src for sources in overlays.values() for src in sources})
    assert len(shared) == 3
    from bs4 import BeautifulSoup
    for name, urls in overlays.items():
        page = BeautifulSoup((destination/'site'/main.safe_filename(name + '.html')).read_text(), 'html.parser')
        for src in urls:
            matches = [img for img in page.select('.gallery img') if img.get('src') == src]
            assert len(matches) == 1
            if src not in {r['src'] for r in current.values()}:
                assert not matches[0].parent.select('.thumb-fav')
    live = live_capture()
    publication = {'publication_sha': subprocess.check_output(['git','-C',str(previous),'rev-parse','HEAD'],text=True).strip()}
    for name in ('portal-data.json','article-sync-snapshot.json','article-sync-status.json','phase3c-production-status.json'):
        publication[name] = json.loads((previous/name).read_text())
    review = SyncReview(root=destination/'no-decisions')
    review.install(publication, live)
    dashboard = review.dashboard()
    rows = [review.view(r) for r in review.rows if r.get('thumbnail') in {p['src'] for p in recent}]
    save(destination/'admin-readonly.json', {'dashboard':dashboard,'rows':rows})
    summary = {'result':'PASS', 'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'baseline_commit':publication['publication_sha'], 'run_id':__import__('os').environ.get('GITHUB_RUN_ID'),
        'guarded_status':sync.status, 'recent_article_count':len(recent_ids),'recent_source_photos':len(recent),
        'already_registered':23, 'new_registered':len(new_rows), 'additions_by_name':dict(Counter(r['gallery_name'] for r in new_rows)),
        'mixed_species_overlays':overlays,'mixed_species_source_photos':len(shared),
        'unregistered_recent': [r for r in recent if r['src'] not in {p['src'] for p in current.values()}],
        'admin_recent_rows':len(rows),'publication':'NOT_ATTEMPTED','history_persisted':False}
    save(destination/'summary.json', summary)
    print('PASS: immutable baseline, 893 preserved IDs, 40 additions, 3 HTML-only photos, Best Shot 12, research 66, retired 7; no publication/history writes')


if __name__ == '__main__':
    capture(sys.argv[1], sys.argv[2])
