"""Pure model and HTML generation for the unknown-mushroom research room."""

from datetime import date, datetime, timezone
import hashlib
import html
import json
import os
import shutil
from urllib.parse import urlparse


def is_research_observation(observation):
    """Apply only the explicit research-page inclusion rule."""
    name = observation.get("gallery_name") if isinstance(observation, dict) else None
    return isinstance(name, str) and (name == "不明" or "?" in name or "？" in name)


def _article_identity(article):
    if not isinstance(article, dict):
        return None
    for key in ("article_id", "article_path", "url"):
        value = article.get(key)
        if value is not None and str(value).strip():
            return key, str(value)
    return None


def _date_value(value):
    if not isinstance(value, str):
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            pass
    return None


def _published_value(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _stable_id(key):
    payload = json.dumps(key, ensure_ascii=False, separators=(",", ":"))
    return "research-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_research_cases(portal_data):
    """Group eligible photos by exact name and explicit article identity."""
    if not isinstance(portal_data, dict) or portal_data.get("version") != 1:
        raise ValueError("research UI requires portal-data schema version 1")
    grouped = {}
    for position, observation in enumerate(portal_data.get("observations", [])):
        if not is_research_observation(observation):
            continue
        name = observation["gallery_name"]
        article = observation.get("article") if isinstance(observation.get("article"), dict) else {}
        identity = _article_identity(article)
        if identity is None:
            observation_id = observation.get("observation_id")
            fallback = str(observation_id) if observation_id is not None else f"position:{position}"
            identity = ("observation_id", fallback)
        key = (name, identity[0], identity[1])
        case = grouped.setdefault(key, {"case_id": _stable_id(key), "gallery_name": name,
            "photos": [], "article": {field: article.get(field) for field in
                ("article_id", "article_path", "title", "url", "published")},
            "_conflict": False})
        classification = observation.get("classification")
        case["_conflict"] = case["_conflict"] or (
            isinstance(classification, dict)
            and classification.get("status") == "manual_review_name_conflict")
        capture = observation.get("capture")
        capture_date = capture.get("date") if isinstance(capture, dict) else None
        parsed_capture = _date_value(capture_date)
        case["photos"].append({
            "src": observation.get("src") or "",
            "capture_date": capture_date if parsed_capture else None,
            "production_index": observation.get("production_index"),
            "observation_id": observation.get("observation_id"),
        })

    cases = []
    for case in grouped.values():
        case["photos"].sort(key=lambda photo: (
            photo["production_index"] is None,
            photo["production_index"] if isinstance(photo["production_index"], (int, float)) else 0,
            str(photo["observation_id"] or ""), str(photo["src"])))
        dates = sorted({_date_value(photo["capture_date"]) for photo in case["photos"]
                        if _date_value(photo["capture_date"])})
        case["capture_dates"] = [value.isoformat() for value in dates]
        case["latest_capture_date"] = dates[-1].isoformat() if dates else None
        case["photo_count"] = len(case["photos"])
        case["status"] = ("名称確認中" if case.pop("_conflict") else
                          "未同定" if case["gallery_name"] == "不明" else "候補名あり")
        cases.append(case)

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    cases.sort(key=lambda case: (
        case["latest_capture_date"] is None,
        -(date.fromisoformat(case["latest_capture_date"]).toordinal()
          if case["latest_capture_date"] else 0),
        _published_value(case["article"].get("published")) is None,
        -((_published_value(case["article"].get("published")) or epoch).timestamp()),
        case["case_id"],
    ))
    return cases


def build_research_model(portal_data):
    cases = build_research_cases(portal_data)
    return {"cases": cases, "case_count": len(cases),
            "photo_count": sum(case["photo_count"] for case in cases),
            "label_count": len({case["gallery_name"] for case in cases}),
            "multi_photo_count": sum(case["photo_count"] > 1 for case in cases)}


def _japanese_date(value):
    parsed = _date_value(value)
    return f"{parsed.year}年{parsed.month}月{parsed.day}日" if parsed else "不明"


def _safe_web_url(value):
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


def render_research_page(model):
    cards = []
    for case in model["cases"]:
        name = html.escape(case["gallery_name"])
        candidate = (f'<div class="research-candidate"><span>現在の候補名</span>'
                     f'<strong>{name}</strong></div>' if case["gallery_name"] != "不明" else "")
        dates = "、".join(_japanese_date(value) for value in case["capture_dates"]) or "不明"
        photos = []
        for number, photo in enumerate(case["photos"], 1):
            src = html.escape(str(photo["src"]), quote=True)
            photos.append(f'<a class="research-photo" href="{src}" target="_blank" rel="noopener">'
                          f'<img src="{src}" alt="{name}の観察写真 {number}" loading="lazy"></a>')
        article = case["article"]
        title = html.escape(str(article.get("title") or "タイトル不明"))
        url = _safe_web_url(article.get("url"))
        article_text = (f'<a href="{html.escape(url, quote=True)}" target="_top">{title}</a>'
                        if url else f'<span>{title}</span>')
        cards.append(f'''<article class="research-case">
<header><span class="research-status">{case["status"]}</span><h2>{name}</h2></header>
{candidate}<dl class="research-facts"><div><dt>撮影日</dt><dd>{dates}</dd></div>
<div><dt>写真枚数</dt><dd>{case["photo_count"]}枚</dd></div></dl>
<div class="research-photos">{''.join(photos)}</div>
<div class="research-article"><span class="research-label">観察記録</span>{article_text}</div>
</article>''')
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>❓ 不明キノコ研究室</title>
<link rel="stylesheet" href="assets/gallery.css"><link rel="stylesheet" href="assets/research.css"></head><body>
<main class="research-page"><a class="back-btn" href="index.html">◀ 図鑑トップに戻る</a>
<header class="research-intro"><h1>❓ 不明キノコ研究室</h1>
<p>まだ名前が分からないキノコや、候補名を調べている観察を集めました。</p>
<p>答えだけでなく、調べていく途中も観察記録の一部です。</p>
<p class="research-warning">「？」付きの名前は候補であり、同定が確定していることを意味しません。</p>
<div class="research-summary"><span>調査中 <strong>{model["case_count"]}</strong>件</span><span>写真 <strong>{model["photo_count"]}</strong>枚</span></div>
</header><section class="research-cases" aria-label="調査中の観察">{''.join(cards)}</section></main>
<script src="assets/gallery.js"></script></body></html>'''


def generate_research_page(portal_data, output_dir, assets_dir):
    model = build_research_model(portal_data)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)
    with open(os.path.join(output_dir, "research.html"), "w", encoding="utf-8") as stream:
        stream.write(render_research_page(model))
    shutil.copy2(os.path.join(assets_dir, "research.css"),
                 os.path.join(output_dir, "assets", "research.css"))
    return model
