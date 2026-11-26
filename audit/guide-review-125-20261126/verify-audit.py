"""Verify the review joins and compare the two immutable published revisions."""
from collections import Counter
import csv
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
MAIN = "69b73ec7f2b0df0a151464351dba92e441511e49"
PREVIOUS = "0e2d9907933f2c00efcf0775a75f3983edabc15a"
PAGES = "4d12205a98e640448b17883e4e89f1ab64a9fd50"
ALLOWED_EXTERNAL_PATH = ".github/workflows/guide-review-125.yml"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def at(revision, path):
    return json.loads(git("show", f"{revision}:{path}"))


def read_csv(path):
    with (AUDIT / path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def assert_public_release():
    files = git("diff", "--name-status", PREVIOUS, PAGES).decode().splitlines()
    assert files == ["M\tarticle-sync-snapshot.json", "M\tarticle-sync-status.json"]
    assert MAIN in git("log", "-1", "--format=%B", PAGES).decode()
    for path, ignored_keys in [
        ("article-sync-snapshot.json", {"last_success_at", "deletion_history_head"}),
        ("article-sync-status.json", {"last_success_at"}),
    ]:
        left, right = at(PREVIOUS, path), at(PAGES, path)
        if path.endswith("snapshot.json"):
            left, right = left["payload"], right["payload"]
        else:
            left["deletions"].pop("history_head")
            right["deletions"].pop("history_head")
        assert {k: v for k, v in left.items() if k not in ignored_keys} == {
            k: v for k, v in right.items() if k not in ignored_keys
        }

    portal = at(PAGES, "portal-data.json")
    assert portal["summary"]["master_linked_subject_count"] == 105
    assert portal["summary"]["master_unlinked_subject_count"] == 208
    assert len(portal["observations"]) == 935
    assert len(portal["subjects"]) == 313
    ref = portal["reference_data"]
    assert len(ref["mushroom_master"]["entries"]) == 141
    assert len(ref["guide_expansion"]["entries"]) == 20
    assert len(ref["sources"]["sources"]) == 419
    assert len(ref["guide_expansion"]["sources"]) == 34
    assert len(at(MAIN, "data/taxonomy-display-ja.json")["sources"]) == 76
    assert len(at(MAIN, "data/best-shots.json")["entries"]) == 17
    assert len(at(PAGES, "research-comment-cases.json")["active_ids"]) == 66

    sys.path.insert(0, str(ROOT))
    from detail_ui import build_detail_views

    rows = [
        {field["label"]: field["value"] for field in view["knowledge"]["rows"]}
        for view in build_detail_views(portal).values() if view["knowledge"]
    ]
    assert len(rows) == 105
    assert sum(row["科名"] != "確認中" for row in rows) == 99
    assert sum(row["属名"] != "確認中" for row in rows) == 96
    assert sum(row["生態"] != "未確認" for row in rows) == 34
    return portal


def assert_inventory(portal):
    review = read_csv("review-125.csv")
    related = read_csv("related-item.csv")
    photos = read_csv("photo-review-195.csv")
    prior = read_csv("manuscript-index.csv")
    summary = json.loads((AUDIT / "summary.json").read_text(encoding="utf-8"))
    script = (AUDIT / "preview" / "data.js").read_text(encoding="utf-8").strip()
    preview = json.loads(script.removeprefix("const AUDIT = ").removesuffix(";"))
    assert preview["main"] == MAIN and preview["pages"] == PAGES
    assert len(review) == 125 and len(related) == 1 and len(photos) == 195
    assert len(prior) == 126 and len(preview["items"]) == 126
    assert len({item["name"] for item in preview["items"]}) == 126
    assert sum(item["scope"] for item in preview["items"]) == 125
    assert len({row["掲載名"] for row in review}) == 125
    assert len({row["観測ID"] for row in photos}) == 195
    assert sum(row["先行調査履歴"] == "あり" for row in review) == 124
    assert sum(row["解説原稿の再審査候補"] == "あり" for row in review) == 89
    assert Counter(row["確認区分"] for row in review) == summary["items"]
    assert Counter(row["記事と画像の確認"] for row in photos) == summary["article_photo_evidence"]
    subjects = {row["gallery_name"]: row for row in portal["subjects"]}
    observed = {row["observation_id"]: row for row in portal["observations"]}
    provenance = {row["記事URL"] for row in read_csv("article-provenance.csv")}
    evidence_by_id = {row["観測ID"]: row for row in photos}
    for row in photos:
        original = observed[row["観測ID"]]
        assert row["掲載名"] == original["gallery_name"]
        assert row["画像URL"] == original["src"]
        assert row["記事URL"] == original["article"]["url"] and row["記事URL"] in provenance
        assert row["記事ID"] == original["article"]["article_id"]
        assert row["撮影日"] == (original["capture"]["date"] or "")
        assert row["現在の分類"] == original["classification"]["status"]
        assert row["記事本文ブロック"] and re.fullmatch(r"[0-9a-f]{64}", row["確認用SHA-256"])
    item_review = {row["掲載名"]: row for row in review + related}
    for item in preview["items"]:
        s = subjects[item["name"]]
        assert s["knowledge_available"] is False and s["mushroom_master_id"] is None
        assert item["question"] == item_review[item["name"]]["撮影者への確認"]
        assert item["group"] == item_review[item["name"]]["確認区分"]
        assert len(item["photos"]) == s["photo_count"]
        assert {photo["id"] for photo in item["photos"]} == {
            row["observation_id"] for row in portal["observations"] if row["gallery_name"] == item["name"]
        }
        for photo in item["photos"]:
            assert photo["src"] == observed[photo["id"]]["src"]
            assert photo["article"] == observed[photo["id"]]["article"]["url"]
            if item["scope"]:
                assert photo["fingerprint"] == evidence_by_id[photo["id"]]["確認用SHA-256"]
    assert len(provenance) == 50


def assert_protection():
    diff = git("diff", "--name-status", MAIN, "HEAD").decode().splitlines()
    for change in diff:
        kind, path = change.split("\t")
        assert kind == "A", change
        assert path == ALLOWED_EXTERNAL_PATH or path.startswith("audit/" + AUDIT.name + "/"), change
    print(f"Protected paths: 0 changes; audit-only additions: {len(diff)}")


if __name__ == "__main__":
    assert_inventory(assert_public_release())
    assert_protection()
    print("PASS: 125 items, 195 observations, one separate related item, 50 articles, and 105 protected public entries.")
