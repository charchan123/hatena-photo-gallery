"""Read-only comparison of the pinned public portal and this display candidate."""
import csv
import json
from pathlib import Path
from subprocess import check_output
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from detail_ui import build_detail_views, render_detail_sections

MAIN = "69b73ec7f2b0df0a151464351dba92e441511e49"
PAGES = "250bc700bc74710a8d40dbc325f6d9229077325b"
PREVIOUS = "4d12205a98e640448b17883e4e89f1ab64a9fd50"
DISPLAY = "data/taxonomy-display-ja.json"
LABELS = {"family": "科名", "genus": "属名", "ecology": "生態", "habitat": "生育環境"}


def git(*args):
    return check_output(["git", "-C", str(ROOT), *args])


def read(revision, path):
    return json.loads(git("show", f"{revision}:{path}"))


def rows(knowledge):
    return {x["label"]: x for x in knowledge["rows"]}


portal = read(PAGES, "portal-data.json")
assert portal == read(PREVIOUS, "portal-data.json")
assert git("diff", "--name-only", PREVIOUS, PAGES).decode().splitlines() == [
    "article-sync-snapshot.json", "article-sync-status.json"]
summary = portal["summary"]
assert [summary[key] for key in (
    "observation_count", "subject_count", "master_linked_subject_count",
    "knowledge_record_count", "source_count")] == [935, 313, 105, 161, 453]
assert len(read(MAIN, "data/best-shots.json")["entries"]) == 17
assert len(read(PAGES, "research-comment-cases.json")["active_ids"]) == 66
assert [len(portal["reference_data"][group][key]) for group, key in (
    ("mushroom_master", "entries"), ("guide_expansion", "entries"),
    ("sources", "sources"), ("guide_expansion", "sources"))] == [141, 20, 419, 34]

before_spec = read(MAIN, DISPLAY)
after_spec = json.loads((ROOT / DISPLAY).read_text(encoding="utf-8"))
assert all(after_spec["sources"][k] == v for k, v in before_spec["sources"].items())
assert len(before_spec["sources"]) == 76 and len(after_spec["sources"]) == 102
for ident, record in before_spec["entries"].items():
    new_record = after_spec["entries"][ident]
    assert record["expected"] == new_record["expected"]
    assert all(new_record["fields"][k] == v for k, v in record["fields"].items())

with (HERE / "field-evidence.csv").open(encoding="utf-8", newline="") as handle:
    audit = list(csv.DictReader(handle))
approved = {(r["掲載名"], LABELS[r["欄"]]): r for r in audit}
assert len(approved) == len(audit) == 31
with tempfile.TemporaryDirectory() as folder:
    old_path = Path(folder) / "before.json"
    old_path.write_bytes(git("show", f"{MAIN}:{DISPLAY}"))
    before = build_detail_views(portal, taxonomy_display_path=old_path)
after = build_detail_views(portal)
actual = {}
for name, old in before.items():
    new = after[name]
    if not old["knowledge"]:
        assert new == old
        continue
    assert {k: v for k, v in old.items() if k != "knowledge"} == {
        k: v for k, v in new.items() if k != "knowledge"}
    new_src = {r["url"] for r in new["knowledge"]["sources"]}
    assert all(r["url"] in new_src for r in old["knowledge"]["sources"])
    previous, changed = rows(old["knowledge"]), rows(new["knowledge"])
    for label in previous.keys() | changed.keys():
        if previous.get(label) != changed.get(label):
            actual[name, label] = changed[label]["value"]
            claim = approved[name, label]
            assert all(u in new_src for u in claim["URL"].split(" | "))
    if not any(row["掲載名"] == name for row in audit):
        assert render_detail_sections(old) == render_detail_sections(new)
assert actual == {k: r["候補表示"] for k, r in approved.items()}
tracked = git("diff", "--name-only", MAIN).decode().splitlines()
assert all(f in {DISPLAY, "tests/browser/comments_integration_protection.py"}
           or f.startswith("audit/guide-105-enrichment-20261128/") for f in tracked)
print("PASS: 105 published views, 31 claimed additions, food warnings and old sources, protected paths")
