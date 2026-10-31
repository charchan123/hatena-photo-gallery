"""Initial staging DB checks are offline only; never open an existing DB."""
import json
from pathlib import Path
import sqlite3
import pytest
from research_comments import registry_digest, fingerprint

ROOT = Path(__file__).resolve().parents[1]
ORDER = ['0001_comments.sql', '0002_guards.sql', '0003_reviewed_cases.sql']

def fresh():
    db = sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys=ON')
    for name in ORDER:
        db.executescript((ROOT/'comments/migrations'/name).read_text(encoding='utf-8'))
    return db

def test_initial_migration_order_registry_and_all_anchors():
    assert sorted(p.name for p in (ROOT/'comments/migrations').glob('*.sql')) == ORDER
    registry = json.loads((ROOT/'comments/cases.json').read_text(encoding='utf-8'))
    db = fresh()
    meta = dict(db.execute('SELECT key,value FROM metadata'))
    assert meta['registry_sha256'] == registry_digest(registry)
    assert meta['schema_version'] == '1' and len(meta['installation_id']) == 32
    assert dict(db.execute('SELECT id,identity_hash FROM cases')) == {
        r['id']:fingerprint(r['article_identity'],r['observation_ids']) for r in registry['cases']}
    assert dict(db.execute('SELECT alias,case_id FROM aliases')) == {
        a:r['id'] for r in registry['cases'] for a in r['render_ids']}
    assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    assert db.execute('SELECT count(*) FROM comments').fetchone() == (0,)
    assert db.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone() == (6,)

def test_reapplying_initial_seed_fails_without_changing_identity_or_cases():
    db = fresh()
    before = '\n'.join(db.iterdump())
    with pytest.raises(sqlite3.IntegrityError):
        db.executescript((ROOT/'comments/migrations'/ORDER[-1]).read_text(encoding='utf-8'))
    assert '\n'.join(db.iterdump()) == before
    # A second fresh database gets a different installation ID.
    other = fresh()
    assert db.execute("SELECT value FROM metadata WHERE key='installation_id'").fetchone() != other.execute("SELECT value FROM metadata WHERE key='installation_id'").fetchone()

def test_integration_allowance_never_accepts_changed_main_or_changed_pr137(monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location('integration_protection', ROOT/'tests/browser/comments_integration_protection.py')
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    def git(*args):
        ref, path = args[-1].split(':',1)
        return {'base':b'original',gate.PR135:b'original',gate.PR137:b'reviewed'}[ref]
    monkeypatch.setattr(gate,'git',git)
    gate.assert_reviewed_source('base','admin/comments_client.py',b'reviewed')
    with pytest.raises(AssertionError):
        gate.assert_reviewed_source('base','admin/comments_client.py',b'changed')
    with pytest.raises(AssertionError):
        gate.assert_reviewed_source('base','assets/gallery.js',b'reviewed')
    monkeypatch.setattr(gate,'git',lambda *args:b'new main' if args[-1].startswith('base:') else git(*args))
    with pytest.raises(AssertionError,match='main advanced'):
        gate.assert_reviewed_source('base','admin/comments_client.py',b'reviewed')
