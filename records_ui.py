"""Build and render article-level observation records from portal schema v1."""

from datetime import datetime, timezone
import html
import os
import shutil


RECORD_CATEGORY = "キノコ探索日記"


def _identity(article):
    for key in ("article_id", "article_path", "url"):
        value = article.get(key)
        if value is not None and str(value).strip():
            return key, str(value)
    return None


def _published_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()
    except (ValueError, OverflowError):
        return None


def build_observation_records(portal_data):
    """Aggregate eligible production observations into deterministic articles."""
    if portal_data.get("version") != 1:
        raise ValueError("records UI requires portal-data schema version 1")
    records = {}
    for position, observation in enumerate(portal_data.get("observations", [])):
        article = observation.get("article")
        if not isinstance(article, dict):
            continue
        categories = article.get("categories")
        if not isinstance(categories, list) or RECORD_CATEGORY not in categories:
            continue
        identity = _identity(article)
        if identity is None:
            continue
        production_index = observation.get("production_index")
        index = production_index if isinstance(production_index, int) else float("inf")
        record = records.get(identity)
        if record is None:
            record = {
                key: article.get(key)
                for key in ("article_id", "article_path", "title", "url", "published", "updated", "categories")
            }
            record.update({"cover_src": "", "photo_count": 0, "subject_count": 0,
                           "first_production_index": production_index,
                           "_cover_order": (index, position), "_subjects": set(),
                           "_identity": identity})
            records[identity] = record
        record["photo_count"] += 1
        record["_subjects"].add(observation.get("gallery_name"))
        if (index, position) < record["_cover_order"]:
            record["_cover_order"] = (index, position)
            record["first_production_index"] = production_index
        if (index, position) == record["_cover_order"]:
            record["cover_src"] = observation.get("src") or ""

    result = []
    for record in records.values():
        record["subject_count"] = len(record.pop("_subjects"))
        record.pop("_cover_order")
        result.append(record)

    def sort_key(record):
        timestamp = _published_timestamp(record.get("published"))
        identity = record["_identity"]
        return (0, -timestamp, identity) if timestamp is not None else (1, 0, identity)

    result.sort(key=sort_key)
    for record in result:
        record.pop("_identity")
    return result


def _format_published(value):
    timestamp = _published_timestamp(value)
    if timestamp is None:
        return "公開日不明"
    published = datetime.fromtimestamp(timestamp, timezone.utc)
    return f"{published.year}年{published.month}月{published.day}日 公開"


def render_record_cards(records, limit=None):
    cards = []
    for position, record in enumerate(records[:limit] if limit is not None else records):
        title = html.escape(str(record.get("title") or "無題"))
        url = record.get("url")
        date = html.escape(_format_published(record.get("published")))
        cover = html.escape(str(record.get("cover_src") or ""), quote=True)
        badge = '<span class="record-card-badge">NEW!</span>' if position == 0 else ""
        image = (f'<img src="{cover}?width=500" alt="" loading="lazy">' if cover else "")
        body = (f'<div class="record-card-thumb">{image}</div><div class="record-card-body">'
                f'{badge}<div class="record-card-date">{date}</div>'
                f'<h3 class="record-card-title">{title}</h3>'
                f'<p class="record-card-meta">現在の図鑑掲載 {record["photo_count"]}枚・{record["subject_count"]}種類</p></div>')
        if url:
            safe_url = html.escape(str(url), quote=True)
            cards.append(f'<a class="record-card record-external-link" href="{safe_url}" target="_top">{body}</a>')
        else:
            cards.append(f'<article class="record-card">{body}</article>')
    return "".join(cards)


def render_records_page(portal_data):
    records = build_observation_records(portal_data)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>観察記録｜キノコ図鑑</title>
<link rel="stylesheet" href="assets/gallery.css">
<link rel="stylesheet" href="assets/records.css">
<script src="assets/gallery.js" defer></script></head><body>
<main class="aiuo-page records-page">
<header class="records-header"><h1 class="aiuo-title">📔 観察記録</h1>
<p class="records-lead">キノコ探索のブログ記事を新しい順にまとめています。</p>
<p class="records-note">表示順の日付は記事の公開日です。写真の撮影日とは別です。</p></header>
<div class="record-list">{render_record_cards(records)}</div>
<div class="records-back"><a href="index.html" class="back-btn">◀ トップに戻る</a></div>
</main></body></html>"""


def generate_records_page(portal_data, output_dir, assets_dir):
    """Write records.html and its records-only stylesheet."""
    records = build_observation_records(portal_data)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)
    with open(os.path.join(output_dir, "records.html"), "w", encoding="utf-8") as stream:
        stream.write(render_records_page(portal_data))
    shutil.copyfile(os.path.join(assets_dir, "records.css"),
                    os.path.join(output_dir, "assets", "records.css"))
    return records
