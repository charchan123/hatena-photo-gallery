"""Evidence-backed subject detail view models and HTML rendering."""

from datetime import datetime, timezone
import html


FOOD_SAFETY_LABELS = {
    "poisonous_confirmed": "公的・専門資料に毒性の記載あり",
    "edibility_reported": "資料に食用の記載あり",
    "unknown": "食毒情報は未確認",
}

GENERIC_FOOD_NOTE = (
    "食用可否の自己判断には使用しない。"
    "毒性の記録がないことは安全を意味しない。"
)

FOOD_NOTE_REPLACEMENTS = (
    ("source report", "出典資料の記載"),
    ("food safety", "食毒情報"),
    ("edibility status", "食用可否の区分"),
    ("schema", "データ構造"),
    ("project", "本サイト"),
    ("source", "出典資料"),
    ("edibility", "食用可否"),
    ("master", "図鑑データ"),
)

FOOD_NOTE_SENTENCES = {
    "石川県の公的図鑑が「食」と記載しているというsource report。projectによる安全判定ではない。": (
        "石川県の公的図鑑では「食」と記載されています。"
        "これは出典資料の記載を示すもので、本サイトが食用可否を判定したものではありません。"
    ),
}


def reader_facing_food_note(note):
    """Translate internal data-management terms without changing source data."""
    note = _present(note)
    if note is None or note == GENERIC_FOOD_NOTE:
        return None
    if note in FOOD_NOTE_SENTENCES:
        return FOOD_NOTE_SENTENCES[note]
    for internal, reader_facing in FOOD_NOTE_REPLACEMENTS:
        note = note.replace(internal, reader_facing)
    return note


def _present(value):
    return value if isinstance(value, str) and value.strip() else None


def _source_ids(field):
    if not isinstance(field, dict):
        return []
    values = field.get("source_ids")
    return [value for value in values if isinstance(value, str)] if isinstance(values, list) else []


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


def _articles_for(gallery_name, observations):
    articles = {}
    for observation in observations:
        if observation.get("gallery_name") != gallery_name:
            continue
        article = observation.get("article")
        if not isinstance(article, dict):
            continue
        identity = _identity(article)
        if identity is None or identity in articles:
            continue
        articles[identity] = {
            "title": article.get("title"), "url": article.get("url"),
            "published": article.get("published"), "_identity": identity,
        }

    def key(article):
        timestamp = _published_timestamp(article.get("published"))
        return ((0, -timestamp) if timestamp is not None else (1, 0), article["_identity"])

    result = sorted(articles.values(), key=key)
    for article in result:
        article.pop("_identity")
    return result


def _knowledge(master, source_map):
    rows = []
    used_ids = []

    def add(label, value, field, *, note=None):
        value = _present(value)
        if value is None:
            return
        rows.append({"label": label, "value": value, "note": note})
        used_ids.extend(_source_ids(field))

    used_ids.extend(value for value in master.get("name_ja_sources", []) if isinstance(value, str))
    scientific = master.get("scientific_name") or {}
    add("学名", scientific.get("value"), scientific,
        note="出典資料に記載された学名" if scientific.get("name_status") == "source_reported" else None)
    taxonomy = master.get("taxonomy") or {}
    family, genus = taxonomy.get("family") or {}, taxonomy.get("genus") or {}
    add("科", family.get("value"), family)
    add("属", genus.get("value"), genus)
    for label, key in (("特徴", "features"), ("生育環境", "habitat"),
                       ("資料に記載された発生時期", "season")):
        field = master.get(key) or {}
        add(label, field.get("summary"), field)
    food = master.get("food_safety") or {}
    status = food.get("status")
    if status in FOOD_SAFETY_LABELS:
        add("食毒情報", FOOD_SAFETY_LABELS[status], food)
        notes = reader_facing_food_note(food.get("notes"))
        if notes:
            rows[-1]["note"] = notes
    toxin_names = []
    for toxin in master.get("toxins") or []:
        if not isinstance(toxin, dict) or not _present(toxin.get("name")):
            continue
        toxin_names.append(toxin["name"])
        used_ids.extend(_source_ids(toxin))
    if toxin_names:
        rows.append({"label": "資料に記載された成分", "value": "、".join(toxin_names), "note": None})

    sources = []
    for source_id in dict.fromkeys(used_ids):
        source = source_map.get(source_id)
        if isinstance(source, dict):
            sources.append({key: source.get(key) for key in ("source_id", "organization", "title", "url")})
    return {"rows": rows, "sources": sources}


def build_detail_views(portal_data):
    """Build detail models using only explicit links in portal schema v1."""
    if not isinstance(portal_data, dict) or portal_data.get("version") != 1:
        raise ValueError("detail UI requires portal-data schema version 1")
    reference = portal_data.get("reference_data") or {}
    master_root = reference.get("mushroom_master") or {}
    source_root = reference.get("sources") or {}
    masters = {row.get("mushroom_id"): row for row in master_root.get("entries", [])
               if isinstance(row, dict) and _present(row.get("mushroom_id"))}
    source_map = {row.get("source_id"): row for row in source_root.get("sources", [])
                  if isinstance(row, dict) and _present(row.get("source_id"))}
    observations = portal_data.get("observations") or []
    views = {}
    for subject in portal_data.get("subjects") or []:
        if not isinstance(subject, dict) or not _present(subject.get("gallery_name")):
            continue
        name = subject["gallery_name"]
        master = masters.get(subject.get("mushroom_master_id"))
        classification_counts = subject.get("classification_counts")
        taxonomy = subject.get("taxonomy")
        review_pending = isinstance(classification_counts, dict) and any(
            classification_counts.get(key, 0) >= 1
            for key in ("confirmed_mushroom_identity_uncertain", "manual_review_name_conflict", "legacy_review")
            if isinstance(classification_counts.get(key, 0), (int, float))
        )
        taxonomy_pending = (
            isinstance(taxonomy, dict)
            and taxonomy.get("subject_type") == "mushroom"
            and subject.get("mushroom_master_id") is None
        )
        views[name] = {
            "gallery_name": name,
            "knowledge": _knowledge(master, source_map) if master is not None else None,
            "knowledge_pending": master is None and (review_pending or taxonomy_pending),
            "articles": _articles_for(name, observations),
        }
    return views


def _format_published(value):
    timestamp = _published_timestamp(value)
    if timestamp is None:
        return "記事公開日：不明"
    date = datetime.fromtimestamp(timestamp, timezone.utc)
    return f"記事公開日：{date.year}年{date.month}月{date.day}日"


def _render_article(article):
    date = html.escape(_format_published(article.get("published")))
    title = html.escape(str(article.get("title") or "無題"))
    url = _present(article.get("url"))
    title_html = f'<a href="{html.escape(url, quote=True)}" target="_top">{title}</a>' if url else title
    return (f'<li class="subject-record-item"><time class="subject-record-date">{date}</time>'
            f'<div class="subject-record-title">{title_html}</div></li>')


def render_detail_sections(view):
    """Render optional knowledge and reverse-link sections for one subject."""
    if not isinstance(view, dict):
        return ""
    parts = []
    knowledge = view.get("knowledge")
    if isinstance(knowledge, dict):
        rows = []
        for row in knowledge.get("rows", []):
            label = html.escape(str(row["label"])); value = html.escape(str(row["value"]))
            note = row.get("note")
            note_html = f'<div class="knowledge-note">{html.escape(str(note))}</div>' if note else ""
            rows.append(f'<div class="knowledge-row"><dt class="knowledge-label">{label}</dt>'
                        f'<dd class="knowledge-value">{value}{note_html}</dd></div>')
        sources = []
        for source in knowledge.get("sources", []):
            organization = html.escape(str(source.get("organization") or ""))
            title = html.escape(str(source.get("title") or "出典"))
            text = f"{organization}：{title}" if organization else title
            url = _present(source.get("url"))
            sources.append(f'<li><a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{text}</a></li>'
                           if url else f"<li>{text}</li>")
        source_html = (f'<details class="knowledge-sources"><summary>出典を見る（{len(sources)}件）</summary>'
                       f'<ul>{"".join(sources)}</ul></details>') if sources else ""
        parts.append('<section class="knowledge-panel"><h2 class="knowledge-title">図鑑情報</h2>'
                     f'<dl class="knowledge-facts">{"".join(rows)}</dl>'
                     '<p class="knowledge-warning">食毒情報は参照資料の記載を整理したものです。'
                     '採取・調理・飲食の判断には使用しないでください。情報がないことは安全を意味しません。</p>'
                     f'{source_html}</section>')
    elif view.get("knowledge_pending") is True:
        parts.append('<section class="knowledge-pending"><h2>図鑑情報は現在整理中です</h2>'
                     '<p>名称や根拠資料を確認できた情報から順次追加しています。</p></section>')
    articles = view.get("articles") or []
    if articles:
        items = [_render_article(article) for article in articles]
        visible = "".join(items[:5])
        older = items[5:]
        more = (f'<details class="subject-record-more"><summary>過去の観察記録をさらに見る（{len(older)}件）</summary>'
                f'<ul class="subject-record-list">{"".join(older)}</ul></details>') if older else ""
        parts.append('<section class="subject-records"><h2>📔 このキノコが登場した観察記録</h2>'
                     f'<ul class="subject-record-list">{visible}</ul>{more}</section>')
    return "".join(parts)
