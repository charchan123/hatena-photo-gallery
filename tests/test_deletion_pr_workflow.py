"""Deletion Draft PR transaction: isolated fake CLI, never contacts GitHub."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest

import article_sync as sync
from admin import deletions as app
from admin import git_workflow as workflow
from admin import sync as admin_sync
from test_admin_deletions import review,body


def transaction(tmp_path,monkeypatch,*,action='approve',failure=None):
    r,pub,live=review(tmp_path,monkeypatch)
    r.decide(body(r.rows[0],action));preview=r.preview_changes()
    files=deepcopy(preview['files']);calls=[];works=[];count={'fetch':0}
    monkeypatch.setattr(workflow,'repository_status',lambda:{'gh_authenticated':True})
    def run(args,**kw):
        calls.append(args);out=''
        if args[:3]==['git','worktree','add']:
            work=Path(args[-2]);work.mkdir(parents=True,exist_ok=True)
            if '-b' in args:
                works.append(work);(work/'tests').mkdir();(work/'tests/fixture.js').write_text('')
        if args[:3]==['git','fetch','origin']:count['fetch']+=1
        if args[:2]==['git','rev-parse']:
            out=('f'*40 if failure=='main_changed' and count['fetch']>1 else 'a'*40)
        if args[:3]==['git','ls-files','--others']:
            out='' if '--' in args else '\n'.join(sorted(files))
        if args==['git','diff','--name-only']:out='unrelated.txt' if failure=='extra_file' else ''
        if args==['git','diff','--cached','--name-only']:out='\n'.join(sorted(files))
        if args[:2]==['git','push'] and failure=='push':raise workflow.GitWorkflowError('fixture network failure')
        if args[:3]==['gh','pr','create']:
            if failure=='pr_response_lost':raise workflow.GitWorkflowError('fixture acknowledgement lost')
            assert '--draft' in args
            assert all(sync.read_json(works[0]/path)==value for path,value in files.items())
            out='https://github.com/example/fixture/pull/1'
        return SimpleNamespace(stdout=out,returncode=1 if failure=='test' and args==['python','-m','pytest','-q'] else 0)
    def generate(work,previous,output,report,env,**kw):
        assert kw=={'deletion_preview':True}
        if failure=='generation':value={'result':'BLOCKED','error_code':'OUTPUT_INTEGRITY_ERROR'};status=1
        elif action=='hold':value={'result':'BLOCKED','error_code':'DELETION_CONFIRMATION_OR_APPROVAL_PENDING'};status=1
        else:value={'result':'PREVIEW'};status=0
        sync.write_json(report,value)
        return SimpleNamespace(returncode=status)
    monkeypatch.setattr(workflow,'run',run)
    monkeypatch.setattr(admin_sync,'generate_in_worktree',generate)
    return r,preview,calls,works


@pytest.mark.parametrize('action',['approve','hold'])
def test_exact_deletion_pr_is_draft_and_never_stages_generated_or_local_state(tmp_path,monkeypatch,action):
    r,p,calls,works=transaction(tmp_path,monkeypatch,action=action)
    result=r.create_pr({'fingerprint':p['fingerprint']})
    assert result['draft'] and not result['published'] and result['local_audit_saved']
    assert next(c for c in calls if c[:2]==['git','add'])==['git','add','--',*sorted(p['files'])]
    assert ['python','-m','pytest','-q'] in calls and ['node',str(works[0]/'tests/fixture.js')] in calls
    assert all(not work.exists() for work in works)
    assert not r.preview
    assert r.create_pr({'fingerprint':p['fingerprint']})['already_created']
    assert len([c for c in calls if c[:3]==['gh','pr','create']])==1


@pytest.mark.parametrize('failure,code',[('generation','VALIDATION_BLOCKED'),('test','PR_TEST_FAILED'),('extra_file','PR_PATHS_INVALID'),('main_changed','REVIEW_STALE'),('push','network failure')])
def test_failed_deletion_pr_keeps_decisions_and_cannot_create_or_publish(tmp_path,monkeypatch,failure,code):
    r,p,calls,works=transaction(tmp_path,monkeypatch,failure=failure)
    before=deepcopy(r.state['decisions'])
    with pytest.raises((sync.SyncError,workflow.GitWorkflowError),match=code):r.create_pr({'fingerprint':p['fingerprint']})
    assert r.state['decisions']==before
    assert not any(c[:3]==['gh','pr','create'] for c in calls)
    assert all(not work.exists() for work in works)


@pytest.mark.parametrize('failure',['push','pr_response_lost'])
def test_uncertain_remote_outcome_survives_restart_and_blocks_blind_retry(tmp_path,monkeypatch,failure):
    r,p,calls,works=transaction(tmp_path,monkeypatch,failure=failure)
    with pytest.raises(workflow.GitWorkflowError):r.create_pr({'fingerprint':p['fingerprint']})
    writes=len([c for c in calls if c[:2]==['git','push'] or c[:3]==['gh','pr','create']])
    restored=app.DeletionReview(tmp_path)
    assert restored.state['pr_attempts'][p['fingerprint']]['status']=='pending_remote'
    assert restored.dashboard()['pr_attempts'][0]['branch'].startswith('admin/photo-deletion-')
    with pytest.raises(sync.SyncError,match='PR_RECOVERY_REQUIRED'):restored.create_pr({'fingerprint':p['fingerprint']})
    assert len([c for c in calls if c[:2]==['git','push'] or c[:3]==['gh','pr','create']])==writes


def test_pr_created_but_final_local_save_failure_does_not_allow_duplicate(tmp_path,monkeypatch):
    r,p,calls,works=transaction(tmp_path,monkeypatch)
    save=r.save;count=[0]
    def fail_final_save():
        count[0]+=1
        if count[0]==2:raise OSError('fixture disk full after remote success')
        save()
    monkeypatch.setattr(r,'save',fail_final_save)
    result=r.create_pr({'fingerprint':p['fingerprint']})
    assert result['url'].endswith('/pull/1') and result['local_audit_saved'] is False
    with pytest.raises(sync.SyncError,match='PR_RECOVERY_REQUIRED'):r.create_pr({'fingerprint':p['fingerprint']})
    assert len([c for c in calls if c[:3]==['gh','pr','create']])==1
