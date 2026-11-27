"""Synthetic read-only comment rows for the local Windows/Android trial."""
from .comment_photos import entries

STAMP = "2026-11-27T10:00:00+09:00"


def fixtures(portal):
    bound = entries(portal)
    available = [(key, value) for key, value in bound.items() if value["photo_status"] == "matched"]
    multi = next(row for row in available if row[1]["photo_count"] > 1)
    single = next(row for row in available if row[1]["photo_count"] == 1)
    other = next(row for row in available if row[0] not in {multi[0], single[0]})
    cases, comments = [], {}
    for index, (key, photos, title, count, unread, reports) in enumerate([
        (multi[0], multi[1], "試験・不明キノコ", 3, 2, 1),
        (single[0], single[1], "試験・不明キノコ", 1, 0, 0),
        (other[0], other[1], "試験・コメントなし", 0, 0, 0),
        ("research-ffffffffffffffff", {"photos": [], "photo_status": "unavailable", "phase": "archived"}, "試験・写真未照合", 1, 1, 0),
    ]):
        if index == 1:
            photos = {**photos, "phase": "identified"}
        cases.append({"id": key, "label": title, "total": count, "unread": unread, "reports": reports, "media": photos})
        comments[key] = [dict(id=f"sample-{index}-{n}", state="hidden" if n == 2 else "visible",
                              official=n == 1, nickname="試験用の投稿者", created_at=STAMP,
                              body="試験用の公式返信です。" if n == 1 else "実機試験用のコメントです。",
                              reviewed=(n == 1 or index == 1), parent_id=f"sample-{index}-0" if n == 1 else None)
                         for n in range(count)]
    return cases, comments


def read_fixture(portal, action, values):
    cases, comments = fixtures(portal)
    if action == "cases":
        query = str(values.get("q", "")).casefold()
        return {"cases": [row for row in cases if query in row["label"].casefold()]}
    if action == "comments":
        return {"comments": [row for row in comments.get(values.get("case_id"), [])
                             if not values.get("unread") or not row["reviewed"]], "next_cursor": None}
    if action == "history":
        return {"audit": [{"action": "hide", "created_at": STAMP}],
                "reports": [{"reason": "試験用の通報", "created_at": STAMP}]}
    raise ValueError("実機試験のコメントデータは閲覧専用です。")
