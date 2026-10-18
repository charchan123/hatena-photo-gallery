"""CI must exercise production ID reconciliation and fail closed before tests."""
from pathlib import Path
import yaml


def test_admin_generation_uses_immutable_baseline_and_guarded_preview():
    workflow = yaml.load(Path('.github/workflows/admin-validate.yml').read_text(), Loader=yaml.BaseLoader)
    assert workflow['permissions'] == {'contents':'read', 'pull-requests':'read'}
    assert set(workflow['on']) == {'pull_request'}
    steps = workflow['jobs']['validate']['steps']
    checkout = next(s['with'] for s in steps if s.get('with',{}).get('ref') == 'gh-pages')
    assert checkout['persist-credentials'] == 'false'
    assert checkout['path'] == '.validation-previous'
    assert set(checkout['sparse-checkout'].split()) == {'/portal-data.json','/phase3c-production-status.json','/article-sync-snapshot.json'}
    generation = next(i for i,s in enumerate(steps) if 'python article_sync.py' in s.get('run',''))
    command = steps[generation]['run']
    assert all(flag in command for flag in ('--previous .validation-previous','--safe-deletions','--deletion-preview','--output cache/never-published-admin-validation'))
    assert 'continue-on-error' not in steps[generation]
    verification = steps[generation+1]['run']
    assert "report['result'] == 'PREVIEW'" in verification
    assert "report['best_shot_references_preserved'] == len(selections)" in verification
    assert "report['deletions']['history_persisted'] is False" in verification
    assert "assert not Path('cache/never-published-admin-validation').exists()" in verification
    assert not any('python main.py' in s.get('run','') or 'deploy' in s.get('uses','') for s in steps)
    assert generation < next(i for i,s in enumerate(steps) if 'pytest' in s.get('run',''))
