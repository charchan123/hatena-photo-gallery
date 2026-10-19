"""Best Shot API regression checks; every mutation uses an isolated memory fixture."""
from copy import deepcopy
import json
import threading
import urllib.error
import urllib.request

import pytest

from admin.core import ChangeSet
from admin.draft_store import DraftStore
from admin.server import AdminServer, Handler
from best_shot_ui import BestShotConfigError, validate_best_shot_config


def observation(i, date="2026-10-01"):
    return {"observation_id": f"obs-{i}", "gallery_name": "ベニテングタケ",
            "src": f"https://example.test/{i}.jpg", "capture": {"date": date},
            "article": {"title": f"観察記録 {i}"}}


def entry(i, order=1):
    return {"selection_id": f"best-{i}", "observation_id": f"obs-{i}",
            "comment": "本人が選んだ一枚", "order": order}


def draft_fixture():
    draft = ChangeSet.__new__(ChangeSet)
    draft.portal = {"version": 1, "observations": [observation(i) for i in range(1, 6)] + [observation(6, None), observation(7, "2025-10-01")]}
    draft.best_shots = {"version": 1, "entries": [], "annual_best": {}}
    draft.notices = {"version": 1, "events": []}
    draft.identifications = {"version": 1, "identifications": []}
    return draft


@pytest.fixture
def api(monkeypatch, tmp_path):
    draft = draft_fixture()
    monkeypatch.setattr("admin.server.load_portal_data", lambda: (draft.portal, "isolated fixture"))
    monkeypatch.setattr("admin.server.ChangeSet", lambda portal: draft)
    monkeypatch.setattr("admin.server.DraftStore", lambda: DraftStore(tmp_path))
    monkeypatch.setattr("admin.server.SyncReview", lambda: object())
    server = AdminServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def post(path, body):
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}" + path,
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-CSRF-Token": server.csrf_token})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    try:
        yield post, draft
    finally:
        server.shutdown(); server.server_close(); thread.join()


@pytest.mark.parametrize("bad", [0, -1, 1.5, "", None, True, "2", 2.0, []])
@pytest.mark.parametrize("operation", ["add", "update"])
def test_direct_api_order_rejection_preserves_draft(api, bad, operation):
    post, draft = api
    if operation == "update": draft.best_shots["entries"] = [entry(1)]
    before = deepcopy((draft.best_shots, draft.notices))
    body = {"entry": entry(2, bad)} if operation == "add" else {"selection_id": "best-1", "changes": {"order": bad}}
    status, result = post("/api/best-shot/" + operation, body)
    assert status == 400
    assert result["field_errors"] == {"order": "1以上の整数を入力してください"}
    assert (draft.best_shots, draft.notices) == before


def test_duplicate_month_is_japanese_and_correction_succeeds(api):
    post, draft = api
    assert post("/api/best-shot/add", {"entry": entry(1)})[0] == 200
    before = deepcopy(draft.best_shots)
    status, result = post("/api/best-shot/add", {"entry": entry(2)})
    assert status == 400 and "順序「1」" in result["field_errors"]["order"]
    assert "2026年10月" in result["field_errors"]["order"]
    assert draft.best_shots == before
    assert post("/api/best-shot/add", {"entry": entry(2, 2)})[0] == 200
    assert post("/api/best-shot/update", {"selection_id": "best-1", "changes": {"order": 1}})[0] == 200  # Self excluded.
    status, result = post("/api/best-shot/update", {"selection_id": "best-1", "changes": {"order": 2}})
    assert status == 400 and "順序「2」" in result["field_errors"]["order"]


def test_fourth_photo_allowed_duplicate_photo_and_missing_date(api):
    post, draft = api
    for i in (1, 2, 3): assert post("/api/best-shot/add", {"entry": entry(i, i)})[0] == 200
    assert post("/api/best-shot/add", {"entry": entry(4, 4)})[0] == 200
    before = deepcopy(draft.best_shots)
    status, result = post("/api/best-shot/add", {"entry": entry(1) | {"selection_id": "other"}})
    assert status == 400 and "すでにBest Shot" in result["field_errors"]["observation_id"]
    status, result = post("/api/best-shot/add", {"entry": entry(6)})
    assert status == 400 and "撮影日" in result["field_errors"]["observation_id"]
    assert draft.best_shots == before


@pytest.mark.parametrize("comment", ["", " " * 3, "き" * 201])
def test_comment_field_errors(api, comment):
    post, draft = api
    status, result = post("/api/best-shot/add", {"entry": entry(1) | {"comment": comment}})
    assert status == 400 and result["field_errors"]["comment"]
    assert draft.best_shots["entries"] == []


def test_failed_notice_does_not_partially_add_best_shot(api):
    post, draft = api
    before = deepcopy((draft.best_shots, draft.notices))
    status, result = post("/api/best-shot/add", {"entry": entry(1), "add_notice": True, "occurred_at": "2099-01-01T00:00:00+00:00"})
    assert status == 400 and result["message"]
    assert (draft.best_shots, draft.notices) == before
    assert post("/api/best-shot/add", {"entry": entry(1), "add_notice": True})[0] == 200
    assert len(draft.best_shots["entries"]) == len(draft.notices["events"]) == 1


def test_noop_edit_preserves_optional_fields_and_annual(api):
    post, draft = api
    draft.best_shots = {"version": 1, "entries": [entry(1) | {"annual_comment": "年間のコメント", "location": "静岡"}], "annual_best": {"2026": "best-1"}}
    before = deepcopy(draft.best_shots)
    assert post("/api/best-shot/update", {"selection_id": "best-1", "changes": {}})[0] == 200
    assert draft.best_shots == before
    status, result = post("/api/best-shot/update", {"selection_id": "best-1", "changes": {"observation_id": "obs-7"}})
    assert status == 400 and "年間ベスト" in result["field_errors"]["observation_id"]
    assert draft.best_shots == before


@pytest.mark.parametrize("n", [1, 2, 3, 4, 10, 30, 999])
def test_shared_validator_accepts_positive_orders_without_month_cap(n):
    draft = draft_fixture()
    assert validate_best_shot_config({"version": 1, "entries": [entry(1, n)]}, draft.portal)[0]["order"] == n


@pytest.mark.parametrize("count", [1, 3, 4, 10, 30, 35])
def test_api_many_monthly_adds_edits_replacements_deletes_and_annual(api, count):
    post, draft = api
    draft.portal["observations"] = [observation(i) for i in range(1, count + 4)] + [observation(100, "2026-09-01")]
    for i in range(1, count + 1):
        assert post("/api/best-shot/add", {"entry": entry(i, i) | {"location": "静岡", "annual_comment": "年間メモ"}})[0] == 200
    assert len(draft.best_shots["entries"]) == count
    assert post("/api/best-shot/annual", {"year": "2026", "selection_id": "best-1"})[0] == 200
    original = deepcopy(draft.best_shots)
    # A genuine duplicate still fails, even after the former monthly cap is exceeded.
    status, result = post("/api/best-shot/add", {"entry": entry(count + 1, count)})
    assert status == 400 and result["error"] == "order must be unique within a year and month"
    assert draft.best_shots == original
    assert post("/api/best-shot/update", {"selection_id": "best-1", "changes": {"order": count + 10}})[0] == 200
    assert post("/api/best-shot/update", {"selection_id": "best-1", "changes": {"observation_id": f"obs-{count + 1}"}})[0] == 200
    # Moving into a different capture month keeps the selection/annual IDs and comments.
    assert post("/api/best-shot/update", {"selection_id": "best-1", "changes": {"observation_id": "obs-100", "order": 1}})[0] == 200
    selected = draft.best_shots["entries"][0]
    assert selected == original["entries"][0] | {"observation_id": "obs-100", "order": 1}
    assert draft.best_shots["annual_best"] == {"2026": "best-1"}
    if count > 1:
        assert post("/api/best-shot/delete", {"selection_id": f"best-{count}"})[0] == 200
        assert draft.best_shots["annual_best"] == {"2026": "best-1"}
    assert post("/api/best-shot/delete", {"selection_id": "best-1"})[0] == 200
    assert draft.best_shots["annual_best"] == {}

def test_failed_atomic_save_rolls_back_compound_best_shot_and_notice(api, monkeypatch):
    post, draft = api
    before = deepcopy(draft.files())
    monkeypatch.setattr("admin.draft_store.os.replace",
                        lambda *args: (_ for _ in ()).throw(OSError("simulated disk failure")))
    code, message = post("/api/best-shot/add", {"entry": entry(1), "add_notice": True})
    assert code == 400
    assert "error" in message
    assert draft.files() == before
