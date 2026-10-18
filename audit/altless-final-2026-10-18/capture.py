"""Published-only, authenticated, isolated acceptance audit. No publication/ref writes.

Run with the same secrets and read-only GH_TOKEN as deletion-audit.yml.
The previous directory must be an immutable gh-pages checkout.
"""
import json
import re
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


def embedded_json(document, name):
    match = re.search(r'window\.' + re.escape(name) + r'\s*=\s*', document)
    assert match, name
    return json.JSONDecoder().raw_decode(document[match.end():])[0]


def capture(previous, destination):
    previous, destination = Path(previous).resolve(), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    baseline = subprocess.check_output(['git','-C',str(previous),'rev-parse','HEAD'],text=True).strip()
    assert baseline == 'b265b70b8ba872751d26dd38201d91fbe023f90e', 'PUBLIC_BASELINE_MOVED_REVIEW_REQUIRED'
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
    assert len(old) == 897 and len(current) == 933
    assert all(oid in current and all(current[oid][k] == r[k] for k in ('gallery_name','src','capture')) for oid,r in old.items())
    assert all({k:v for k,v in r['article'].items() if k != 'article_path'} ==
               {k:v for k,v in current[oid]['article'].items() if k != 'article_path'} for oid,r in old.items())
    old_exif = embedded_json((previous/'favorite.html').read_text(), 'EXIF_CACHE')
    new_exif = embedded_json((destination/'site/favorite.html').read_text(), 'EXIF_CACHE')
    assert all(src in new_exif and value == new_exif[src] for src,value in old_exif.items())
    assert len(old_exif) == 897
    for key in ('mushroom_master','sources'):
        assert portal['reference_data'][key] == sync.previous['reference_data'][key]
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
    assert len(new_rows) == 36
    historical = json.loads((ROOT/'audit/altless-final-2026-10-18/summary.json').read_text())
    expected = Counter(historical['additions_by_name'])
    expected.subtract({'ブドウニガイグチ':2, 'マツタケ':2})
    assert Counter(r['gallery_name'] for r in new_rows) == +expected
    assert len(recent_ids) == 7 and len(recent) == 73
    assert sum(r['src'] in old_src for r in recent) == 27
    assert {r['src'] for r in new_rows} <= {r['src'] for r in recent}
    shared = sorted({src for sources in overlays.values() for src in sources})
    recent_shared = sorted(set(shared) & {r['src'] for r in recent})
    assert len(recent_shared) == 3
    assert len(shared) == 5
    unregistered = [r for r in recent if r['src'] not in {p['src'] for p in current.values()}]
    assert Counter(r['detected_label'] for r in unregistered if r['detected_label']) == {
        'オオジョウゴタケ？':3, 'フモトニガイグチ':1, 'アブラシメジモドキ':1, 'フジアザミ':1}
    assert sum(r['last_rejected_boundary_reason']=='family_or_group_heading' for r in unregistered) == 1
    assert not list((destination/'site').glob('*アンズアケ*'))
    assert not (destination/'site/フジアザミ.html').exists()
    from research_ui import build_research_cases
    before_cases, after_cases = build_research_cases(sync.previous), build_research_cases(portal)
    projection = lambda cases: sorted((c['case_id'], c['gallery_name'], sorted((p['observation_id'],p['src'],p['capture_date']) for p in c['photos'])) for c in cases)
    assert projection(before_cases) == projection(after_cases) and len(after_cases) == 66
    save(destination/'research-public.json', after_cases)
    save(destination/'new-registered-photos.json', new_rows)
    candidate_snapshot = json.loads((destination/'site/article-sync-snapshot.json').read_text())['payload']
    before_snapshot = json.loads((previous/'article-sync-snapshot.json').read_text())['payload']
    for key in ('retirement','deletions'):
        assert candidate_snapshot[key] == before_snapshot[key]
    receipts = {r['observation_id']:r for r in candidate_snapshot['automatic_additions']}
    assert all(receipts[r['observation_id']] == r for r in before_snapshot['automatic_additions'])
    new_receipts = set(receipts)-{r['observation_id'] for r in before_snapshot['automatic_additions']}
    assert new_receipts == {r['observation_id'] for r in new_rows}
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
        'already_registered':27, 'new_registered':len(new_rows), 'additions_by_name':dict(Counter(r['gallery_name'] for r in new_rows)),
        'preserved_capture_exif_article_metadata':897, 'research_case_photo_projection_unchanged':True,
        'prior_automatic_receipts_preserved':len(before_snapshot['automatic_additions']), 'new_automatic_receipts':len(new_receipts),
        'mixed_species_overlays':overlays,'mixed_species_source_photos':len(shared),
        'recent_mixed_species_source_photos':len(recent_shared),
        'unregistered_recent': [r for r in recent if r['src'] not in {p['src'] for p in current.values()}],
        'admin_recent_rows':len(rows),'publication':'NOT_ATTEMPTED','history_persisted':False}
    save(destination/'summary.json', summary)
    print('PASS: immutable baseline, 897 preserved IDs/names/URLs/EXIF/article metadata, 36 additions, 3 HTML-only photos, Best Shot 12, research 66, retired 7; no publication/history writes')


if __name__ == '__main__':
    capture(sys.argv[1], sys.argv[2])
