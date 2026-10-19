"""Persistence and GitHub CLI path regressions; tests never touch production."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from admin.core import ChangeSet
from admin.draft_store import DraftRecoveryError, DraftStore
from admin import git_workflow


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    files = {
        "best-shots.json": {"version": 1, "entries": [], "annual_best": {}},
        "update-notices.json": {"version": 1, "events": []},
        "research-identifications.json": {"version": 1, "identifications": []},
        "mushroom-master.json": {"version": 1, "entries": []},
    }
    for name, value in files.items():
        (data / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("admin.core.DATA", data)
    portal = {"version": 1, "observations": [
        {"observation_id": "obs-1", "gallery_name": "ベニテングタケ",
         "src": "https://example.test/1.jpg",
         "capture": {"date": "2026-10-01"}, "article": {"title": "記録"}}]}
    return tmp_path, portal


def add_entry(draft):
    draft.add_best_shot({"selection_id": "best-1", "observation_id": "obs-1",
                         "comment": "編集したコメント", "order": 1}, add_notice=True)


def test_atomic_save_and_restart_restore_full_changeset(sandbox):
    root, portal = sandbox
    draft = ChangeSet(portal)
    store = DraftStore(root)
    store.recover(draft)
    add_entry(draft)
    store.save(draft)
    path = root / "admin/local-state/admin-draft.json"
    assert store.saved and path.is_file()
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert list(snapshot["files"]) == list(draft.files())
    assert len(snapshot["files"]["data/best-shots.json"]["entries"]) == 1
    assert len(snapshot["files"]["data/update-notices.json"]["events"]) == 1
    recovered = DraftStore(root)
    restored = recovered.recover(ChangeSet(portal))
    assert recovered.restored and recovered.saved
    assert restored.files() == draft.files()
    # Autosave must not write to the production data path.
    assert json.loads((root / "data/best-shots.json").read_text())["entries"] == []


def test_fail_closed_when_main_data_changes_and_preserves_backup(sandbox):
    root, portal = sandbox
    draft = ChangeSet(portal)
    store = DraftStore(root)
    store.recover(draft)
    add_entry(draft)
    store.save(draft)
    path = store.path
    unchanged = path.read_bytes()
    main = root / "data/best-shots.json"
    source = json.loads(main.read_text())
    source["entries"] = [{"selection_id": "other"}]
    main.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(DraftRecoveryError, match="現在のmain"):
        DraftStore(root).recover(ChangeSet(portal))
    assert path.read_bytes() == unchanged


def test_draft_already_merged_becomes_clean_on_restart(sandbox):
    root, portal = sandbox
    draft = ChangeSet(portal)
    store = DraftStore(root)
    store.recover(draft)
    add_entry(draft)
    store.save(draft)
    for name, value in draft.files().items():
        (root / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    recovered = DraftStore(root)
    restored = recovered.recover(ChangeSet(portal))
    assert restored.files() == draft.files()
    assert not recovered.saved and not recovered.restored
    assert not store.path.exists()


def test_invalid_snapshot_blocks_startup_without_deleting(sandbox):
    root, portal = sandbox
    store = DraftStore(root)
    store.path.parent.mkdir(parents=True)
    store.path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(DraftRecoveryError, match="復元できません"):
        store.recover(ChangeSet(portal))
    assert store.path.read_text(encoding="utf-8") == "{invalid"


def test_write_failure_keeps_previous_snapshot(sandbox, monkeypatch):
    root, portal = sandbox
    draft = ChangeSet(portal)
    store = DraftStore(root)
    store.recover(draft)
    add_entry(draft)
    store.save(draft)
    before = store.path.read_bytes()
    draft.update_best_shot("best-1", {"comment": "新しい文章"})
    monkeypatch.setattr("admin.draft_store.os.replace",
                        lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        store.save(draft)
    assert store.path.read_bytes() == before
    assert not list(store.path.parent.glob(".admin-draft-*.tmp"))


def test_reverted_draft_removes_only_local_snapshot(sandbox):
    root, portal = sandbox
    draft = ChangeSet(portal)
    store = DraftStore(root)
    store.recover(draft)
    add_entry(draft)
    store.save(draft)
    assert store.path.exists()
    draft.best_shots = deepcopy(store.baseline["data/best-shots.json"])
    draft.notices = deepcopy(store.baseline["data/update-notices.json"])
    store.save(draft)
    assert not store.path.exists()
    assert not store.saved


def test_gh_cli_fallback_works_with_old_windows_path(tmp_path, monkeypatch):
    cli = tmp_path / "GitHub CLI" / "gh.exe"
    cli.parent.mkdir()
    cli.write_bytes(b"")
    monkeypatch.setattr(git_workflow.shutil, "which", lambda _: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    assert git_workflow.locate_gh() == str(cli)
    commands = []
    def run(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="logged in", stderr="")
    monkeypatch.setattr(git_workflow.subprocess, "run", run)
    assert git_workflow.run(["gh", "auth", "status"]).returncode == 0
    assert commands[0][0][0] == str(cli)
    assert commands[0][1]["shell"] is False


def test_gh_without_binary_returns_actionable_error(monkeypatch):
    monkeypatch.setattr(git_workflow.shutil, "which", lambda _: None)
    for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.delenv(variable, raising=False)
    with pytest.raises(git_workflow.GitWorkflowError, match="GitHub CLI"):
        git_workflow.run(["gh", "auth", "status"])
