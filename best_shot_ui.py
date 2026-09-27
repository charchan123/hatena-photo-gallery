"""Manual, owner-curated Best Shot collection built from fresh portal observations."""

from collections import Counter, defaultdict
from datetime import date
import html
import json
import os
import re
import shutil
from urllib.parse import urlparse


SCHEMA_VERSION = 1
MAX_COMMENT_LENGTH = 200
MAX_LOCATION_LENGTH = 100
MAX_ENTRIES_PER_MONTH = 3
ENTRY_FIELDS = {"selection_id", "observation_id", "comment", "location", "order"}
REQUIRED_ENTRY_FIELDS = {"selection_id", "observation_id", "comment", "order"}


class BestShotConfigError(ValueError):
    """The manually curated Best Shot configuration is invalid."""


def load_best_shot_config(path):
    """Load a version-controlled Best Shot configuration file."""
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def _non_empty_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise BestShotConfigError(f"{field} must be a non-empty string")
    return value.strip()


def _capture_date(observation, selection_id):
    capture = observation.get("capture")
    raw = capture.get("date") if isinstance(capture, dict) else None
    if not isinstance(raw, str):
        raise BestShotConfigError(f"{selection_id} requires observation.capture.date")
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as error:
        raise BestShotConfigError(f"{selection_id} has invalid observation.capture.date") from error
    if raw != parsed.isoformat():
        raise BestShotConfigError(f"{selection_id} has invalid observation.capture.date")
    return parsed


def validate_best_shot_config(config, portal_data):
    """Validate schema v1 and resolve every reference against portal observations."""
    if not isinstance(config, dict):
        raise BestShotConfigError("Best Shot config must be an object")
    if config.get("version") != SCHEMA_VERSION:
        raise BestShotConfigError("Best Shot config version must be exactly 1")
    if "entries" not in config or not isinstance(config["entries"], list):
        raise BestShotConfigError("entries must be a list")
    annual = config.get("annual_best", {})
    if not isinstance(annual, dict):
        raise BestShotConfigError("annual_best must be an object")
    if not isinstance(portal_data, dict) or portal_data.get("version") != 1:
        raise BestShotConfigError("Best Shot requires portal-data schema version 1")

    by_observation = defaultdict(list)
    for observation in portal_data.get("observations", []):
        if isinstance(observation, dict):
            by_observation[observation.get("observation_id")].append(observation)

    resolved = []
    selection_ids = set()
    observation_ids = set()
    month_counts = Counter()
    month_orders = set()
    for index, entry in enumerate(config["entries"]):
        if not isinstance(entry, dict):
            raise BestShotConfigError(f"entries[{index}] must be an object")
        unknown = set(entry) - ENTRY_FIELDS
        missing = REQUIRED_ENTRY_FIELDS - set(entry)
        if unknown or missing:
            raise BestShotConfigError(f"entries[{index}] has invalid fields")
        selection_id = _non_empty_string(entry.get("selection_id"), "selection_id")
        observation_id = _non_empty_string(entry.get("observation_id"), "observation_id")
        comment = _non_empty_string(entry.get("comment"), "comment")
        if len(comment) > MAX_COMMENT_LENGTH:
            raise BestShotConfigError("comment is longer than 200 characters")
        location = entry.get("location")
        if location is not None and not isinstance(location, str):
            raise BestShotConfigError("location must be a string")
        location = location.strip() if isinstance(location, str) else None
        location = location or None
        if location and len(location) > MAX_LOCATION_LENGTH:
            raise BestShotConfigError("location is longer than 100 characters")
        order = entry.get("order")
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise BestShotConfigError("order must be a positive integer")
        if selection_id in selection_ids:
            raise BestShotConfigError(f"duplicate selection_id: {selection_id}")
        if observation_id in observation_ids:
            raise BestShotConfigError(f"duplicate observation_id: {observation_id}")
        matches = by_observation.get(observation_id, [])
        if len(matches) != 1:
            raise BestShotConfigError(
                f"observation_id must resolve exactly once: {observation_id}"
            )
        observation = matches[0]
        captured = _capture_date(observation, selection_id)
        month_key = (captured.year, captured.month)
        month_counts[month_key] += 1
        if month_counts[month_key] > MAX_ENTRIES_PER_MONTH:
            raise BestShotConfigError("a month may contain at most 3 Best Shots")
        order_key = (*month_key, order)
        if order_key in month_orders:
            raise BestShotConfigError("order must be unique within a year and month")
        month_orders.add(order_key)
        selection_ids.add(selection_id)
        observation_ids.add(observation_id)
        article = observation.get("article")
        article = article if isinstance(article, dict) else {}
        resolved.append({
            "selection_id": selection_id,
            "observation_id": observation_id,
            "year": captured.year,
            "month": captured.month,
            "order": order,
            "gallery_name": str(observation.get("gallery_name") or ""),
            "src": str(observation.get("src") or ""),
            "capture_date": captured.isoformat(),
            "location": location,
            "comment": comment,
            "article_title": str(article.get("title") or ""),
            "article_url": str(article.get("url") or ""),
            "is_annual_best": False,
        })

    resolved_by_selection = {entry["selection_id"]: entry for entry in resolved}
    used_annual_selections = set()
    for year_text, selection_id in annual.items():
        if not isinstance(year_text, str) or not re.fullmatch(r"\d{4}", year_text):
            raise BestShotConfigError("annual_best keys must be YYYY strings")
        selection_id = _non_empty_string(selection_id, "annual_best selection_id")
        if selection_id in used_annual_selections:
            raise BestShotConfigError("an annual selection cannot be reused")
        selected = resolved_by_selection.get(selection_id)
        if selected is None:
            raise BestShotConfigError(f"annual_best selection does not exist: {selection_id}")
        if selected["year"] != int(year_text):
            raise BestShotConfigError("annual_best year must match capture year")
        selected["is_annual_best"] = True
        used_annual_selections.add(selection_id)
    return resolved


def build_best_shot_model(config, portal_data):
    """Build a descending year/month model solely from manually selected entries."""
    resolved = validate_best_shot_config(config, portal_data)
    grouped = defaultdict(lambda: defaultdict(list))
    for entry in resolved:
        grouped[entry["year"]][entry["month"]].append(entry)
    years = []
    for year in sorted(grouped, reverse=True):
        months = [
            {"month": month, "entries": sorted(grouped[year][month], key=lambda row: row["order"])}
            for month in sorted(grouped[year], reverse=True)
        ]
        flat = [entry for month in months for entry in month["entries"]]
        years.append({
            "year": year,
            "entry_count": len(flat),
            "annual_best": next((entry for entry in flat if entry["is_annual_best"]), None),
            "months": months,
        })
    return {
        "entry_count": len(resolved),
        "year_count": len(years),
        "latest_year": years[0]["year"] if years else None,
        "years": years,
    }


def _http_url(value):
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except (TypeError, ValueError):
        return False


def _card(entry, hero=False):
    esc = lambda value, quote=False: html.escape(str(value), quote=quote)
    src = esc(entry["src"], True)
    name = esc(entry["gallery_name"])
    captured = date.fromisoformat(entry["capture_date"])
    badge = '<span class="best-shot-badge">🏆 年間ベスト</span>' if entry["is_annual_best"] else ""
    location = f'<p class="best-shot-meta">場所：{esc(entry["location"])}</p>' if entry["location"] else ""
    article = ""
    if _http_url(entry["article_url"]):
        title = esc(entry["article_title"], True)
        article = (f'<a class="best-shot-article" href="{esc(entry["article_url"], True)}" '
                   f'target="_top" title="{title}">この日の観察記録を見る</a>')
    classes = "best-shot-card best-shot-card--hero" if hero else "best-shot-card"
    return f'''<article class="{classes}" data-selection-id="{esc(entry['selection_id'], True)}">
  <a class="best-shot-photo" href="{src}" target="_top"><img src="{src}" alt="{name}" loading="lazy"></a>
  <div class="best-shot-card__body">{badge}<h3>{name}</h3>
    <p class="best-shot-meta">撮影日：{captured.year}年{captured.month}月{captured.day}日</p>{location}
    <p class="best-shot-comment">{esc(entry['comment'])}</p>{article}
  </div>
</article>'''


def _year_content(year_model):
    annual = ""
    if year_model["annual_best"]:
        annual = (f'<section class="annual-best"><h2>🏆 {year_model["year"]}年 年間ベストショット</h2>'
                  f'{_card(year_model["annual_best"], hero=True)}</section>')
    months = []
    for month in year_model["months"]:
        cards = "".join(_card(entry) for entry in month["entries"])
        months.append(f'<section class="best-shot-month"><h2>{month["month"]}月</h2><div class="best-shot-grid">{cards}</div></section>')
    return annual + "".join(months)


def _document(title, body):
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><link rel="stylesheet" href="assets/gallery.css"><link rel="stylesheet" href="assets/best-shots.css"></head>
<body><main class="best-shots-page">{body}</main></body></html>'''


def render_best_shot_page(model):
    """Render the landing page with the latest selected capture year, if any."""
    header = '<header class="best-shots-header"><h1>📸 ベストショット</h1><p>キノコ探索の中で出会った、とっておきの写真を集めました。</p></header>'
    if not model["years"]:
        content = '<p class="best-shots-empty">ベストショットは現在選定中です。</p>'
    else:
        latest = model["years"][0]
        content = f'<h2 class="best-shots-year-title">{latest["year"]}年のベストショット</h2>{_year_content(latest)}'
        older = model["years"][1:]
        if older:
            links = "".join(f'<li><a href="best-shots-{row["year"]}.html">{row["year"]}年</a></li>' for row in older)
            content += f'<nav class="best-shots-archive"><h2>📚 過去のベストショット</h2><ul>{links}</ul></nav>'
    return _document("ベストショット｜キノコ図鑑", header + content + '<p class="best-shots-back"><a href="index.html">◀ トップに戻る</a></p>')


def render_best_shot_year_page(year_model):
    year = year_model["year"]
    body = f'<header class="best-shots-header"><h1>📸 {year}年のベストショット</h1></header>{_year_content(year_model)}'
    body += '<p class="best-shots-back"><a href="best-shots.html">◀ ベストショット一覧に戻る</a></p>'
    return _document(f"{year}年のベストショット｜キノコ図鑑", body)


def generate_best_shot_pages(portal_data, config_path, output_dir, assets_dir):
    """Generate the landing page and a stable archive page for every selected year."""
    model = build_best_shot_model(load_best_shot_config(config_path), portal_data)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)
    with open(os.path.join(output_dir, "best-shots.html"), "w", encoding="utf-8") as stream:
        stream.write(render_best_shot_page(model))
    for year_model in model["years"]:
        with open(os.path.join(output_dir, f'best-shots-{year_model["year"]}.html'), "w", encoding="utf-8") as stream:
            stream.write(render_best_shot_year_page(year_model))
    shutil.copy2(os.path.join(assets_dir, "best-shots.css"), os.path.join(output_dir, "assets", "best-shots.css"))
    return model
