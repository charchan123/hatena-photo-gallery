"""Human review gate for new, already Phase-3C-validated gallery occurrences.

Never classifies an image, changes an old name/ID/URL, or authorizes deletion.
Only hashed, exact-input approvals are versioned. Local notes/photos stay local.
"""
from collections import Counter
from datetime import datetime
from pathlib import Path
import json

from article_sync import HASH, SAFE_NEW, SyncError, digest, observation_groups, payload_hash

APPROVAL_PATH = 'sync-reviews/approvals.json'
HEADER = {'version': 1, 'scope': 'phase3c-safe-new-photo-only', 'require_new_photo_review': True}
FIELDS = {'candidate_id', 'article_hash', 'url_hash', 'ordinal', 'base_snapshot_sha256',
          'inventory_sha256', 'fingerprint', 'name_hash', 'decision', 'decided_at',
          'comment_sha256', 'reviewer', 'change_type'}


def identity(article_hash, url_hash, ordinal):
    return 'sync-' + payload_hash([article_hash, url_hash, ordinal])


def occurrence_rows(portal):
    counts = Counter()
    result = {}
    observation_groups(portal)
    for row in portal['observations']:
        key = (digest(row['article']['article_id']), digest(row['src']))
        ordinal = counts[key]; counts[key] += 1
        result[(*key, ordinal)] = row
    return result


def photo_fingerprint(article, image, observation):
    # Ignore transient article_N and production order; include all classification
    # evidence and the entire article inventory (including updated timestamp hash).
    return payload_hash({'article': article, 'image': image,
                         'classification': observation.get('classification') if observation else None,
                         'name': observation.get('gallery_name') if observation else None})


def validate_approvals(value):
    if not isinstance(value, dict) or set(value) != {*HEADER, 'approvals'}:
        raise SyncError('REVIEW_MANIFEST_INVALID')
    if any(type(value[k]) is not type(v) or value[k] != v for k, v in HEADER.items()):
        raise SyncError('REVIEW_MANIFEST_INVALID')
    if not isinstance(value['approvals'], list) or len(value['approvals']) > 10000:
        raise SyncError('REVIEW_MANIFEST_INVALID')
    seen = set()
    for row in value['approvals']:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise SyncError('REVIEW_MANIFEST_INVALID')
        if any(not isinstance(row[k], str) or not HASH.fullmatch(row[k]) for k in
               ('article_hash','url_hash','base_snapshot_sha256','inventory_sha256','fingerprint','name_hash','comment_sha256')):
            raise SyncError('REVIEW_MANIFEST_INVALID')
        if type(row['ordinal']) is not int or not 0 <= row['ordinal'] <= 100000:
            raise SyncError('REVIEW_MANIFEST_INVALID')
        if (row['candidate_id'] != identity(row['article_hash'], row['url_hash'], row['ordinal'])
                or row['decision'] != 'adopt' or row['reviewer'] != 'explicit-local-human-review'
                or row['change_type'] != 'new_gallery_photo'):
            raise SyncError('REVIEW_MANIFEST_INVALID')
        try:
            timestamp = datetime.fromisoformat(row['decided_at'])
            if timestamp.tzinfo is None: raise ValueError()
        except (TypeError, ValueError):
            raise SyncError('REVIEW_MANIFEST_INVALID') from None
        key = (row['candidate_id'], row['base_snapshot_sha256'], row['inventory_sha256'])
        if key in seen: raise SyncError('REVIEW_MANIFEST_DUPLICATE')
        seen.add(key)
    return value


def load_approvals(root):
    path = Path(root) / APPROVAL_PATH
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise SyncError('REVIEW_MANIFEST_MISSING')
    try: return validate_approvals(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, json.JSONDecodeError): raise SyncError('REVIEW_MANIFEST_INVALID') from None


def gate_new_photos(portal, previous, articles, snapshot_sha256, manifest):
    """Additional gate AFTER retirement, Phase3C and normal ID/name validation.

    Existing rows need no re-approval. A successful publication makes new rows
    existing on the next run, so historical approvals never exempt future edits.
    """
    validate_approvals(manifest)
    old = occurrence_rows(previous); current = occurrence_rows(portal)
    inv_hash = payload_hash(articles)
    approvals = {(r['candidate_id'], r['base_snapshot_sha256'], r['inventory_sha256']): r
                 for r in manifest['approvals']}
    applied = []
    for key, observation in current.items():
        if key in old: continue
        ah, uh, ordinal = key
        classification = observation.get('classification', {})
        if (classification.get('status') not in SAFE_NEW
                or classification.get('subject_state_status') != 'accepted_subject'
                or classification.get('classification_confidence') != 'high'):
            raise SyncError('NEW_PHOTO_CLASSIFICATION_REQUIRES_REVIEW')
        cid = identity(*key)
        row = approvals.get((cid, snapshot_sha256, inv_hash))
        if not row: raise SyncError('NEW_PHOTO_HUMAN_APPROVAL_REQUIRED')
        images = articles.get(ah, {}).get('images', [])
        # Gallery and DOM duplicate ordinals are equivalent only when every
        # occurrence of this URL in the article is a gallery photograph.
        if sum(x['url_hash'] == uh for x in images) != sum(k[:2] == key[:2] for k in current):
            raise SyncError('REVIEW_DUPLICATE_OCCURRENCE_AMBIGUOUS')
        image = next((x for x in images if x['url_hash'] == uh and x['ordinal'] == ordinal), None)
        if (not image or row['fingerprint'] != photo_fingerprint(articles[ah], image, observation)
                or row['name_hash'] != digest(observation['gallery_name'])):
            raise SyncError('STALE_PHOTO_REVIEW')
        applied.append(cid)
    return {'approved_new_photos': len(applied), 'manifest_sha256': payload_hash(manifest)}
