"""Render the EXIF-only seasonal observation portal from portal-data schema v1."""

from collections import OrderedDict
import html
import json
import os


SEASONS = OrderedDict((
    ("spring", {"label": "春", "months": (3, 4, 5)}),
    ("summer", {"label": "夏", "months": (6, 7, 8)}),
    ("autumn", {"label": "秋", "months": (9, 10, 11)}),
    ("winter", {"label": "冬", "months": (12, 1, 2)}),
))


def group_subjects_by_season(portal_data):
    """Group subjects solely by their exported EXIF capture month counts."""
    grouped = OrderedDict((key, []) for key in SEASONS)
    for subject in portal_data.get("subjects", []):
        counts = subject.get("capture_month_counts")
        if not isinstance(counts, dict):
            continue
        for key, season in SEASONS.items():
            month_counts = {
                month: counts.get(str(month), 0)
                for month in season["months"]
                if isinstance(counts.get(str(month)), int) and counts[str(month)] > 0
            }
            if month_counts:
                grouped[key].append({**subject, "season_month_counts": month_counts})
    return grouped


def _subject_card(subject, safe_filename):
    name = html.escape(str(subject.get("gallery_name", "")))
    cover = html.escape(str(subject.get("cover_src", "")), quote=True)
    href = html.escape(f"{safe_filename(subject.get('gallery_name', ''))}.html", quote=True)
    counts = subject["season_month_counts"]
    months = "・".join(f"{month}月" for month in counts)
    photo_count = sum(counts.values())
    return f"""
      <article class="season-card">
        <a class="season-card__link" href="{href}">
          <img class="season-card__image" src="{cover}?width=640" alt="{name}" loading="lazy">
          <div class="season-card__body">
            <h3>{name}</h3>
            <p class="season-card__months">撮影月：{months}</p>
            <p class="season-card__count">この季節の観察写真 {photo_count}枚</p>
          </div>
        </a>
      </article>"""


def render_season_page(portal_data, safe_filename):
    """Return a self-contained page body while preserving the portal contract."""
    if portal_data.get("version") != 1:
        raise ValueError("season UI requires portal-data schema version 1")
    grouped = group_subjects_by_season(portal_data)
    buttons = []
    sections = []
    for position, (key, season) in enumerate(SEASONS.items()):
        subjects = grouped[key]
        observation_count = sum(
            sum(subject["season_month_counts"].values()) for subject in subjects
        )
        selected = "true" if position == 0 else "false"
        buttons.append(
            f'<button class="season-tab" type="button" role="tab" '
            f'id="tab-{key}" aria-controls="season-{key}" '
            f'aria-selected="{selected}" data-season="{key}">'
            f'<strong>{season["label"]}</strong><span>{"・".join(map(str, season["months"]))}月</span></button>'
        )
        cards = "".join(_subject_card(row, safe_filename) for row in subjects)
        sections.append(f"""
    <section class="season-results" id="season-{key}" role="tabpanel" aria-labelledby="tab-{key}" data-season-panel="{key}">
      <header class="season-results__header">
        <h2>{season['label']}の観察</h2>
        <p>{len(subjects)}種類・観察写真 {observation_count}枚</p>
      </header>
      <div class="season-grid">{cards}</div>
    </section>""")
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>季節から探す｜キノコ図鑑</title>
<link rel="stylesheet" href="assets/season.css">
<script src="assets/season.js" defer></script>
</head>
<body>
<main class="season-page">
  <nav class="season-back" aria-label="パンくず"><a href="index.html">← キノコ図鑑トップ</a></nav>
  <header class="season-hero">
    <p class="season-hero__eyebrow">OBSERVATION ARCHIVE</p>
    <h1>季節から探す</h1>
    <p class="season-hero__lead">このブログで実際に撮影した写真のEXIF撮影月から探せます。</p>
    <p class="season-hero__note">一般的なキノコの発生時期を示すものではありません。EXIF撮影月がない写真は季節に推測配置していません。</p>
  </header>
  <div class="season-tabs" role="tablist" aria-label="季節を選ぶ">{''.join(buttons)}</div>
  {''.join(sections)}
</main>
</body>
</html>
"""


def generate_season_page(portal_data, output_dir, assets_dir, safe_filename):
    """Write season.html and its dedicated assets from an in-memory fresh export."""
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)
    with open(os.path.join(output_dir, "season.html"), "w", encoding="utf-8") as stream:
        stream.write(render_season_page(portal_data, safe_filename))
    for filename in ("season.css", "season.js"):
        source = os.path.join(assets_dir, filename)
        target = os.path.join(output_dir, "assets", filename)
        with open(source, "rb") as source_stream, open(target, "wb") as target_stream:
            target_stream.write(source_stream.read())


def load_fresh_portal_data(path):
    """Load the file saved successfully by the current build run."""
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)
