"""Evidence-backed feature search data validation and page generation."""

import html
import json
import os
import shutil


class FeatureFacetError(ValueError):
    """Raised when curated feature data breaks its evidence contract."""


def load_feature_facets(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def _rows(root, key):
    rows = root.get(key) if isinstance(root, dict) else None
    if not isinstance(rows, list):
        raise FeatureFacetError(f"{key} must be a list")
    return rows


def validate_feature_facets(feature_data, mushroom_master):
    """Validate the complete v1 curated index without mutating either input."""
    if not isinstance(feature_data, dict) or feature_data.get("version") != 1:
        raise FeatureFacetError("feature facets version must be 1")
    groups = _rows(feature_data, "groups")
    facets = _rows(feature_data, "facets")
    entries = _rows(feature_data, "entries")
    masters = _rows(mushroom_master, "entries")

    def unique(rows, key, kind):
        result = {}
        for row in rows:
            value = row.get(key) if isinstance(row, dict) else None
            if not isinstance(value, str) or not value.strip():
                raise FeatureFacetError(f"{kind} requires non-empty {key}")
            if value in result:
                raise FeatureFacetError(f"duplicate {key}: {value}")
            result[value] = row
        return result

    group_map = unique(groups, "group_id", "group")
    facet_map = unique(facets, "facet_id", "facet")
    master_map = unique(masters, "mushroom_id", "mushroom master")
    entry_map = unique(entries, "mushroom_id", "feature entry")
    for facet_id, facet in facet_map.items():
        if facet.get("group_id") not in group_map:
            raise FeatureFacetError(f"facet_id {facet_id}: unknown group_id {facet.get('group_id')}")

    used = set()
    for mushroom_id, entry in entry_map.items():
        master = master_map.get(mushroom_id)
        if master is None:
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: unknown mushroom")
        features = master.get("features") if isinstance(master.get("features"), dict) else {}
        summary = features.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: features.summary is required")
        expected_sources = features.get("source_ids")
        assignments = entry.get("assignments")
        if not isinstance(assignments, list):
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: assignments must be a list")
        seen = set()
        for assignment in assignments:
            facet_id = assignment.get("facet_id") if isinstance(assignment, dict) else None
            context = f"mushroom_id {mushroom_id}, facet_id {facet_id}"
            if facet_id not in facet_map:
                raise FeatureFacetError(f"{context}: unknown facet")
            if facet_id in seen:
                raise FeatureFacetError(f"{context}: duplicate assignment")
            seen.add(facet_id); used.add(facet_id)
            evidence = assignment.get("evidence_text")
            if not isinstance(evidence, str) or not evidence.strip():
                raise FeatureFacetError(f"{context}: evidence_text must be non-empty")
            if evidence not in summary:
                raise FeatureFacetError(f"{context}: evidence_text is not an exact summary substring")
            sources = assignment.get("source_ids")
            if not isinstance(sources, list) or not sources:
                raise FeatureFacetError(f"{context}: source_ids must be non-empty")
            if set(sources) != set(expected_sources or []):
                raise FeatureFacetError(f"{context}: source_ids do not match features.source_ids")

    covered = {row["mushroom_id"] for row in masters
               if isinstance(row.get("features"), dict)
               and isinstance(row["features"].get("summary"), str)
               and row["features"]["summary"].strip()}
    if set(entry_map) != covered:
        raise FeatureFacetError(
            f"mushroom_id coverage mismatch: missing={sorted(covered-set(entry_map))}, "
            f"extra={sorted(set(entry_map)-covered)}")
    unused = set(facet_map) - used
    if unused:
        raise FeatureFacetError(f"unused facet_id values: {sorted(unused)}")
    return True


def build_feature_search_model(portal_data, feature_data, safe_filename=lambda value: value):
    """Join subjects only through their explicit mushroom_master_id."""
    if not isinstance(portal_data, dict) or portal_data.get("version") != 1:
        raise ValueError("feature UI requires portal-data schema version 1")
    facets = {row["facet_id"]: row for row in feature_data["facets"]}
    assignments = {
        row["mushroom_id"]: [item["facet_id"] for item in row["assignments"]]
        for row in feature_data["entries"]
    }
    results = []
    for subject in portal_data.get("subjects", []):
        facet_ids = assignments.get(subject.get("mushroom_master_id"))
        if not facet_ids:
            continue
        name = subject.get("gallery_name")
        if not isinstance(name, str) or not name:
            continue
        results.append({"gallery_name": name, "cover_src": subject.get("cover_src", ""),
                        "href": f"{safe_filename(name)}.html", "facet_ids": list(facet_ids),
                        "facet_labels": [facets[value]["label"] for value in facet_ids]})
    counts = {facet_id: sum(facet_id in row["facet_ids"] for row in results) for facet_id in facets}
    groups = [{**group, "facets": [{**facet, "count": counts[facet["facet_id"]]}
               for facet in feature_data["facets"] if facet["group_id"] == group["group_id"]]}
              for group in feature_data["groups"]]
    return {"groups": groups, "results": results, "coverage_count": len(results)}


def render_feature_page(model, safe_filename=None):
    groups = []
    for group in model["groups"]:
        buttons = "".join(
            f'<button type="button" class="feature-filter" data-facet="{html.escape(f["facet_id"], quote=True)}" '
            f'aria-pressed="false">{html.escape(f["label"])} <span>{f["count"]}</span></button>'
            for f in group["facets"])
        groups.append(f'<fieldset><legend>{html.escape(group["label"])}</legend><div class="feature-buttons">{buttons}</div></fieldset>')
    cards = []
    for row in model["results"]:
        name = html.escape(row["gallery_name"]); cover = html.escape(str(row["cover_src"]), quote=True)
        chips = "".join(f'<span class="feature-chip" data-facet-chip="{html.escape(fid, quote=True)}">{html.escape(label)}</span>'
                        for fid, label in zip(row["facet_ids"], row["facet_labels"]))
        cards.append(f'<a class="feature-card" href="{html.escape(row["href"], quote=True)}" data-facets="{html.escape(" ".join(row["facet_ids"]), quote=True)}">'
                     f'<img src="{cover}?width=500" alt="{name}" loading="lazy"><h2>{name}</h2><div class="feature-chips">{chips}</div></a>')
    count = model["coverage_count"]
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>特徴から探す｜キノコ図鑑</title><link rel="stylesheet" href="assets/gallery.css"><link rel="stylesheet" href="assets/features.css">
<script src="assets/gallery.js" defer></script><script src="assets/features.js" defer></script></head><body>
<main class="feature-page"><a class="back-btn" href="index.html">◀ 図鑑トップに戻る</a><header><h1>🔎 特徴から探す</h1>
<p>写真や資料に記載された見た目の特徴を組み合わせて探せます。</p><p class="feature-warning">選んだ特徴が出典資料に明記されている図鑑登録種を表示します。特徴だけでキノコの種類を判定する機能ではありません。</p>
<p>特徴検索対応: {count}種類</p></header><section class="feature-controls"><p>選んだ特徴をすべて含む図鑑登録種を表示します。条件を選ぶと絞り込めます。</p>{''.join(groups)}
<button type="button" class="feature-clear">選択をクリア</button></section><div class="feature-result-count" aria-live="polite">{count}種類</div>
<div class="feature-results">{''.join(cards)}</div><p class="feature-empty" hidden>該当する図鑑登録種はありません。条件を減らしてみてください。</p></main></body></html>'''


def generate_feature_page(portal_data, feature_data, output_dir, assets_dir, safe_filename):
    model = build_feature_search_model(portal_data, feature_data, safe_filename)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)
    with open(os.path.join(output_dir, "features.html"), "w", encoding="utf-8") as stream:
        stream.write(render_feature_page(model))
    for filename in ("features.css", "features.js"):
        shutil.copy2(os.path.join(assets_dir, filename), os.path.join(output_dir, "assets", filename))
    return model
