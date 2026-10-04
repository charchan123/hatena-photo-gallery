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


def render_research_page(model, identified=None):
    status_classes = {
        "未同定": "is-unidentified",
        "候補名あり": "is-candidate",
        "名称確認中": "is-review",
    }
    cards = []
    for case in model["cases"]:
        name = html.escape(case["gallery_name"])
        candidate_value = name if case["gallery_name"] != "不明" else "-"
        candidate = (
            f'<div class="research-candidate"><span>現在の候補名</span>'
            f'<strong>{candidate_value}</strong></div>'
        )
        dates = "、".join(_japanese_date(value) for value in case["capture_dates"]) or "不明"
        photos = []
        for number, photo in enumerate(case["photos"], 1):
            src = html.escape(str(photo["src"]), quote=True)
            photos.append(
                f'<a class="research-photo" href="{src}" target="_blank" rel="noopener">'
                f'<img src="{src}" alt="{name}の観察写真 {number}" loading="lazy"></a>'
            )
        article = case["article"]
        title = html.escape(str(article.get("title") or "タイトル不明"))
        url = _safe_web_url(article.get("url"))
        article_text = (
            f'<a href="{html.escape(url, quote=True)}" target="_top">{title}</a>'
            if url else f'<span>{title}</span>'
        )
        status = case["status"]
        cards.append(f'''<article class="research-case">
<header class="research-case__header">
  <div><span class="research-status {status_classes[status]}">{status}</span><h2>{name}</h2></div>
</header>
{candidate}
<dl class="research-facts"><div><dt>撮影日</dt><dd>{dates}</dd></div>
<div><dt>写真枚数</dt><dd>{case["photo_count"]}枚</dd></div></dl>
<div class="research-photos">{''.join(photos)}</div>
<div class="research-article"><span class="research-label">観察記録</span>{article_text}</div>
</article>''')
    archives = []
    for item in identified or []:
        case, identification = item["case"], item["identification"]
        photo = case["photos"][0] if case["photos"] else {"src": ""}
        article_url = _safe_web_url(case["article"].get("url"))
        article_link = (f'<a href="{html.escape(article_url, quote=True)}" target="_top">観察記録を見る</a>'
                        if article_url else "")
        archives.append(f'''<article class="research-case research-case--identified">
<img src="{html.escape(str(photo['src']), quote=True)}" alt="{html.escape(case['gallery_name'])}" loading="lazy">
<div><span class="research-status is-identified">判明済み</span>
<h3>{html.escape(case['gallery_name'])} <span aria-hidden="true">→</span> {html.escape(identification['identified_name'])}</h3>
<p>{html.escape(str(identification.get('note') or ''))}</p>{article_link}</div></article>''')
    archive_html = (f'''<section class="research-cases-wrap" aria-labelledby="identified-title">
<header class="research-cases-heading"><div><span class="research-eyebrow">IDENTIFIED</span>
<h2 id="identified-title">正体が判明したキノコ</h2></div><span>{len(archives)}件</span></header>
<div class="research-cases">{''.join(archives)}</div></section>''' if archives else "")
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>不明キノコ研究室｜キノコ図鑑</title>
<link rel="stylesheet" href="assets/gallery.css">
<link rel="stylesheet" href="assets/research.css">
<script src="assets/gallery.js" defer></script>
</head>
<body class="research-index">
<main id="gallery-content-root" class="research-page">
  <section class="research-hub" aria-labelledby="research-title">
    <header class="research-hero">
      <a class="research-back-link" href="index.html">← 図鑑へ戻る</a>
      <div class="research-hero-copy">
        <span class="research-eyebrow">RESEARCH LAB</span>
        <h1 id="research-title">不明キノコ研究室</h1>
        <p>まだ名前が分からないキノコや、候補名を調べているキノコを集めました。</p>
      </div>
    </header>
    <div class="research-overview">
      <div class="research-overview-copy">
        <span class="research-eyebrow">WORK IN PROGRESS</span>
        <h2>名前が分かるまでの調査記録</h2>
        <p>名前が分かるまでに調べたことや、候補になった特徴を記録しています。</p>
      </div>
      <div class="research-summary">
        <span>調査中 <strong>{model["case_count"]}</strong>件</span>
        <span>写真 <strong>{model["photo_count"]}</strong>枚</span>
      </div>
      <div class="research-notices">
        <p class="research-warning">「？」付きの名前は候補であり、同定が確定していることを意味しません。</p>
        <p class="research-coming-soon"><strong>コメント・返信機能は今後追加予定です。</strong><br>同定のヒントや情報を寄せられるようにする予定です。</p>
      </div>
    </div>
  </section>
  {archive_html}
  <section class="research-cases-wrap" aria-labelledby="research-cases-title">
    <header class="research-cases-heading">
      <div><span class="research-eyebrow">OPEN CASES</span><h2 id="research-cases-title">調査中の観察</h2></div>
      <span>{model["case_count"]}件</span>
    </header>
    <div class="research-cases">{''.join(cards)}</div>
  </section>
  <footer class="research-footer"><a href="index.html">← キノコ図鑑へ戻る</a></footer>
</main>
</body>
</html>'''


def generate_research_page(portal_data, output_dir, assets_dir, registry=None, mushroom_master=None):
    identified = []
    if registry is not None and mushroom_master is not None:
        from research_identifications import split_research_cases
        open_cases, identified = split_research_cases(portal_data, registry, mushroom_master)
        model = {"cases": open_cases, "case_count": len(open_cases),
                 "photo_count": sum(c["photo_count"] for c in open_cases),
                 "label_count": len({c["gallery_name"] for c in open_cases}),
                 "multi_photo_count": sum(c["photo_count"] > 1 for c in open_cases)}
    else:
        model = build_research_model(portal_data)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)
    with open(os.path.join(output_dir, "research.html"), "w", encoding="utf-8") as stream:
        stream.write(render_research_page(model, identified))
    shutil.copy2(os.path.join(assets_dir, "research.css"),
                 os.path.join(output_dir, "assets", "research.css"))
    return model
