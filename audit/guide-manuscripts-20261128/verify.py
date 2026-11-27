"""Validate the audit package against the unchanged published and review snapshots."""
import csv
import hashlib
import json
from pathlib import Path
from subprocess import check_output
import unicodedata
from urllib.parse import urlsplit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUMMARY = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
PROVENANCE = "audit/guide-review-125-20261126/"
COUNTS = {"priority65": 65, "other24": 24, "partial2": 2}
PENDING = dict.fromkeys(("photo_name", "manuscript", "food", "features_search", "publication"),
                        "human_review_pending")


def git(*args):
    return check_output(["git", "-C", str(ROOT), *args])


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def name_key(value):
    return " ".join(unicodedata.normalize("NFKC", value).split())


portal = json.loads(git("show", f"{SUMMARY['pages']}:portal-data.json"))
assert [portal["summary"][key] for key in (
    "observation_count", "subject_count", "master_linked_subject_count",
    "knowledge_record_count", "source_count")] == [935, 313, 105, 161, 453]
assert len(json.loads(git("show", f"{SUMMARY['main']}:data/best-shots.json"))["entries"]) == 17
assert len(json.loads(git("show", f"{SUMMARY['pages']}:research-comment-cases.json"))["active_ids"]) == 66
assert len(json.loads(git("show", f"{SUMMARY['main']}:data/taxonomy-display-ja.json"))["sources"]) == 76
current = {r["gallery_name"]: r for r in portal["subjects"]}
published_photos = {r["observation_id"]: r for r in portal["observations"]}
catalog = json.loads(git("show", f"{SUMMARY['pr186']}:admin/guide-review/catalog.json"))
assert catalog["basis"] == f"PR #185 · {SUMMARY['pr185']}"
review = list(csv.DictReader(git("show", f"{SUMMARY['pr185']}:{PROVENANCE}review-125.csv")
                           .decode().splitlines()))
by_name = {r["name"]: r for r in catalog["items"]}
expected = {r["掲載名"] for r in review if r["確認区分"] == "B"
            and r["前回状態"] == "現行v1検証済み・未決"} | {"センニンタケ"}
assert expected == {r["name"] for r in catalog["items"] if r["priority_candidate"]}
other = {r["掲載名"] for r in review if r["解説原稿の再審査候補"] == "あり"} - expected
assert len(expected) == 65 and len(other) == 24

master_records = [m for group in ("mushroom_master", "guide_expansion")
                  for m in portal["reference_data"][group]["entries"]]
reserved_ids = {m["mushroom_id"] for m in master_records}
reserved_names = {name_key(alias) for m in master_records
                  for alias in [m["canonical_name_ja"], *m.get("aliases_ja", [])]}
with (HERE / "source-index.csv").open(encoding="utf-8", newline="") as handle:
    sources = {s["出典ID"]: s for s in csv.DictReader(handle)}
with (HERE / "field-matrix-91.csv").open(encoding="utf-8", newline="") as handle:
    matrix = {r["掲載名"]: r for r in csv.DictReader(handle)}
assert len(sources) == SUMMARY["source_ids"] and len(matrix) == 91
for row in sources.values():
    address = urlsplit(row["URL"])
    assert address.scheme in {"http", "https"} and address.hostname
    assert not address.username and not address.password
seen = set()
seen_ids = set()
seen_master_ids = set()
for group, size in COUNTS.items():
    path = HERE / (group + ".jsonl")
    data = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    group_name = {r["gallery_name"] for r in data}
    assert len(data) == len(group_name) == size
    assert not seen.intersection(group_name)
    seen.update(group_name)
    assert group_name == {"priority65": expected, "other24": other,
                          "partial2": {"キノボリイグチ", "ウツロベニハナイグチ"}}[group]
    for r in data:
        name = r["gallery_name"]
        assert r["scope"] == group
        assert not current[name]["mushroom_master_id"] and not current[name]["knowledge_available"]
        assert r["catalog_key_sha256"] == hashlib.sha256(name.encode()).hexdigest()
        assert r["catalog_item_sha256"] == sha(by_name[name])
        assert current[name]["photo_count"] == len(by_name[name]["photos"])
        for p in by_name[name]["photos"]:
            current_photo = published_photos[p["id"]]
            assert (current_photo["gallery_name"], current_photo["src"], current_photo["article"]["article_id"]) == (
                name, p["src"], p["article_id"])
        assert r["approval_requirements"] == PENDING
        assert r["candidate_id"] not in seen_ids and not r["identity_collisions"]
        seen_ids.add(r["candidate_id"])
        if (proposed := r["proposed_master_id"]) is not None:
            assert proposed not in reserved_ids | seen_master_ids
            seen_master_ids.add(proposed)
        assert name_key(name) not in reserved_names
        fields = r["fields"]
        assert fields["food"]["value"] == "未確認" and not fields["food"]["source_ids"]
        for key, data in fields.items():
            if key not in {"food", "caution"}:
                assert not any(s in data["value"] for s in ("食べ", "中毒", "有毒", "無毒", "毒性", "食用"))
                assert data["source_ids"] and set(data["source_ids"]) <= set(r["source_ids"])
                assert data.get("source_location")
        assert set(r["source_ids"]) <= sources.keys()
        revision = r.pop("revision_sha256")
        assert revision == matrix[name]["改訂SHA-256"] == sha(r)
assert set(seen) == matrix.keys()
with (HERE / "remaining-34.csv").open(encoding="utf-8", newline="") as handle:
    backlog = list(csv.DictReader(handle))
backlog_names = {r["掲載名"] for r in backlog}
assert len(backlog_names) == len(backlog) == SUMMARY["remaining_without_package"] == 34
assert backlog_names == {r["掲載名"] for r in review} - seen
assert len(by_name["センニンタケ"]["legacy_scope"]) == 3
assert all(f.startswith("audit/guide-manuscripts-20261128/") for f in
           git("diff", "--name-only", SUMMARY["main"]).decode().splitlines())
print("PASS: 65 exact priority matches, other 24, 2 partial records, 91 revisions, 34 backlog items and five pending decisions")
