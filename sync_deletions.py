"""Exact-target deletion planning. No remote writes; original Phase 1 gates remain.

A plan is evidence, never permission to publish. The daily adapter must durably
commit its fetch event before using it, and still run the original validators.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re

from article_sync import (SyncError, digest, payload_hash, observation_groups,
                          validate_snapshot)

ROOT_HASH = digest('hatena-photo-deletion-history-v1')
MIN_INTERVAL = timedelta(hours=6)
MAX_INTERVAL = timedelta(hours=72)
MAX_AUTO_IMAGES = 20
MAX_AUTO_FRACTION = .03
MAX_AUTO_ARTICLES = 2


def instant(value):
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None: raise ValueError()
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise SyncError('DELETION_TIMESTAMP_INVALID') from None


def occurrences(articles):
    return {(aid, im['url_hash'], im['ordinal']): im
            for aid, a in articles.items() for im in a['images']}


def photo_keys(portal):
    result = {}
    for (aid, src), rows in observation_groups(portal).items():
        for n, row in enumerate(rows): result[(digest(aid), digest(src), n)] = row
    return result


def healthy_fetch(audit, articles, excluded):
    """Require the strict API harvester's independently checked accounting."""
    try:
        assert audit['pagination_complete'] is True
        assert type(audit['pages_completed']) is int and audit['pages_completed'] > 0
        assert audit['published_articles'] == audit['html_articles'] == len(articles) > 0
        assert audit['entries_received'] == len(articles) + audit['drafts_excluded']
        assert audit['drafts_excluded'] == len(excluded)
        assert set(articles).isdisjoint(excluded)
        assert audit['html_image_representation_difference_articles'] == 0
        assert sum(audit['content_type_counts'].values()) == len(articles)
        assert sum(audit['html_source_counts'].values()) == len(articles)
    except (AssertionError, KeyError, TypeError):
        raise SyncError('DELETION_FETCH_NOT_COMPLETE') from None


def validate_history(history, anchor=None):
    try:
        assert isinstance(history, list)
        head = ROOT_HASH; seen = set(); last = None
        for index, item in enumerate(history):
            assert set(item) == {'version', 'seq', 'previous', 'event', 'sha256'}
            assert item['version'] == 1 and type(item['seq']) is int and item['seq'] == index + 1
            assert item['previous'] == head
            assert item['sha256'] == payload_hash({k: v for k, v in item.items() if k != 'sha256'})
            event = item['event']; at = instant(event['at'])
            assert last is None or at >= last
            assert event['run_id'] not in seen
            assert re.fullmatch(r'[a-zA-Z0-9:._-]{1,100}', event['run_id'])
            assert event['kind'] in {'fetch','result'} and type(event['healthy']) is bool
            assert re.fullmatch(r'[0-9a-f]{64}', event['baseline'])
            assert re.fullmatch(r'[0-9a-f]{40}', event['baseline_commit'])
            assert isinstance(event['candidates'], dict)
            seen.add(event['run_id']); last = at; head = item['sha256']
        assert anchor is None or anchor == ROOT_HASH or anchor in {x['sha256'] for x in history}
    except (AssertionError, KeyError, TypeError, ValueError):
        raise SyncError('DELETION_HISTORY_CORRUPT') from None
    return head


def append_event(history, event):
    head = validate_history(history)
    # A retry of the same attempt is not another observation. Identical writes
    # are idempotent; a changed fetch with the same run must invalidate it.
    same = [r for r in history if r['event']['run_id'] == event['run_id']]
    if same:
        if same[0]['event'] != event: raise SyncError('DELETION_RUN_ALREADY_RECORDED')
        return deepcopy(history)
    row = {'version': 1, 'seq': len(history) + 1, 'previous': head, 'event': event}
    row['sha256'] = payload_hash(row)
    result = history + [row]; validate_history(result)
    return result


def confirmed(history, candidate, baseline, protection, at):
    """Consecutive healthy *independent* fetches, 6–72h apart, same context.

    An intervening outage, reappearance, baseline/ref change or changed article
    invalidates the streak. Unrelated new articles do not reset the context.
    """
    now = instant(at); matches = []
    for item in reversed(history):
        ev = item['event']
        if ev['kind'] != 'fetch': continue
        elapsed = now - instant(ev['at'])
        if elapsed < timedelta(0): raise SyncError('DELETION_HISTORY_IN_FUTURE')
        if elapsed > MAX_INTERVAL: break
        if (not ev['healthy'] or ev['baseline'] != baseline
                or ev['protection'] != protection
                or ev['candidates'].get(candidate['candidate_id']) != candidate['fingerprint']): break
        matches.append(ev)
    return any(a.get('independent_id',a['run_id']) != b.get('independent_id',b['run_id'])
        and instant(a['at'])-instant(b['at']) >= MIN_INTERVAL for a in matches for b in matches)


def plan(snapshot, portal, articles, audit, excluded, protection):
    """Return every removed DOM occurrence, with gallery IDs where applicable.

    Ambiguous identity is NEVER rescued by a human deletion approval. URL
    replacements and duplicate changes need a different explicit migration.
    """
    before = validate_snapshot(snapshot, portal)['articles']
    healthy_fetch(audit, articles, excluded)
    if protection.get('complete') is not True: raise SyncError('DELETION_REFERENCES_UNAVAILABLE')
    if protection.get('sha256') != payload_hash({k: v for k, v in protection.items() if k != 'sha256'}):
        raise SyncError('DELETION_PROTECTION_CORRUPT')
    old, new = occurrences(before), occurrences(articles); photos = photo_keys(portal)
    deleted = old.keys() - new.keys(); added = new.keys() - old.keys()
    removed_articles = before.keys() - articles.keys()
    old_locations = {}
    for row in portal['observations']:
        if row['article'].get('url'):
            old_locations[digest(row['article']['article_id'])] = digest(row['article']['url'])
    old_locations.update({aid: a['article_url_hash'] for aid,a in before.items() if a.get('article_url_hash')})
    if any(aid not in old_locations or not before[aid]['images'] for aid in removed_articles):
        raise SyncError('DELETION_ARTICLE_IDENTITY_UNAVAILABLE')
    current_locations = {aid:a.get('article_url_hash') for aid,a in articles.items()}
    if any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in current_locations.values()):
        raise SyncError('DELETION_ARTICLE_LOCATIONS_UNAVAILABLE')
    if len(set(current_locations.values())) != len(current_locations):
        raise SyncError('DELETION_ARTICLE_URL_DUPLICATE')
    # A single image can exceed 3% on a tiny gallery; allow one. Large real
    # publications are capped by BOTH 20 images and 3% of all source occurrences.
    mass = (len(deleted) > min(MAX_AUTO_IMAGES, max(1, int(len(old) * MAX_AUTO_FRACTION)))
            or len(removed_articles) > min(MAX_AUTO_ARTICLES, max(1, int(len(before) * .05))))
    old_url_counts = Counter(k[1] for k in old)
    old_counts = Counter(k[:2] for k in old); new_counts = Counter(k[:2] for k in new)
    rows = []
    for key in sorted(deleted):
        aid, url, ordinal = key; source = photos.get(key); issues = []
        removed_here = [k for k in deleted if k[0] == aid]
        added_here = [k for k in added if k[0] == aid]
        if added_here: issues.append('POSSIBLE_URL_REPLACEMENT')
        if aid not in old_locations: issues.append('ARTICLE_URL_IDENTITY_UNAVAILABLE')
        elif (aid in current_locations and current_locations[aid] != old_locations[aid]) or any(
                other != aid and loc == old_locations[aid] for other,loc in current_locations.items()):
            issues.append('ARTICLE_URL_MOVED_OR_CHANGED')
        # Same URL appearing in another article may be an article move, even if
        # that new article has a different Atom ID. Never match by title/name.
        if old_url_counts[url] != 1 or any(k[1] == url for k in new): issues.append('URL_MOVED_OR_SHARED')
        if old_counts[key[:2]] != 1 or new_counts[key[:2]]: issues.append('DUPLICATE_OCCURRENCE_AMBIGUOUS')
        if aid in excluded: issues.append('DRAFT_TRANSITION_REQUIRES_MIGRATION')
        if aid in articles:
            # Remaining occurrences must be the EXACT ordered subsequence, with
            # identical labels and classification, not just the same URL set.
            expected = [im for im in before[aid]['images'] if (aid, im['url_hash'], im['ordinal']) not in deleted]
            if expected != articles[aid]['images']: issues.append('SURVIVOR_SEQUENCE_OR_LABEL_CHANGED')
        if len(articles) < len(before) * .9: issues.append('ABNORMAL_ARTICLE_DECREASE')
        oid = source['observation_id'] if source else None
        cid = payload_hash({'baseline': snapshot['sha256'], 'key': list(key)})
        refs = list(protection['references'].get(oid, [])) if oid else []
        refs += protection.get('source_references',{}).get(cid,[])
        for ref in protection.get('image_references',{}).get(url,[]):
            if ref not in refs:refs.append(ref)
        core = {'baseline': snapshot['sha256'], 'article_hash': aid, 'url_hash': url, 'ordinal': ordinal,
                'observation_id': oid, 'before_image': old[key],
                'after_article': articles.get(aid), 'references': refs}
        cid = payload_hash({'baseline': snapshot['sha256'], 'key': list(key)})
        rows.append({'candidate_id': cid, 'fingerprint': payload_hash(core),
            'article_hash': aid, 'url_hash': url, 'ordinal': ordinal, 'observation_id': oid,
            'kind': 'article_deleted' if aid not in articles else 'photo_deleted',
            'identity_issues': sorted(set(issues)), 'protection': refs,
            'mass_review': mass, 'status': 'identity_uncertain' if issues else 'approval_pending' if refs or mass else 'reconfirmation_pending'})
    return rows


def event_for(rows, snapshot, baseline_commit, protection, articles, run_id, at, *, healthy=True, error=None):
    return {'kind': 'fetch', 'at': at, 'run_id': run_id, 'independent_id':run_id.split(':attempt:')[0], 'baseline': snapshot['sha256'],
        'baseline_commit': baseline_commit, 'protection': protection.get('sha256'),
        'source_sha256': payload_hash(articles), 'healthy': healthy, 'error_code': error,
        'candidates': {r['candidate_id']: r['fingerprint'] for r in rows} if healthy else {},
        'findings': deepcopy(rows) if healthy else []}


def select(rows, snapshot, history, protection, at, decisions=()):
    """Select only exact, reconfirmed targets; human choices cannot bypass proof."""
    validate_history(history, snapshot['payload'].get('deletion_history_head'))
    allowed = []; decisions = {d['candidate_id']: d for d in decisions}
    for row in rows:
        row['status'] = 'identity_uncertain' if row['identity_issues'] else 'reconfirmation_pending'
        if row['identity_issues']: continue
        d = decisions.get(row['candidate_id'])
        if d and (d.get('fingerprint') != row['fingerprint'] or d.get('baseline') != snapshot['sha256']
                  or d.get('protection') != protection['sha256']):
            raise SyncError('DELETION_APPROVAL_STALE')
        if d and d.get('action') in {'hold', 'propose_replacement'}:
            row['status'] = 'held'; continue
        if not confirmed(history, row, snapshot['sha256'], protection['sha256'], at): continue
        if row['protection'] or row['mass_review']:
            row['status'] = 'approval_pending'
            # Ordinary approval cannot sever any important reference. Only a
            # separately validated archive transaction can clear research refs.
            if not d or d.get('action') not in {'approve', 'archive_research', 'retire_research', 'approve_research_photo'}: continue
            unresolved = [r for r in row['protection'] if not (d['action'] in {'archive_research', 'retire_research', 'approve_research_photo'} and (
                (r['kind'] == 'research' and r['id'] in d.get('case_ids', [])) or
                (r['kind'] == 'identification' and r['id'] in {i['identification_id'] for a in d.get('archives', []) for i in a['identifications']})))]
            if unresolved: continue
            mode = 'manual'
        else:
            mode = 'manual' if d and d.get('action') == 'approve' else 'automatic'
        row['status'] = mode + '_eligible'; allowed.append({**row, 'mode': mode})
    return allowed


def without_targets(portal, targets):
    result = deepcopy(portal); ids = {r['observation_id'] for r in targets if r['observation_id']}
    result['observations'] = [r for r in result['observations'] if r['observation_id'] not in ids]
    result['summary']['observation_count'] = len(result['observations'])
    observation_groups(result)
    return result
