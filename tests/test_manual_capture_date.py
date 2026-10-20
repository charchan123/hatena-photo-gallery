"""Manual dates, stable provenance and owner-confirmed source reconciliation."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from admin.core import ChangeSet
from admin.draft_store import DraftStore, DraftRecoveryError
from best_shot_ui import BestShotConfigError, validate_best_shot_config, render_best_shot_page, build_best_shot_model
from article_sync import validate_references

@pytest.fixture
def sandbox(tmp_path,monkeypatch):
    data=tmp_path/'data';data.mkdir()
    for name,obj in {'best-shots':{'version':1,'entries':[],'annual_best':{}},'update-notices':{'version':1,'events':[]},'research-identifications':{'version':1,'identifications':[]},'mushroom-master':{'version':1,'entries':[]}}.items():
        (data/(name+'.json')).write_text(json.dumps(obj))
    monkeypatch.setattr('admin.core.DATA',data)
    def obs(i,date):return {'observation_id':i,'gallery_name':'試験きのこ','src':'https://example.test/'+i+'.jpg','capture':{'date':date,'date_source':'other_confirmed' if date else None},'article':{'title':'2099年の記事','article_id':'article-'+i,'url':'https://example.test/day'}}
    portal={'version':1,'observations':[obs('undated',None),obs('dated','2025-10-01'),obs('second',None)]}
    return tmp_path,portal,ChangeSet(portal)

def entry(oid='undated',sid='best-1',order=1,**kw):
    return dict(selection_id=sid,observation_id=oid,comment='本人のコメント',order=order,**kw)

def test_source_date_without_exif_is_authoritative_and_unknown_without_input_rejected(sandbox):
    _,p,d=sandbox
    d.add_best_shot(entry('dated'))
    assert validate_best_shot_config(d.best_shots,p)[0]['capture_date']=='2025-10-01'
    with pytest.raises(BestShotConfigError):d.add_best_shot(entry('undated','two'))

@pytest.mark.parametrize('bad',['',None,0,True,[],{},'2025-2-01','2025-02-30','2025-02-29','1900-02-29','2024-02-30','2024-01-01T00:00:00Z',' 2024-01-01','9999-01-01','２０２４-０１-０１'])
def test_invalid_manual_dates_are_atomic_and_field_scoped(sandbox,bad):
    _,p,d=sandbox;before=deepcopy(d.files())
    with pytest.raises(BestShotConfigError)as e:d.add_best_shot(entry(manual_capture_date=bad),add_notice=True)
    assert e.value.field=='manual_capture_date'
    assert d.files()==before

@pytest.mark.parametrize('date',['2024-02-29','2000-02-29','2025-10-01'])
def test_valid_date_leap_year_month_order_publication_and_annual(sandbox,date):
    _,p,d=sandbox;before=deepcopy(p)
    d.add_best_shot(entry(manual_capture_date=date),annual=True)
    resolved=validate_best_shot_config(d.best_shots,p)[0]
    assert resolved['capture_date']==date and resolved['capture_date_source']=='owner_manual'
    assert d.best_shots['annual_best']=={date[:4]:'best-1'}
    assert d.best_shots['entries'][0]['manual_capture_date_origin']=='owner_confirmed_undated_source'
    assert date[:4]+'年' in render_best_shot_page(build_best_shot_model(d.best_shots,p))
    assert p==before


def test_duplicate_photo_order_month_move_and_annual_year_change(sandbox):
    _,p,d=sandbox
    d.add_best_shot(entry('dated',sid='dated-best'))
    with pytest.raises(BestShotConfigError):d.add_best_shot(entry(manual_capture_date='2025-10-03'))
    d.add_best_shot(entry(order=2,manual_capture_date='2025-10-03'))
    with pytest.raises(BestShotConfigError):d.add_best_shot(entry(sid='duplicate',order=3,manual_capture_date='2025-10-03'))
    d.set_annual('2025','best-1')
    before=deepcopy(d.files())
    with pytest.raises(BestShotConfigError):d.update_best_shot('best-1',{'manual_capture_date':'2024-10-01'})
    assert d.files()==before
    d.set_annual('2025',None)
    d.update_best_shot('best-1',{'manual_capture_date':'2024-09-01','order':1})
    assert validate_best_shot_config(d.best_shots,p)[1]['year']==2024
    with pytest.raises(BestShotConfigError):d.set_annual('2025','best-1')


def test_dated_source_override_rejected_and_replacement_never_inherits_date(sandbox):
    _,p,d=sandbox
    with pytest.raises(BestShotConfigError):d.add_best_shot(entry('dated',manual_capture_date='2024-01-01'))
    d.add_best_shot(entry(manual_capture_date='2024-01-01'))
    before=deepcopy(d.files())
    with pytest.raises(BestShotConfigError):d.update_best_shot('best-1',{'observation_id':'second'})
    assert d.files()==before
    d.update_best_shot('best-1',{'observation_id':'dated'})
    assert 'manual_capture_date' not in d.best_shots['entries'][0]
    assert 'manual_capture_date_origin' not in d.best_shots['entries'][0]


def test_future_source_appearance_keeps_manual_date_and_owner_reconciles(sandbox):
    root,p,d=sandbox
    d.add_best_shot(entry(manual_capture_date='2024-03-01'))
    original=deepcopy(d.files());previous=deepcopy(p)
    p['observations'][0]['capture']['date']='2025-10-01'
    row=validate_best_shot_config(d.best_shots,p)[0]
    assert row['capture_date']=='2024-03-01' and row['source_capture_date']=='2025-10-01'
    assert row['capture_date_conflict'] and row['capture_date_review_required']
    assert d.files()==original
    with pytest.raises(BestShotConfigError):d.update_best_shot('best-1',{'manual_capture_source_ack':'2025-10-02'})
    d.update_best_shot('best-1',{'manual_capture_source_ack':'2025-10-01'})
    assert not validate_best_shot_config(d.best_shots,p)[0]['capture_date_review_required']
    # Real daily-sync reference guard continues with stable IDs/URLs.
    (root/'data/best-shots.json').write_text(json.dumps(d.best_shots))
    assert validate_references(p,previous,root/'data')['best_shot_references_preserved']==1
    d.set_annual('2024','best-1');before=deepcopy(d.files())
    with pytest.raises(BestShotConfigError):d.update_best_shot('best-1',{'manual_capture_date':None})
    assert d.files()==before
    d.set_annual('2024',None)
    d.update_best_shot('best-1',{'manual_capture_date':None})
    assert 'manual_capture_date'not in d.best_shots['entries'][0]
    assert validate_best_shot_config(d.best_shots,p)[0]['capture_date']=='2025-10-01'


def test_autosave_restart_and_pr_payload_preserve_date_and_provenance(sandbox):
    root,p,d=sandbox;store=DraftStore(root);store.recover(d)
    d.add_best_shot(entry(manual_capture_date='2024-02-29'),add_notice=True);store.save(d)
    recovered=DraftStore(root);restored=recovered.recover(ChangeSet(p))
    assert recovered.restored and restored.files()==d.files()
    assert restored.files()['data/best-shots.json']['entries'][0]['manual_capture_date']=='2024-02-29'
    assert len(restored.files()['data/update-notices.json']['events'])==1
    assert json.loads((root/'data/best-shots.json').read_text())['entries']==[]
    main=root/'data/best-shots.json';main.write_text(json.dumps({'version':1,'entries':[entry('dated')],'annual_best':{}}))
    with pytest.raises(DraftRecoveryError):DraftStore(root).recover(ChangeSet(p))


def test_common_validator_requires_provenance_and_rejects_unknown_fields(sandbox):
    _,p,d=sandbox
    for row in [entry(manual_capture_date='2024-01-01'),entry(manual_capture_date_origin='owner_confirmed_undated_source'),entry(extra_date='2024-01-01')]:
        with pytest.raises(BestShotConfigError):validate_best_shot_config({'version':1,'entries':[row],'annual_best':{}},p)


def test_pr_writer_serializes_manual_fields_without_touching_source_data(sandbox,monkeypatch):
    from types import SimpleNamespace
    from admin import git_workflow
    root,p,d=sandbox
    d.add_best_shot(entry(manual_capture_date='2024-02-29'),add_notice=True)
    monkeypatch.setattr(git_workflow,'repository_status',lambda:{'gh_authenticated':True})
    captured={}
    def run(args,**kwargs):
        if args[:3]==['git','worktree','add']:
            (Path(args[5])/'data').mkdir()
        if args[:2]==['python','-m']:
            captured.update(json.loads((Path(kwargs['cwd'])/'data/best-shots.json').read_text()))
        return SimpleNamespace(returncode=1 if args[:3]==['git','diff','--cached']else 0,stdout='https://example.test/isolated-pr')
    monkeypatch.setattr(git_workflow,'run',run)
    git_workflow.create_pull_request(d.files(),d.validate())
    assert captured['entries'][0]['manual_capture_date']=='2024-02-29'
    assert captured['entries'][0]['manual_capture_date_origin']=='owner_confirmed_undated_source'
    assert json.loads((root/'data/best-shots.json').read_text())['entries']==[]
