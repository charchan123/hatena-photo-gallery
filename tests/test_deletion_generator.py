"""Real generator, strict Atom fixture transport, isolated Git evidence only."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import subprocess

import article_sync as sync
import deletion_guard as guard_module
from sync_deletions import instant
from test_article_sync import atom_entry,feed
from test_sync_automatic_updates import configure
from test_deletion_guard import Store
from test_sync_deletions import T


def pin(directory):
    def git(*args):return subprocess.check_output(['git',*args],cwd=directory,stderr=subprocess.DEVNULL,text=True).strip()
    git('init');git('add','portal-data.json','article-sync-snapshot.json','phase3c-production-status.json')
    git('-c','user.name=fixture','-c','user.email=fixture@example.test','commit','-m','Pin fixture publication')


def test_real_daily_generator_confirms_deletion_preserves_survivors_and_replays(tmp_path,monkeypatch):
    ids=['A']+['B'+str(i) for i in range(11)]
    old=''.join(atom_entry(aid,src='https://images.example/'+aid+'.jpg') for aid in ids)
    changed=''.join(atom_entry(aid,src='https://images.example/'+aid+'.jpg') for aid in ids if aid!='B0')+atom_entry('NEW',src='https://images.example/NEW.jpg')
    draft=atom_entry('retired-fixture',draft='yes')
    main,calls,previous=configure(monkeypatch,tmp_path,[feed(old+draft)]+[feed(changed+draft)]*3)
    report=tmp_path/'report.json';baseline=tmp_path/'baseline'
    assert sync.run(previous,baseline,report)==0,sync.read_json(report)
    # Exercise the seven-photo validator with a synthetic excluded draft ID.
    # The production manifest stays untouched (separately byte-verified).
    import sync_retirement
    legacy=deepcopy(sync_retirement.load_manifest())
    legacy['target_article_sha256']=sync.digest('retired-fixture')
    monkeypatch.setattr(sync_retirement,'load_manifest',lambda:deepcopy(legacy))
    sealed=sync.read_json(baseline/'article-sync-snapshot.json')
    sealed['payload']['retirement']={**sync_retirement.ledger_fields(sync_retirement.load_manifest()),'applied_at':T}
    sealed['sha256']=sync.payload_hash(sealed['payload'])
    sync.write_json(baseline/'article-sync-snapshot.json',sealed)
    pin(baseline)
    before=sync.read_json(baseline/'portal-data.json')
    removed=next(r for r in before['observations'] if r['article']['article_id']=='B0')
    store=Store([]);hour=[0]
    class Clock:
        @staticmethod
        def now(tz=None):return instant(T)+timedelta(hours=hour[0])
    monkeypatch.setattr(guard_module,'datetime',Clock)
    real_guard=guard_module.DeletionGuard
    class FixtureGuard(real_guard):
        def __init__(self,previous,snapshot,commit,root,run_id,**kwargs):
            super().__init__(previous,snapshot,commit,tmp_path,run_id,store=store,pending=[],**kwargs)
    monkeypatch.setattr(guard_module,'DeletionGuard',FixtureGuard)
    monkeypatch.setenv('GITHUB_RUN_ID','123');monkeypatch.setenv('GITHUB_RUN_ATTEMPT','1')
    output=tmp_path/'candidate'
    assert sync.run(baseline,output,report,safe_deletions=True)==1
    assert sync.read_json(report)['error_code']=='DELETION_CONFIRMATION_OR_APPROVAL_PENDING'
    assert not output.exists() and len(store.history)==2
    hour[0]=7;monkeypatch.setenv('GITHUB_RUN_ID','456')
    assert sync.run(baseline,output,report,safe_deletions=True)==0,sync.read_json(report)
    current=sync.read_json(output/'portal-data.json');sealed=sync.read_json(output/'article-sync-snapshot.json')
    sync.validate_snapshot(sealed,current)
    old_ids={r['observation_id'] for r in before['observations']}
    new_ids={r['observation_id'] for r in current['observations']}
    assert old_ids-new_ids=={removed['observation_id']} and len(new_ids-old_ids)==1
    receipt=sealed['payload']['deletions'][0]
    assert receipt['mode']=='automatic' and receipt['automatic_addition_receipt']['observation_id']==removed['observation_id']
    for name in ('index','new-top','records','season','features','research','best-shots','favorite'):
        assert (output/(name+'.html')).is_file()
    assert not (output/'admin').exists() and not (output/'sync-migrations').exists()
    pin(output);hour[0]=8;monkeypatch.setenv('GITHUB_RUN_ID','789')
    again=tmp_path/'again'
    assert sync.run(output,again,report,safe_deletions=True)==0,sync.read_json(report)
    assert sync.read_json(again/'article-sync-snapshot.json')['payload']['deletions']==[receipt]
    assert {r['observation_id'] for r in sync.read_json(again/'portal-data.json')['observations']}==new_ids
    assert len(calls)==4
