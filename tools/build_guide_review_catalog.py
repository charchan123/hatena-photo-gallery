"""Normalize the reviewed PR #185 snapshot for the local admin console."""
import argparse
import csv
import json
from pathlib import Path
import subprocess

AUDIT_HEAD = "b7961a0633288e940add911051da509e689c93a7"
ROOT = Path(__file__).resolve().parents[1]


def rows(directory, name):
    with (directory / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build(directory):
    script = (directory / "preview/data.js").read_text(encoding="utf-8").strip()
    if not script.startswith("const AUDIT = ") or not script.endswith(";"):
        raise ValueError("予期しない監査データ形式")
    preview = json.loads(script.removeprefix("const AUDIT = ").removesuffix(";"))
    inventory = {row["掲載名"]: row for row in
                 rows(directory, "review-125.csv") + rows(directory, "related-item.csv")}
    photos = {row["観測ID"]: row for row in rows(directory, "photo-review-195.csv")}
    manuscript = {row["掲載名"]: row for row in rows(directory, "manuscript-index.csv")}
    source_index = rows(directory, "prior-source-index.csv")
    portal = json.loads(subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{preview['pages']}:portal-data.json"]))
    active = {row["observation_id"]: row for row in portal["observations"]}
    items = []
    for item in preview["items"]:
        name = item["name"]
        row = inventory[name]
        assert item["group"] == row["確認区分"] and len(item["photos"]) == int(row["写真枚数"])
        material = manuscript[name]
        draft = item["draft"]
        source_rows = [r for r in source_index if r["掲載名"] == name]
        assert set(["資料掲載学名", "科", "属", "特徴", "生育環境", "発生時期", "生態", "食毒"]) <= material.keys()
        evidence = []
        for photo in item["photos"]:
            source = photos.get(photo["id"], {})
            article = active[photo["id"]]["article"]
            if item["scope"]:
                assert photo["fingerprint"] == source["確認用SHA-256"]
                assert photo["src"] == source["画像URL"] and photo["article"] == source["記事URL"]
            evidence.append({**photo, "article_id": article["article_id"],
                             "article_revision": article.get("updated") or article.get("published") or "",
                             "block": source.get("記事本文ブロック", ""),
                             "caption": source.get("同一画像のキャプション", ""),
                             "history": source.get("過去承認", "")})
        fields = {key: material[key] for key in ("資料掲載学名", "科", "属", "特徴", "生育環境", "発生時期", "生態", "食毒")}
        items.append({**item, "photos": evidence,
                      "legacy_scope": [photo["id"] for photo in evidence] if name == "センニンタケ" else [],
                      "priority_candidate":
                      (item["group"] == "B" and row["前回状態"] == "現行v1検証済み・未決") or name == "センニンタケ",
                      "draft": {"preview": draft, "fields": fields,
                                "reference": material["資料参照"], "status": material["現在の扱い"],
                                "notes": material["保留・根拠の詳細"], "sources": source_rows}})
    assert len(items) == len(inventory) == 126 and sum(item["scope"] for item in items) == 125
    assert sum(len(item["photos"]) for item in items if item["scope"]) == len(photos) == 195
    assert sum(item["priority_candidate"] for item in items) == 65
    return {"version": 1, "basis": f"PR #185 · {AUDIT_HEAD}", "pages": preview["pages"], "items": items}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", type=Path)
    args = parser.parse_args()
    (ROOT / "admin/guide-review/catalog.json").write_text(
        json.dumps(build(args.audit), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
