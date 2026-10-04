from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from admin.core import AdminError, ChangeSet, notice_window, safe_branch_name, validate_notices
from admin.git_workflow import GitWorkflowError, create_pull_request, run
from admin.server import AdminServer, BIND_ADDRESS
from research_identifications import ResearchIdentificationError, validate_registry
from research_ui import build_research_cases


def observation(identifier="obs-1", name="不明", date="2026-10-01"):
    return {"observation_id": identifier, "gallery_name": name, "src": "https://example.test/a.jpg",
            "capture": {"date": date}, "article": {"article_id": "entry-1", "article_path": "/entry/1",
            "title": "<unsafe>", "url": "https://example.test/entry/1"}, "production_index": 1}


@pytest.fixture
def portal(): return {"version": 1, "observations": [observation()]}


def registry_row(portal):
    case = build_research_cases(portal)[0]
    return {"version": 1, "identifications": [{"identification_id": "ident-1", "case_id": case["case_id"],
        "article": {"article_id": "entry-1"}, "original_gallery_name": "不明", "identified_name": "ベニタケ",
        "identified_at": "2026-10-01T10:00:00+09:00", "mushroom_master_id": None, "note": "", "status": "identified"}]}


def test_server_rejects_external_bind():
    with pytest.raises(ValueError, match="127.0.0.1"):
        AdminServer(("0.0.0.0", 0), Mock())
    assert BIND_ADDRESS == "127.0.0.1"


def test_notice_rules_and_expiration():
    now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    event = {"section": "research", "kind": "identified", "summary": "1種の正体が判明", "occurred_at": "2026-10-01T00:00:00+00:00"}
    validate_notices({"version": 1, "events": [event]}, now)
    assert notice_window(event, now)["active"]
    event["section"] = "guide"
    with pytest.raises(AdminError, match="research"): validate_notices({"version": 1, "events": [event]}, now)
    event.update(section="research", occurred_at="2099-01-01T00:00:00+00:00")
    with pytest.raises(AdminError, match="future"): validate_notices({"version": 1, "events": [event]}, now)


def test_identification_validation_and_duplicate(portal):
    master = {"entries": []}; registry = registry_row(portal)
    assert validate_registry(registry, portal, master)[0]["identified_name"] == "ベニタケ"
    registry["identifications"].append(dict(registry["identifications"][0]))
    with pytest.raises(ResearchIdentificationError, match="duplicate identification_id"):
        validate_registry(registry, portal, master)


def test_unknown_master_is_allowed_but_invalid_link_is_not(portal):
    row = registry_row(portal); assert validate_registry(row, portal, {"entries": []})
    row["identifications"][0]["mushroom_master_id"] = "invented"
    with pytest.raises(ResearchIdentificationError, match="does not exist"):
        validate_registry(row, portal, {"entries": []})


def test_reopen_keeps_audit_record(monkeypatch, portal):
    draft = ChangeSet.__new__(ChangeSet); draft.portal=portal; draft.master={"entries": []}
    draft.identifications=registry_row(portal)
    draft.reopen("ident-1")
    assert draft.identifications["identifications"][0]["status"] == "reopened"


def test_identify_explicitly_adds_notice(portal):
    draft = ChangeSet.__new__(ChangeSet); draft.portal=portal; draft.master={"entries": []}
    draft.identifications={"version":1,"identifications":[]}; draft.notices={"version":1,"events":[]}
    draft.identify(build_research_cases(portal)[0], "ベニタケ")
    assert draft.notices["events"][0]["kind"] == "identified"


def test_subprocess_requires_list_and_branch_ignores_user_input():
    with pytest.raises(GitWorkflowError): run("git status")
    name = safe_branch_name("x; rm -rf /")
    assert ";" not in name and name.startswith("admin/")


def test_pr_safe_failure_without_gh(monkeypatch):
    monkeypatch.setattr("admin.git_workflow.repository_status", lambda: {"gh_authenticated": False})
    with pytest.raises(GitWorkflowError, match="GitHub認証"):
        create_pull_request({}, {}, "test")


def test_public_isolation_and_workflow():
    root = Path(__file__).parents[1]
    assert not (root / "output" / "admin").exists()
    workflow = (root / ".github/workflows/admin-validate.yml").read_text()
    assert "JamesIves" not in workflow and "deploy" not in workflow.lower()
    generate = (root / ".github/workflows/generate.yml").read_text()
    assert "admin" not in generate.lower()


def test_static_ui_does_not_embed_secrets():
    root = Path(__file__).parents[1] / "admin/static"
    text = "".join(p.read_text() for p in root.iterdir())
    assert "GH_TOKEN" not in text and "HATENA_API_KEY" not in text
    assert "textContent" in (root / "admin.js").read_text()
