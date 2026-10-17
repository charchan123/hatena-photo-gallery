"""One-off, GET-only source review using the existing admin approval methods.

Run from repository root with production GET credentials. Never invokes create_pr,
GitHistory.save, non-preview generation, deployment, or remote Git writes.
Artifacts contain only the already-published observations and review evidence.
"""
import json
import os
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from admin.deletions import DeletionReview, atomic_json
from admin.sync import generate_in_worktree
from article_sync import digest, payload_hash, read_json
from deletion_approvals import load, validate, archive_context
from deletion_protection import github_get
from sync_deletions import confirmed, select, without_targets

MAIN = '4b95bd9e9e44f225027858c5dd4fd4b7cd865f59'
PAGES = '757cbfc868452d3bb892849fce0e2122cd8c566e'
COMMENT = 'https://github.com/charchan123/hatena-photo-gallery/pull/116#issuecomment-6228088094'
COMMENT_HASH = 'dc580b456284e621d96d15e2026eec3f968e1f2b4a21fe130237f0a7720d09ca'
TARGETS = {
    'obs-b65bc66594a331b3fb0e79f41dbfe9d2b8c5e94bdd826c49b1a6b26472f12e51': ('archive_research', 'research-940496f1ccdb136f', 1, 0),
    'obs-87fa70cf88bf584c315b452899c54a1426d784d2fb6aa9beede5b38d2a98a7c6': ('approve_research_photo', 'research-f9cb62e956fa8604', 6, 5),
}
REASON = 'ブログ執筆者が原記事から除いた欠落写真を公開図鑑へ無断復活させず、研究記録の保全を優先するため。個別方針の承認記録：' + COMMENT


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def refs():
    return {line.split()[1]: line.split()[0] for line in git('ls-remote', '--heads', 'origin', 'main', 'gh-pages', 'sync-deletion-audit').splitlines()}


def main():
    bundle = ROOT / 'cache/research-approval-bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    before = refs()
    assert before['refs/heads/main'] == MAIN and before['refs/heads/gh-pages'] == PAGES
    assert "SAFE_PHOTO_DELETION_PUBLISH_ENABLED: 'false'" in (ROOT / '.github/workflows/generate.yml').read_text()
    comment = github_get('issues/comments/6228088094')
    assert comment['user']['login'] == 'charchan123' and comment['author_association'] == 'OWNER'
    assert comment['html_url'] == COMMENT and digest(comment['body']) == COMMENT_HASH
    review = DeletionReview(ROOT, state_path=ROOT / 'cache/research-individual-review.json')
    dashboard = review.refresh(live=True)
    snapshot = review.publication['article-sync-snapshot.json']
    assert review.publication['publication_sha'] == PAGES
    assert snapshot['sha256'] == '7212389cdc412bf3577c78c3e0be5c91926ecc398930427b775f2459071adcb0'
    fetches = [r['event'] for r in review.history if r['event']['kind'] == 'fetch']
    pair = [next(e for e in fetches if e['independent_id'] == 'actions:' + str(rid)) for rid in (38922030976, 38990433068)]
    seconds = (datetime.fromisoformat(pair[1]['at']) - datetime.fromisoformat(pair[0]['at'])).total_seconds()
    assert 6 * 3600 <= seconds <= 72 * 3600
    assert pair[0]['healthy'] and pair[1]['healthy'] and pair[0]['candidates'] == pair[1]['candidates']
    assert pair[0]['baseline'] == pair[1]['baseline'] == snapshot['sha256']
    assert pair[0]['protection'] == pair[1]['protection'] == review.protection['sha256']
    assert len(review.rows) == 16
    assert {r['observation_id'] for r in review.rows if r['protection']} == set(TARGETS)
    for row in review.rows:
        assert not row['identity_issues'] and not row['mass_review']
        assert pair[1]['candidates'][row['candidate_id']] == row['fingerprint']
        assert confirmed(review.history, row, snapshot['sha256'], review.protection['sha256'], datetime.now(timezone.utc).isoformat())
    existing = load(ROOT)
    generated = not existing
    if generated:
        assert Counter(r['status'] for r in review.rows) == {'automatic_eligible': 14, 'approval_pending': 2}
        for oid, (action, case_id, total, remaining) in TARGETS.items():
            row = next(r for r in review.rows if r['observation_id'] == oid)
            assert row['related_research_cases'] == [{'case_id': case_id, 'photo_count': total, 'remaining_photo_count': remaining}]
            result = review.decide({'candidate_id': row['candidate_id'], 'fingerprint': row['fingerprint'],
                'action': action, 'reason': REASON, 'confirm_id': oid})
            assert result['saved'] and result['published'] is False
        preview = review.preview_changes()
        assert preview['ready'] and preview['published'] is False and not review.preview['negative_only']
        files = preview['files']
        manifests = [v for path, v in files.items() if path.startswith('sync-migrations/')]
    else:
        # On reruns, validate the immutable official output; never mint new IDs.
        manifests = existing
        files = {'sync-migrations/photo-deletions/' + m['approval_id'] + '.json': m for m in manifests}
        preview = {'ready': True, 'published': False, 'fingerprint': payload_hash(files), 'files': files,
            'diff': [{'path': p, 'before': None, 'after': v} for p, v in files.items()]}
    assert len(manifests) == 2
    by_candidate = {r['candidate_id']: r for r in review.rows}
    for manifest in manifests:
        validate(manifest)
        row = by_candidate[manifest['candidate_id']]
        action, case_id, total, remaining = TARGETS[row['observation_id']]
        assert manifest['action'] == action and manifest['case_ids'] == [case_id]
        assert manifest['reason_sha256'] == digest(REASON)
        assert manifest['supersedes'] is None
        capsule = manifest['archives'][0]
        assert len(capsule['observations']) == total
        old = {o['observation_id']: o for o in review.publication['portal-data.json']['observations']}
        assert all(old[o['observation_id']] == o for o in capsule['observations'])
        assert capsule['identifications'] == [i for i in manifest['registry_before']['identifications'] if i['case_id'] == case_id]
    selected = select(deepcopy(review.rows), snapshot, review.history, review.protection, datetime.now(timezone.utc).isoformat(), manifests)
    assert Counter(r['mode'] for r in selected) == {'automatic': 14, 'manual': 2}
    assert all(r['observation_id'] in TARGETS for r in selected if r['mode'] == 'manual')
    # Validate full original capsules and exact active registry, with no invented history.
    registry = files.get('data/research-identifications.json', read_json(ROOT / 'data/research-identifications.json'))
    archive_context(manifests, review.publication['portal-data.json'], registry, read_json(ROOT / 'data/mushroom-master.json'), selected)
    from article_sync import reconcile_ids
    from research_ui import build_research_cases
    projection = reconcile_ids(review.live['portal'], without_targets(review.publication['portal-data.json'], selected))
    cases = {c['case_id']: c for c in build_research_cases(projection)}
    assert 'research-940496f1ccdb136f' not in cases
    assert len(cases['research-f9cb62e956fa8604']['photos']) == 5
    with tempfile.TemporaryDirectory(prefix='kinoko-approved-preview-') as tmp:
        work, previous = Path(tmp) / 'work', Path(tmp) / 'previous'
        added = []
        try:
            for dest, ref in ((work, 'HEAD'), (previous, PAGES)):
                subprocess.run(['git', 'worktree', 'add', '--detach', str(dest), ref], cwd=ROOT, check=True, capture_output=True)
                added.append(dest)
            for path, value in files.items():
                assert path == 'data/research-identifications.json' or path == 'sync-migrations/photo-deletions/' + value['approval_id'] + '.json'
                atomic_json(work / path, value)
            result = generate_in_worktree(work, previous, Path(tmp) / 'never-published', bundle / 'guarded-preview.json', os.environ.copy(), deletion_preview=True)
            report = read_json(bundle / 'guarded-preview.json')
            assert result.returncode == 0, report.get('error_code', 'PREVIEW_FAILED')
            assert report['result'] == 'PREVIEW' and report['deletions']['history_persisted'] is False
            assert report['deletions']['automatic_deletion_eligible'] == 14 and report['deletions']['manual_deletion_eligible'] == 2
            assert report['deletions']['pending'] == 0 and report['gallery_photo_count'] == 893 and report['preserved_photo_ids'] == 890
            assert not (Path(tmp) / 'never-published').exists()
            # No generated pages, raw source bodies, or cache can enter the PR.
            expected = sorted(p for p in files if not (ROOT / p).exists())
            actual = sorted(git('ls-files', '--others', '--exclude-standard'))
            changed = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=work, text=True)
            assert sorted(line[3:] for line in changed.splitlines()) == expected
        finally:
            for dest in reversed(added):
                subprocess.run(['git', 'worktree', 'remove', '--force', str(dest)], cwd=ROOT, check=True, capture_output=True)
    review.assert_fresh()
    assert refs() == before, 'Production refs changed during review; repeat from fresh evidence'
    for path, value in files.items():
        atomic_json(bundle / 'files' / path, value)
    atomic_json(bundle / 'decision-preview.json', preview)
    atomic_json(bundle / 'evidence.json', {
        'version': 1, 'at': datetime.now(timezone.utc).isoformat(), 'run_id': os.environ.get('GITHUB_RUN_ID'),
        'source_commit': git('rev-parse', 'HEAD'), 'authorization': {'url': COMMENT, 'body_sha256': COMMENT_HASH},
        'production_refs_before': before, 'production_refs_after': refs(), 'history_event_count': len(review.history),
        'independent_fetches': [{'run_id': e['run_id'], 'at': e['at'], 'healthy': e['healthy']} for e in pair],
        'interval_seconds': seconds, 'fetch_audit': review.live['fetch_audit'], 'baseline': snapshot['sha256'],
        'protection': review.protection['sha256'], 'preview_fingerprint': preview['fingerprint'],
        'formal_admin_methods': ['refresh(live=True)', 'decide(each full confirm_id)', 'preview_changes()', 'assert_fresh()'] if generated else ['refresh(live=True)', 'validate(existing immutable manifests)', 'assert_fresh()'],
        'individual_decisions': [{'observation_id': by_candidate[m['candidate_id']]['observation_id'], 'action': m['action'], 'approval_id': m['approval_id']} for m in manifests],
        'manifest_count': 2, 'automatic_manifest_count': 0, 'selected_modes': dict(Counter(r['mode'] for r in selected)),
        'research_after': {'kawarihatsu': 'archived_with_full_original_capsule', 'lanmaoa_remaining_photos': 5},
        'publication': 'NOT_ATTEMPTED', 'production_deletions_applied': 0, 'history_writes': 0,
    })
    print('PASS: 2 official individual manifests; isolated guarded PREVIEW; automatic 14 / manual 2 / pending 0; production writes 0')


if __name__ == '__main__':
    main()
