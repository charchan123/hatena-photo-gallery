"""Real isolated Git worktrees and an intercepted gh; never access GitHub."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from admin import git_workflow as workflow
from admin.draft_store import DraftStore


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True,
                          encoding='utf-8', errors='replace')


@pytest.fixture
def repository(tmp_path, monkeypatch):
    remote = tmp_path / 'remote.git'
    git(tmp_path, 'init', '--bare', str(remote))
    checkout = tmp_path / 'Windows path with spaces 管理室'
    checkout.mkdir()
    git(checkout, 'init', '-b', 'main')
    git(checkout, 'config', 'user.email', 'fixture@example.test')
    git(checkout, 'config', 'user.name', 'Isolated test')
    baseline = {'data/best-shots.json': {'version':1, 'entries':[], 'annual_best':{}},
                'data/update-notices.json': {'version':1, 'events':[]},
                'data/research-identifications.json': {'version':1, 'identifications':[]}}
    (checkout / 'data').mkdir()
    for path, value in baseline.items():
        (checkout/path).write_text(json.dumps(value), encoding='utf-8')
    git(checkout, 'add', 'data')
    git(checkout, 'commit', '-m', 'synthetic baseline')
    git(checkout, 'remote', 'add', 'origin', str(remote))
    git(checkout, 'push', '-u', 'origin', 'main')
    original_main = git(checkout, 'rev-parse', 'HEAD').stdout.strip()
    files = deepcopy(baseline)
    files['data/best-shots.json']['entries'] = [{'fixture':'架空の変更'}]
    validation = {'best_shots':1, 'notices':0, 'identifications':0}
    commands, state = [], {}
    original_run = workflow.run
    monkeypatch.setattr(workflow, 'repository_status', lambda:{'gh_authenticated':True})
    def run(args, *, cwd=None, check=True):
        commands.append(list(args))
        assert args[0] in {'git','gh'}, 'local Python/pytest must never run'
        if state.get('fail') and args[:len(state['fail'])] == state['fail']:
            raise workflow.GitWorkflowError('fixture failure: permission denied')
        if args[:3] == ['git','ls-remote','--exit-code'] and state.get('race'):
            return SimpleNamespace(stdout='0'*40+'\trefs/heads/main\n')
        if args[:4] == ['git','diff','--cached','--name-only'] and state.get('unexpected'):
            return SimpleNamespace(stdout='data/best-shots.json\nunapproved.py\n')
        if args[:3] == ['gh','pr','create']:
            state['body'] = Path(args[args.index('--body-file')+1]).read_text(encoding='utf-8')
            state['staged_files'] = {path:json.loads((Path(cwd)/path).read_text(encoding='utf-8')) for path in baseline}
            return SimpleNamespace(stdout=state.get('url','https://github.com/fixture/test/pull/123')+'\n')
        return original_run(args, cwd=Path(cwd) if cwd else checkout, check=check)
    monkeypatch.setattr(workflow, 'run', run)
    # Durable local snapshot must survive every outcome byte-for-byte.
    draft = SimpleNamespace(files=lambda:files)
    store = DraftStore(checkout)
    store.baseline = baseline
    store.base_hashes = {name:'synthetic-baseline' for name in baseline}
    store.save(draft)
    saved = store.path.read_bytes()
    yield SimpleNamespace(root=checkout, remote=remote, baseline=baseline, files=files,
                          validation=validation, commands=commands, state=state, main=original_main)
    assert store.path.read_bytes() == saved
    assert git(checkout, 'branch','--show-current').stdout.strip() == 'main'
    assert git(checkout,'status','--porcelain','--untracked-files=no').stdout == ''


def create(r):
    return workflow.create_pull_request(r.files, r.validation, baseline=r.baseline)


def test_success_is_draft_only_and_serializes_utf8_without_pytest(repository):
    r=repository
    result=create(r)
    assert result['draft'] and result['ci_status']=='pending'
    command=next(c for c in r.commands if c[:3]==['gh','pr','create'])
    assert '--draft' in command and '--body-file' in command and '--body' not in command
    assert r.state['staged_files']==r.files
    assert '`data/best-shots.json`' in r.state['body'] and '\\`' not in r.state['body']
    assert 'GitHub Actions' in r.state['body'] and r.main in r.state['body']
    changed=git(r.root,'diff','--name-only','main',result['branch']).stdout.splitlines()
    assert changed==['data/best-shots.json']
    assert git(r.root,'rev-parse','main').stdout.strip()==r.main
    assert not any('merge' in c or 'rebase' in c or 'reset' in c for c in r.commands)


@pytest.mark.parametrize('path',workflow.ADMIN_DATA_FILES)
def test_all_baseline_documents_must_match_even_if_not_edited(repository,path):
    r=repository
    r.baseline[path]['version']=True  # True must not compare equal to JSON 1.
    with pytest.raises(workflow.GitWorkflowError,match=path):create(r)
    assert not any(c[1]=='push' for c in r.commands)


def test_stale_code_stops_before_worktree_or_push(repository):
    r=repository
    # Advance remote main independently; leave the running checkout untouched.
    git(r.root,'branch','advance')
    other=r.root.parent/'new main'
    git(r.root,'worktree','add',str(other),'advance')
    (other/'new-code.txt').write_text('new main code',encoding='utf-8')
    git(other,'add','new-code.txt');git(other,'commit','-m','advance main')
    git(other,'push','origin','HEAD:main')
    with pytest.raises(workflow.GitWorkflowError,match='実行中のコード'):create(r)
    assert not any(c[1:3]==['worktree','add'] for c in r.commands)
    assert git(r.root,'rev-parse','HEAD').stdout.strip()==r.main


def test_main_advance_during_preparation_is_not_rebased(repository):
    r=repository;r.state['race']=True
    with pytest.raises(workflow.GitWorkflowError,match='作成中にmain'):create(r)
    assert not any(c[1]=='push' for c in r.commands)


@pytest.mark.parametrize('prefix', [['git','fetch'],['git','commit'],['git','push'],['gh','pr','create']])
def test_external_failures_keep_draft_with_cause_and_recovery(repository,prefix):
    r=repository;r.state['fail']=prefix
    with pytest.raises(workflow.GitWorkflowError,match='permission denied') as error:create(r)
    assert '下書きは保持' in str(error.value)
    assert '確認' in str(error.value)
    if prefix[0]=='gh':assert 'GitHubのブランチ admin/' in str(error.value)


def test_auth_failure_has_login_instructions_without_git_mutation(repository,monkeypatch):
    monkeypatch.setattr(workflow,'repository_status',lambda:{'gh_authenticated':False})
    with pytest.raises(workflow.GitWorkflowError,match='gh auth login'):create(repository)
    assert not repository.commands


def test_write_failure_stops_before_commit_and_push(repository,monkeypatch):
    r=repository;write=Path.write_text
    def fail(path,*args,**kwargs):
        if path.name=='best-shots.json' and 'kinoko-admin-' in str(path):raise OSError('disk full')
        return write(path,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',fail)
    with pytest.raises(workflow.GitWorkflowError,match='空き容量.*disk full'):create(r)
    assert not any(c[1] in {'commit','push'} for c in r.commands)


def test_unexpected_staging_stops_before_commit(repository):
    r=repository;r.state['unexpected']=True
    with pytest.raises(workflow.GitWorkflowError,match='ステージ対象'):create(r)
    assert not any(c[1] in {'commit','push'} for c in r.commands)


@pytest.mark.parametrize('url',['','https://github.com/fixture/test','https://github.com/fixture/test/pull/1\nwarning'])
def test_missing_or_malformed_success_url_is_not_reported_as_success(repository,url):
    repository.state['url']=url
    with pytest.raises(workflow.GitWorkflowError,match='URLを確認'):create(repository)


def test_no_changes_cannot_create_pr(repository):
    repository.files=deepcopy(repository.baseline)
    with pytest.raises(workflow.GitWorkflowError,match='変更がありません'):create(repository)


def test_missing_baseline_or_validation_cannot_publish(repository):
    r=repository
    with pytest.raises(workflow.GitWorkflowError,match='照合情報'):
        workflow.create_pull_request(r.files,r.validation)
    with pytest.raises(workflow.GitWorkflowError,match='入力検証'):
        workflow.create_pull_request(r.files,{},baseline=r.baseline)


def test_run_preserves_windows_utf8_and_stdout_error(monkeypatch):
    def failure(args,**kwargs):
        assert kwargs['encoding']=='utf-8' and kwargs['errors']=='replace' and not kwargs['shell']
        raise subprocess.CalledProcessError(1,args,output='具体的な原因',stderr='')
    monkeypatch.setattr(workflow.subprocess,'run',failure)
    with pytest.raises(workflow.GitWorkflowError,match='具体的な原因'):
        workflow.run(['git','status'])


def test_jst_manual_date_needs_no_iana_database_at_utc_day_boundary(monkeypatch):
    import best_shot_ui as best
    class Clock(datetime):
        @classmethod
        def now(cls,tz):
            assert tz.utcoffset(None).total_seconds()==9*3600
            return datetime(2026,10,20,15,30,tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(best,'datetime',Clock)
    assert best._manual_date('2026-10-21').isoformat()=='2026-10-21'
    with pytest.raises(best.BestShotConfigError):best._manual_date('2026-10-22')
    assert 'zoneinfo' not in Path(best.__file__).read_text(encoding='utf-8')


def test_ci_gate_remains_read_only_and_covers_windows_and_full_guarded_validation():
    import yaml
    ci=yaml.load(Path('.github/workflows/admin-pr-regressions.yml').read_text(encoding='utf-8'),Loader=yaml.BaseLoader)
    assert ci['permissions']=={'contents':'read'} and set(ci['on'])=={'pull_request'}
    assert ci['jobs']['admin-pr']['strategy']['matrix']['os']==['ubuntu-latest','windows-latest']
    steps=ci['jobs']['admin-pr']['steps']
    assert steps[0]['with']['ref']=='${{ github.event.pull_request.head.sha }}'
    assert steps[0]['with']['persist-credentials']=='false'
    text=Path('.github/workflows/admin-validate.yml').read_text(encoding='utf-8')
    assert 'python -m pytest -q' in text and '--deletion-preview' in text
    assert '--output cache/never-published-admin-validation' in text
    assert 'contents: read' in text and 'pull-requests: read' in text
    assert 'continue-on-error' not in text
    assert not any('merge_pull_request' in s.get('run','') or 'deploy' in s.get('uses','') for s in steps)


def test_cleanup_failure_cannot_hide_created_draft_url(repository):
    repository.state['fail']=['git','worktree','remove']
    assert create(repository)['url']=='https://github.com/fixture/test/pull/123'


def test_nonfinite_json_is_rejected_before_fetch(repository):
    repository.files['data/best-shots.json']['bad']=float('nan')
    with pytest.raises(workflow.GitWorkflowError,match='JSONとして'):create(repository)
    assert not repository.commands
