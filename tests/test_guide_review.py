from copy import deepcopy
from io import BytesIO
import json
import sqlite3
import threading

from PIL import Image
import pytest

from admin.guide_review import GuideReview, ReviewError, _fingerprint, item_id


NAME = "センニンタケ"


def image(color="green"):
    output = BytesIO()
    Image.new("RGB", (16, 12), color).save(output, format="PNG")
    return output.getvalue(), "image/png"


def observation(number, name=NAME):
    return {"observation_id": f"obs-{number:064x}", "gallery_name": name,
            "src": f"https://cdn-ak.f.st-hatena.com/{number}.png", "capture": {"date": "2025-11-01"},
            "article": {"article_id": f"article-{number}", "url": f"https://exsudoporus-ruber.hatenablog.jp/entry/{number}", "updated": "2025-11-01"},
            "classification": {"status": "legacy_review"}}


@pytest.fixture
def setup(tmp_path):
    portal = {"version": 1, "observations": [observation(n) for n in range(3)] + [observation(4, "別項目")]}
    data = {row["src"]: image() for row in portal["observations"]}
    draft = {"fields": {"特徴": "試験用原稿", "食毒": "安全性資料の該当記録"}, "sources": [],
             "preview": {"sources": []}}
    photos = [{"id": row["observation_id"], "src": row["src"], "article": row["article"]["url"],
               "date": row["capture"]["date"], "status": row["classification"]["status"],
               "article_id": row["article"]["article_id"]} for row in portal["observations"][:3]]
    common = {"reason": "", "question": "目視してください", "priority": 1, "priority_candidate": True, "scope": True}
    catalog = {"version": 1, "items": [
        {**common, "name": NAME, "group": "A", "photos": photos, "legacy_scope": [p["id"] for p in photos], "draft": draft},
        {**common, "name": "別項目", "group": "B", "photos": [], "draft": draft},
    ]}
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    review = GuideReview(tmp_path, lambda: deepcopy(portal), lambda url: data[url], path)
    review.refresh()
    return review, portal, data, catalog


def operation(review, *, item=NAME, kind="name", decision="confirmed", scope="all", photos=None, load=True, ack=True):
    key = item_id(item)
    state = review.state(key)
    ids = photos if photos is not None else [p["identity"]["id"] for p in state["item"]["photos"]]
    tickets = {photo: review.photo(key, photo)[2] for photo in ids} if kind == "name" and load and decision == "confirmed" else {}
    return {"revision": state["revision"], "item": key, "kind": kind, "decision": decision, "scope": scope,
            "photos": ids, "tickets": tickets, "reviewer": "確認者", "note": "根拠のメモ", "ack": ack}


def status(review, name=NAME):
    return review.state(item_id(name))["item"]["status"]


def test_image_and_explicit_confirmation_are_both_required(setup):
    review, _, _, _ = setup
    with pytest.raises(ReviewError, match="確認操作"):
        review.change(operation(review, load=False))
    with pytest.raises(ReviewError, match="確認操作"):
        review.change(operation(review, ack=False))
    body = operation(review)
    body["tickets"][body["photos"][0]] = "forged"
    with pytest.raises(ReviewError, match="再読み込み"):
        review.change(body)
    assert review.records() == []
    review.change(operation(review))
    assert status(review) == "confirmed"


def test_replacement_between_view_and_save_is_rejected(setup):
    review, _, data, _ = setup
    body = operation(review)
    data[next(iter(data))] = image("red")
    with pytest.raises(ReviewError, match="画像が更新"):
        review.change(body)
    assert not review.records()


@pytest.mark.parametrize("change", ["add", "remove", "image", "article"])
def test_freshness_is_item_specific(setup, change):
    review, portal, data, _ = setup
    for name in (NAME, "別項目"):
        review.change(operation(review, item=name))
    if change == "add":
        portal["observations"].append(observation(6))
    if change == "remove":
        portal["observations"].pop(0)
    if change == "article":
        portal["observations"][0]["article"]["updated"] = "2026-01-01"
    if change == "image":
        url = portal["observations"][0]["src"]
        data[url] = image("red")
        review.photo(item_id(NAME), portal["observations"][0]["observation_id"])
    review.refresh()
    assert status(review) == "recheck"
    assert status(review, "別項目") == "confirmed"


def test_legacy_scope_is_three_and_does_not_cover_new_photo(setup):
    review, portal, data, _ = setup
    ids = [p["observation_id"] for p in portal["observations"][:3]]
    portal["observations"].append(observation(5))
    data[portal["observations"][-1]["src"]] = image()
    review.refresh()
    assert status(review) == "pending"
    with pytest.raises(ReviewError, match="範囲"):
        review.change(operation(review, scope="legacy", photos=ids[:2]))
    review.change(operation(review, scope="legacy", photos=ids))
    assert status(review) == "individual"
    assert set(review.records()[0]["image_hashes"]) == set(ids)


def test_independent_approvals_and_source_revision(setup):
    review, _, _, cat = setup
    review.change(operation(review))
    review.change(operation(review, kind="manuscript", scope="editorial", photos=[]))
    item = review.state(item_id(NAME))["item"]
    assert item["editorial"] == {"manuscript": "confirmed", "food": "pending", "features": "pending"}
    assert item["publication"] == "locked"
    cat["items"][0]["draft"]["sources"] = [{"URL": "https://example.org/revised"}]
    review.catalog.write_text(json.dumps(cat), encoding="utf-8")
    review.refresh()
    assert review.state(item_id(NAME))["item"]["editorial"]["manuscript"] == "stale"
    assert status(review) == "confirmed"


def test_history_correction_and_restart(setup, tmp_path):
    review, portal, data, _ = setup
    review.change(operation(review))
    restarted = GuideReview(tmp_path, lambda: deepcopy(portal), lambda url: data[url], review.catalog)
    assert status(restarted) == "recheck"
    for photo in portal["observations"][:3]:
        restarted.photo(item_id(NAME), photo["observation_id"])
    assert status(restarted) == "confirmed"
    restarted.change(operation(restarted, decision="reset"))
    assert status(restarted) == "pending"
    assert [r["decision"] for r in restarted.records()] == ["confirmed", "reset"]


def test_restore_keeps_unverified_history_and_rejects_bad_records(setup, tmp_path):
    review, portal, data, _ = setup
    review.change(operation(review))
    before = review.snapshot(review.records())
    restored = GuideReview(tmp_path / "restored", lambda: deepcopy(portal), lambda url: data[url], review.catalog)
    for key, value in [("target", "wrong"), ("revision", 0), ("checksum", "wrong")]:
        with pytest.raises(ReviewError):
            restored.change({"revision": 0, "backup": before | {key: value}}, restore=True)
    bad = deepcopy(before)
    bad["events"][0]["photos"][0]["url"] = "http://127.0.0.1"
    bad["checksum"] = _fingerprint({k: v for k, v in bad.items() if k != "checksum"})
    with pytest.raises(ReviewError, match="識別"):
        restored.change({"revision": 0, "backup": bad}, restore=True)
    assert restored.change({"revision": 0, "backup": before}, restore=True)["saved"] == 1
    for row in portal["observations"][:3]:
        restored.photo(item_id(NAME), row["observation_id"])
    assert status(restored) == "recheck"
    restored.change(operation(restored))
    assert status(restored) == "confirmed"


def test_competing_servers_cannot_overwrite(setup, tmp_path):
    first, portal, data, _ = setup
    second = GuideReview(tmp_path, lambda: deepcopy(portal), lambda url: data[url], first.catalog)
    ops = [(service, operation(service, decision="held")) for service in [first, second]]
    barrier = threading.Barrier(2)
    results = []

    def save(service, body):
        barrier.wait(timeout=5)
        try:
            results.append(service.change(body)["saved"])
        except ReviewError:
            results.append("conflict")

    threads = [threading.Thread(target=save, args=pair) for pair in ops]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert sorted(results, key=str) == [1, "conflict"]
    assert len(first.records()) == 1


def test_corrupt_database_is_preserved(setup):
    review, _, _, _ = setup
    review.path.parent.mkdir(parents=True)
    review.path.write_bytes(b"broken backup content")
    with pytest.raises(sqlite3.DatabaseError):
        review.records()
    assert review.path.read_bytes() == b"broken backup content"
