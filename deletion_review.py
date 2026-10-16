"""Read-only live deletion audit. Never modifies source, public output or refs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from article_sync import (SyncError, read_json, write_json, validate_snapshot,
                          compare_inventory, digest)
from sync_deletions import plan, occurrences, photo_keys, without_targets
from deletion_protection import collect, open_selections


def details(rows, portal):
    photos = photo_keys(portal)
    from research_ui import build_research_cases
    cases={c['case_id']:c for c in build_research_cases(portal)}
    missing={r['observation_id'] for r in rows if r['observation_id']}
    result = []
    for row in rows:
        photo = photos.get((row['article_hash'], row['url_hash'], row['ordinal']), {})
        article = photo.get('article', {})
        if not article:
            article=next((p['article'] for p in portal['observations'] if digest(p['article']['article_id'])==row['article_hash']),{})
        result.append({**row, 'gallery_name': photo.get('gallery_name'), 'src': photo.get('src'),
            'article_id': article.get('article_id'), 'article_title': article.get('title'),
            'article_url': article.get('url'), 'related_research_cases':[{'case_id':ref['id'],
                'photo_count':len(cases[ref['id']]['photos']),
                'remaining_photo_count':sum(p['observation_id'] not in missing for p in cases[ref['id']]['photos'])}
                for ref in row['protection'] if ref['kind']=='research' and ref['id'] in cases]})
    return result


def audit(previous, baseline_commit, live, root, pending):
    portal = read_json(Path(previous) / 'portal-data.json')
    snapshot = read_json(Path(previous) / 'article-sync-snapshot.json')
    validate_snapshot(snapshot, portal)
    phase = read_json(Path(previous) / 'phase3c-production-status.json')
    if phase.get('cutover_active') is not True or phase.get('validation', {}).get('valid') is not True or phase.get('production_image_count') != len(portal['observations']):
        raise SyncError('PREVIOUS_PUBLICATION_NOT_HEALTHY')
    protection = collect(portal, snapshot, root, pending)
    rows = plan(snapshot, portal, live['articles'], live['fetch_audit'], set(live['excluded_draft_hashes']), protection)
    old_keys = photo_keys(portal); new_keys = photo_keys(live['portal'])
    added_source = occurrences(live['articles']).keys() - occurrences(snapshot['payload']['articles']).keys()
    removed_source = occurrences(snapshot['payload']['articles']).keys() - occurrences(live['articles']).keys()
    added = []
    for key in sorted(added_source):
        p = live.get('photos', {}).get(key, {}); row = new_keys.get(key, {})
        added.append({'article_hash': key[0], 'url_hash': key[1], 'ordinal': key[2],
            'gallery_eligible': key in new_keys, 'gallery_name': row.get('gallery_name'), 'detected_name': p.get('detected_name'),
            'src': row.get('src') or p.get('thumbnail'), 'article': {k:v for k,v in row.get('article',{}).items() if k in {'article_id','title','url','published','updated'}} or {
                'title': p.get('article_title'), 'url': p.get('article_url')},
            'classification': row.get('classification')})
    # Pure identity simulation, NEVER a publication/deletion permission. The
    # real adapter still rejects every unapproved protected target above/below.
    from article_sync import reconcile_ids
    from best_shot_ui import validate_best_shot_config
    comparison=without_targets(portal,rows) if rows else portal
    simulated=reconcile_ids(live['portal'],comparison)
    validate_best_shot_config(read_json(Path(root)/'data/best-shots.json'),simulated)
    for pr in pending:validate_best_shot_config(pr['config'],simulated)
    preserved={r['observation_id'] for r in comparison['observations']}
    identity_simulation={'purpose':'READ_ONLY_IDENTITY_CHECK_NOT_DELETION_APPROVAL',
        'remaining_existing_ids':len(preserved),'new_gallery_ids':[r['observation_id'] for r in simulated['observations'] if r['observation_id'] not in preserved],
        'main_best_shots_valid':True,'pending_best_shots_valid':True,'publication':'NOT_ATTEMPTED'}
    return {'version': 1, 'read_only': True, 'at': datetime.now(timezone.utc).isoformat(),
        'baseline_commit': baseline_commit, 'snapshot_sha256': snapshot['sha256'],
        'counts': {**compare_inventory(snapshot['payload']['articles'], live['articles']),
            'previous_gallery': len(old_keys), 'candidate_gallery': len(new_keys),
            'missing_gallery_occurrences': len(old_keys.keys() - new_keys.keys()),
            'missing_gallery_in_removed_source': len(set(old_keys) & removed_source),
            'new_source_gallery_occurrences': len(set(new_keys) & added_source),
            'new_source_non_gallery_occurrences': len(added_source - set(new_keys)),
            'source_image_count': len(occurrences(live['articles'])),
            'protected_deletion_candidates': sum(bool(r['protection']) for r in rows)},
        'identity_simulation':identity_simulation, 'fetch_audit': live['fetch_audit'], 'removed': details(rows, portal), 'added_source': added,
        'new_articles': sorted(live['articles'].keys() - snapshot['payload']['articles'].keys()),
        'protection': protection, 'pending_selections_checked': [{'number':p['number'],'head':p['head'],'entry_count':len(p['config']['entries']),'file_absent_verified':p.get('file_absent_verified',False)} for p in pending], 'publication': 'NOT_ATTEMPTED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', required=True)
    parser.add_argument('--baseline-commit', required=True)
    parser.add_argument('--report', default='cache/deletion-live-audit.json')
    args = parser.parse_args()
    try:
        from admin.sync import live_capture
        report = audit(args.previous, args.baseline_commit, live_capture(), Path(__file__).parent, open_selections())
        write_json(args.report, report)
        print('Read-only deletion audit: COMPLETE (no approval/publication)')
        print('Audit evidence: '+json.dumps({'counts':report['counts'], 'removed':[{'observation_id':r['observation_id'],'article_hash':r['article_hash'],'url_hash':r['url_hash'],'kind':r['kind'],'protection':r['protection']} for r in report['removed']]},ensure_ascii=False))
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, SyncError) else 'LIVE_DELETION_AUDIT_UNAVAILABLE'
        write_json(args.report, {'version': 1, 'read_only': True, 'result': 'BLOCKED', 'error_code': code,
            'publication': 'NOT_ATTEMPTED'})
        print('Read-only deletion audit: BLOCKED')
        return 1


if __name__ == '__main__': raise SystemExit(main())
