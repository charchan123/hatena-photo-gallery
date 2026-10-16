from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_daily_keeps_atomic_deploy_after_durable_guard():
    workflow=yaml.safe_load((ROOT/'.github/workflows/generate.yml').read_text())
    assert workflow['concurrency']=={'group':'hatena-gallery-publication','cancel-in-progress':False}
    assert workflow['jobs']['build']['if']=="github.ref == 'refs/heads/main'"
    assert workflow['env']['SAFE_PHOTO_DELETION_PUBLISH_ENABLED']=='false'
    steps=workflow['jobs']['build']['steps']
    generation=next(s for s in steps if '--safe-deletions' in s.get('run',''))
    assert generation['if']=='always()'
    assert '--deletion-preview' not in generation['run']
    deployment=next(s for s in steps if s.get('uses','').startswith('JamesIves/'))
    assert deployment['if']=="success() && env.SAFE_PHOTO_DELETION_PUBLISH_ENABLED == 'true'"
    assert '--deletion-observe-only' in generation['run']
    assert 'SAFE_PHOTO_DELETION_PUBLISH_ENABLED' in generation['run']
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
    assert 'pull_request:' in text and 'schedule:' in text
    assert "github.event_name == 'schedule'" in workflow['jobs']['audit']['if']
    summary=next(s for s in workflow['jobs']['audit']['steps'] if s.get('run')=='python deletion_monitor.py')
    assert summary['if']=='always()'


def test_monitor_reports_only_counts_and_missing_evidence_fails_closed(tmp_path):
    import json
    from deletion_monitor import summarize
    text,pending=summarize(tmp_path)
    assert pending and '不足' in text
    (tmp_path/'deletion-live-audit.json').write_text(json.dumps({'read_only':True,'publication':'NOT_ATTEMPTED',
        'counts':{'deleted_images':16,'protected_deletion_candidates':2},'private_note':'DO_NOT_PRINT'}))
    (tmp_path/'deletion-preview.json').write_text(json.dumps({'result':'BLOCKED','raw_body':'DO_NOT_PRINT'}))
    text,pending=summarize(tmp_path)
    assert pending and '16件' in text and '2件' in text and 'DO_NOT_PRINT' not in text
    (tmp_path/'deletion-preview.json').write_text(json.dumps({'result':'PREVIEW'}))
    assert summarize(tmp_path)[1] is False
