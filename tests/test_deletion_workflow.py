from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_daily_keeps_atomic_deploy_after_durable_guard():
    workflow=yaml.safe_load((ROOT/'.github/workflows/generate.yml').read_text())
    assert workflow['concurrency']=={'group':'hatena-gallery-publication','cancel-in-progress':False}
    assert workflow['jobs']['build']['if']=="github.ref == 'refs/heads/main'"
    steps=workflow['jobs']['build']['steps']
    generation=next(s for s in steps if '--safe-deletions' in s.get('run',''))
    assert generation['if']=='always()'
    assert '--deletion-preview' not in generation['run']
    deployment=next(s for s in steps if s.get('uses','').startswith('JamesIves/'))
    assert 'if' not in deployment # GitHub's default success() gating remains.
    assert steps.index(generation)<steps.index(deployment)
    assert deployment['with']['branch']=='gh-pages'
    assert workflow['permissions']['pull-requests']=='read'
    assert next(s for s in steps if s.get('uses','').startswith('actions/upload-artifact'))['if']=='always()'


def test_live_audit_workflow_cannot_publish_or_persist_confirmation():
    text=(ROOT/'.github/workflows/deletion-audit.yml').read_text()
    workflow=yaml.safe_load(text)
    assert workflow['permissions']=={'contents':'read','pull-requests':'read'}
    assert '--safe-deletions' in text and '--deletion-preview' in text
    assert 'history_persisted' in text and 'never-published-deletion-preview' in text
    assert 'git push' not in text and 'JamesIves/' not in text and 'workflow_dispatch:' not in text
    assert 'pull_request:' in text and 'schedule:' not in text
