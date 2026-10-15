"""Read-only live deletion audit. Never modifies source, public output or refs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from article_sync import (SyncError, read_json, write_json, validate_snapshot,
                          compare_inventory, digest)
from sync_deletions import plan, occurrences, photo_keys
from deletion_protection import collect, open_selections


def details(rows, portal):
    photos = photo_keys(portal)
    result = []
    for row in rows:
        photo = photos.get((row['article_hash'], row['url_hash'], row['ordinal']), {})
        article = photo.get('article', {})
        result.append({**row, 'gallery_name': photo.get('gallery_name'), 'src': photo.get('src'),
            'article_id': article.get('article_id'), 'article_title': article.get('title'),
            'article_url': article.get('url')})
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
            'gallery_eligible': key in new_keys, 'gallery_name': row.get('gallery_name'),
            'src': row.get('src') or p.get('thumbnail'), 'article': row.get('article') or {
                'title': p.get('article_title'), 'url': p.get('article_url')},
            'classification': row.get('classification')})
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
        'fetch_audit': live['fetch_audit'], 'removed': details(rows, portal), 'added_source': added,
        'new_articles': sorted(live['articles'].keys() - snapshot['payload']['articles'].keys()),
        'protection': protection, 'publication': 'NOT_ATTEMPTED'}


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
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, SyncError) else 'LIVE_DELETION_AUDIT_UNAVAILABLE'
        write_json(args.report, {'version': 1, 'read_only': True, 'result': 'BLOCKED', 'error_code': code,
            'publication': 'NOT_ATTEMPTED'})
        print('Read-only deletion audit: BLOCKED')
        return 1


if __name__ == '__main__': raise SystemExit(main())
