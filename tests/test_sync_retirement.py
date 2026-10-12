"""Isolated approval-boundary fixtures; never edit the pinned manifest/baseline."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import article_sync as sync
import sync_retirement as retirement


@pytest.fixture
def approved(tmp_path, monkeypatch):
    m = deepcopy(retirement.load_manifest())
    rows = [{'observation_id': f'old-{i}', 'src': f'https://images.example/{i}.jpg',
             'gallery_name': 'シイタケ', 'article': {'article_id': f'article-{i // 5}', 'url': 'https://public.example/article'},
             'classification': {'status': 'confirmed_named_mushroom', 'subject_state_status': 'accepted_subject', 'classification_confidence': 'high'},
             'capture': {'date': '2025-05-01'}} for i in range(906)]
    for i, target in enumerate(m['observations']):
        src = f'https://images.example/retired-{i}.jpg'
        target['image_url_sha256'] = sync.digest(src)
        rows.append({'observation_id': target['observation_id'], 'src': src,
                     'gallery_name': target['canonical_registered_name'],
                     'article': {'article_id': 'retired-article', 'url': 'https://public.example/retired'},
                     'classification': {'status': 'confirmed_named_mushroom'}, 'capture': {'date': '2025-05-01'}})
    previous = {'version': 1, 'observations': rows, 'summary': {'observation_count': 913}}
    m['target_article_sha256'] = sync.digest('retired-article')
    m['old_article_url_sha256'] = sync.digest('https://public.example/retired')
    m['baseline_portal_sha256'] = sync.payload_hash(previous)
    monkeypatch.setattr(retirement, 'load_manifest', lambda: deepcopy(m))
    monkeypatch.setattr(retirement, 'baseline_commit', lambda p: m['baseline_commit'])
    data = tmp_path / 'data'
    sync.write_json(data / 'best-shots.json', {'version': 1, 'entries': []})
    sync.write_json(data / 'research-identifications.json', {'version': 1, 'identifications': []})
    sync.write_json(data / 'mushroom-master.json', {'version': 1, 'entries': []})
    current = deepcopy(previous)
    current['observations'] = current['observations'][:906]
    current['summary']['observation_count'] = 906
    for r in current['observations']: r['observation_id'] = 'candidate-' + r['observation_id']
    return m, previous, current, data


def prepared(approved):
    m, old, current, data = approved
    r = retirement.Retirement(old, None, data.parent)
    effective = r.prepare(current, {sync.digest('article-0'): {}}, {m['target_article_sha256']}, data)
    return r, sync.reconcile_ids(current, effective)


def test_only_seven_retired_and_every_remaining_id_and_name_preserved(approved):
    _, previous, _, _ = approved
    original = deepcopy(previous)
    r, resolved = prepared(approved)
    assert previous == original
    assert r.applied_count == 7
    assert len(resolved['observations']) == 906
    assert [(p['observation_id'], p['src'], p['gallery_name'], p['article']['article_id']) for p in resolved['observations']] == [
        (p['observation_id'], p['src'], p['gallery_name'], p['article']['article_id']) for p in previous['observations'][:906]]
    assert r.status()['retired_total'] == 7


@pytest.mark.parametrize('damage', ['other_removed', 'target_present', 'draft_missing', 'article_public'])
def test_retirement_cannot_cover_another_deletion_or_changed_article_state(approved, damage):
    m, old, current, data = approved
    articles, drafts = {sync.digest('article-0'): {}}, {m['target_article_sha256']}
    if damage == 'other_removed': current['observations'].pop()
    if damage == 'target_present': current['observations'].append(deepcopy(old['observations'][-1]))
    if damage == 'draft_missing': drafts.clear()
    if damage == 'article_public': articles[m['target_article_sha256']] = {}
    current['summary']['observation_count'] = len(current['observations'])
    with pytest.raises(sync.SyncError): retirement.Retirement(old, None, data.parent).prepare(current, articles, drafts, data)


@pytest.mark.parametrize('damage', ['baseline_sha', 'baseline_payload', 'missing_target', 'duplicate_id', 'article', 'name', 'url', 'source'])
def test_original_913_baseline_and_exact_target_fields_are_bound(approved, monkeypatch, damage):
    m, old, _, data = approved
    if damage == 'baseline_sha': monkeypatch.setattr(retirement, 'baseline_commit', lambda p: 'other-commit')
    elif damage == 'baseline_payload': old['summary']['extra'] = True
    elif damage == 'missing_target': old['observations'].pop(); old['summary']['observation_count'] -= 1
    elif damage == 'duplicate_id': old['observations'][-1]['observation_id'] = old['observations'][-2]['observation_id']
    elif damage == 'article': old['observations'][-1]['article']['article_id'] = 'other'
    elif damage == 'name': old['observations'][-1]['gallery_name'] = 'other'
    elif damage == 'url': old['observations'][-1]['article']['url'] = 'other'
    elif damage == 'source': old['observations'][-1]['src'] = 'other'
    with pytest.raises(sync.SyncError):
        sync.observation_groups(old)
        retirement.Retirement(old, None, data.parent)


@pytest.mark.parametrize('damage', ['missing', 'extra_id', 'baseline', 'reason'])
def test_actual_manifest_bytes_cannot_be_missing_or_changed(tmp_path, monkeypatch, damage):
    path = tmp_path / 'manifest.json'
    raw = retirement.MANIFEST_PATH.read_bytes()
    if damage != 'missing':
        m = json.loads(raw)
        if damage == 'extra_id': m['observations'].append(m['observations'][0])
        elif damage == 'baseline': m['baseline_commit'] = 'different'
        elif damage == 'reason': m['approval_scope'] = 'all deletions approved'
        path.write_text(json.dumps(m))
    monkeypatch.setattr(retirement, 'MANIFEST_PATH', path)
    with pytest.raises(sync.SyncError, match='RETIREMENT_MANIFEST_INVALID'): retirement.load_manifest()


def test_best_shot_target_blocks_retirement(approved):
    _, old, current, data = approved
    sync.write_json(data / 'best-shots.json', {'version': 1, 'entries': [
        {'selection_id': 'protected', 'observation_id': old['observations'][-1]['observation_id'], 'comment': '', 'order': 1}]})
    m = approved[0]
    with pytest.raises(sync.SyncError, match='RETIREMENT_PROTECTED_REFERENCE'):
        retirement.Retirement(old, None, data.parent).prepare(current, {}, {m['target_article_sha256']}, data)


def test_research_target_blocks_retirement(approved):
    m, old, _, data = approved
    old['observations'][-1]['gallery_name'] = '不明'
    with pytest.raises(sync.SyncError, match='RETIREMENT_PROTECTED_REFERENCE'):
        retirement.protected_targets(old, {x['observation_id'] for x in m['observations']}, data)


@pytest.mark.parametrize('damage', ['remove', 'rename', 'url', 'duplicate'])
def test_other_photo_guard_still_blocks_after_approved_seven(approved, damage):
    r, resolved = prepared(approved)
    changed = deepcopy(resolved)
    if damage == 'remove': changed['observations'].pop()
    if damage == 'rename': changed['observations'][0]['gallery_name'] = 'other'
    if damage == 'url': changed['observations'][0]['src'] = 'replacement'
    if damage == 'duplicate': changed['observations'].append(deepcopy(changed['observations'][0])); changed['observations'][-1]['observation_id'] = 'extra'
    changed['summary']['observation_count'] = len(changed['observations'])
    with pytest.raises(sync.SyncError): sync.reconcile_ids(changed, r.effective_previous)


def test_sealed_migration_is_carried_forward_without_repeating_deletion(approved, monkeypatch):
    r, resolved = prepared(approved)
    m, _, _, data = approved
    payload = {'retirement': r.ledger}
    next_run = retirement.Retirement(resolved, payload, data.parent)
    assert next_run.prepare(deepcopy(resolved), {}, {m['target_article_sha256']}, data) == resolved
    assert next_run.applied_count == 0
    assert next_run.status()['state'] == 'ALREADY_APPLIED'
    assert sync.reconcile_ids(deepcopy(resolved), resolved) == resolved
    assert sync.compare_inventory({sync.digest('A'): {'updated_hash':'same','images':[]}}, {sync.digest('A'): {'updated_hash':'same','images':[]}})['new_images'] == 0
    with pytest.raises(sync.SyncError, match='RETIRED_ARTICLE_REVIEW_REQUIRED'):
        next_run.prepare(resolved, {m['target_article_sha256']: {}}, set(), data)
    bad = deepcopy(r.ledger); bad['retired_count'] = 8
    with pytest.raises(sync.SyncError, match='RETIREMENT_LEDGER_INVALID'): retirement.validate_ledger(bad, resolved)
    with pytest.raises(sync.SyncError, match='RETIREMENT_LEDGER_MISSING'): retirement.Retirement(resolved, None, data.parent)


@pytest.mark.parametrize('leak', ['id', 'article_url', 'image_url', 'json_escaped_image'])
def test_public_candidate_inspection_rejects_retired_leaks(approved, tmp_path, leak):
    r, resolved = prepared(approved)
    old = approved[1]['observations'][-1]
    out = tmp_path / 'site'; out.mkdir()
    if leak == 'id': (out/'index.html').write_text(old['observation_id'])
    elif leak == 'article_url': (out/'index.html').write_text('<a href="'+old['article']['url']+'">old</a>')
    elif leak == 'image_url': (out/'index.html').write_text('<img src="'+old['src']+'">')
    else: (out/'old.json').write_text(json.dumps({'src':old['src']}).replace('/', '\\/'))
    with pytest.raises(sync.SyncError, match='RETIRED_CONTENT_IN_OUTPUT'): r.inspect_output(out, resolved)


def test_same_image_legitimately_in_another_public_article_is_not_deleted(approved, tmp_path):
    r, resolved = prepared(approved)
    old = approved[1]['observations'][-1]
    resolved['observations'][0]['src'] = old['src']
    out = tmp_path/'site';out.mkdir();(out/'index.html').write_text('<img src="'+old['src']+'">')
    result = r.inspect_output(out, resolved)
    assert result['result'] == 'PASS' and result['shared_image_urls_preserved'] == 1


def test_initial_migration_cannot_overwrite_original_checkout(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import main
    root = tmp_path/'original';root.mkdir();(root/'portal-data.json').write_bytes(b'original evidence')
    fake = SimpleNamespace(status={'version':1},previous_directory=root,retirement=SimpleNamespace(initial=True))
    monkeypatch.setattr(sync,'SyncRun',lambda *a:fake)
    monkeypatch.setattr(main,'build_gallery',lambda **k:pytest.fail('must not generate'))
    report=tmp_path/'report.json'
    assert sync.run(root,root,report)==1
    assert sync.read_json(report)['error_code']=='RETIREMENT_ORIGINAL_OVERWRITE_FORBIDDEN'
    assert (root/'portal-data.json').read_bytes()==b'original evidence'


def test_identification_history_explicit_target_article_reference_blocks(approved):
    from research_ui import build_research_cases
    m, old, _, data = approved
    old['observations'][0]['gallery_name']='不明'
    case=build_research_cases(old)[0]
    # Even a row that passes the legacy URL fallback may not point its Atom ID at the retired article.
    row={'identification_id':'history','case_id':case['case_id'],
         'article':{'article_id':'retired-article','url':case['article']['url']},
         'original_gallery_name':'不明','identified_name':'シイタケ',
         'identified_at':'2026-10-12T00:00:00+00:00','mushroom_master_id':None,'status':'identified'}
    sync.write_json(data/'research-identifications.json',{'version':1,'identifications':[row]})
    with pytest.raises(sync.SyncError,match='RETIREMENT_PROTECTED_REFERENCE'):
        retirement.protected_targets(old,{x['observation_id'] for x in m['observations']},data)
