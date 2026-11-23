from copy import deepcopy
import json
from pathlib import Path

import main
import portal_data
import pytest


def references(*, aliases=None, canonical="菌名"):
    taxonomy = {"version": 1, "entries": [{
        "canonical_name": canonical, "subject_type": "mushroom",
        "aliases": aliases or [], "verification_status": "verified",
        "mushroom_master_id": "fungus-id", "sources": ["source-id"],
    }]}
    master = {"version": 1, "entries": [{
        "mushroom_id": "fungus-id", "canonical_name_ja": canonical,
    }]}
    sources = {"version": 1, "sources": [{"source_id": "source-id"}]}
    return taxonomy, master, sources


def shadow(src="image.jpg", *, gallery_name="菌名", legacy_alt="旧名",
           subject_type="mushroom", detected_label="菌名", path="article.html"):
    return {
        "src": src, "gallery_name": gallery_name, "legacy_alt": legacy_alt,
        "subject_type": subject_type, "detected_label": detected_label,
        "article_path": path, "classification_reason": "taxonomy_mushroom",
        "classification_confidence": "high", "subject_state_status": "accepted",
        "taxonomy_canonical_name": gallery_name, "taxonomy_match_type": "canonical",
    }


def build(entries=None, shadows=None, exif=None, articles=None, refs=None):
    taxonomy, master, sources = refs or references()
    return portal_data.build_portal_data(
        production_entries=entries or [{"alt": "菌名", "src": "image.jpg"}],
        shadow_metadata=[shadow()] if shadows is None else shadows,
        article_metadata=articles or {}, exif_cache=exif or {},
        taxonomy=taxonomy, mushroom_master=master, sources=sources,
        production_mode="phase3c_hybrid", cutover_active=True,
    )


def test_one_occurrence_and_confirmed_classification():
    result = build()
    assert len(result["observations"]) == 1
    assert result["observations"][0]["classification"]["status"] == "confirmed_named_mushroom"


def test_duplicate_src_queue_ids_grouping_and_cover_are_stable():
    entries = [{"alt": "菌名", "src": "same.jpg"}] * 2
    shadows = [shadow("same.jpg"), shadow("same.jpg")]
    first = build(entries, shadows)
    second = build(entries, shadows)
    rows = first["observations"]
    assert len(rows) == 2
    assert len({row["observation_id"] for row in rows}) == 2
    assert [row["observation_id"] for row in rows] == [
        row["observation_id"] for row in second["observations"]
    ]
    assert first["subjects"][0]["photo_count"] == 2
    assert first["subjects"][0]["cover_src"] == "same.jpg"


def test_article_metadata_propagates_but_not_to_capture_date():
    articles = {"article.html": {
        "article_id": "id", "title": "2026年9月19日 静岡県浜松市",
        "url": "https://example.test/post", "published": "2026-09-19T01:00:00Z",
        "updated": "2026-09-20T01:00:00Z", "categories": ["キノコ"], "excerpt": "本文冒頭",
    }}
    observation = build(articles=articles)["observations"][0]
    assert observation["article"] == {"article_path": "article.html", **articles["article.html"]}
    assert observation["capture"]["date"] is None
    assert "location" not in observation


def test_exif_date_is_only_capture_date_source():
    capture = build(exif={"image.jpg": {
        "date": "2026/09/19", "model": "camera", "iso": "100"
    }})["observations"][0]["capture"]
    assert (capture["date"], capture["month"], capture["date_source"]) == (
        "2026-09-19", 9, "exif"
    )
    assert capture["camera"]["model"] == "camera"


def test_invalid_exif_date_is_safely_unknown():
    capture = build(exif={"image.jpg": {"date": "2026/99/99"}})["observations"][0]["capture"]
    assert (capture["date"], capture["month"], capture["date_source"]) == (None, None, None)


def test_exact_canonical_link_and_reference_provenance():
    result = build()
    assert result["observations"][0]["mushroom_master_id"] == "fungus-id"
    assert result["subjects"][0]["knowledge_available"] is True
    assert result["reference_data"]["sources"]["sources"][0]["source_id"] == "source-id"


def test_only_exact_canonical_names_link():
    taxonomy, master, sources = references(aliases=["別名"])
    for name in ("別名", " 菌名 ", "菌名？", "不明"):
        result = build(entries=[{"alt": name, "src": "image.jpg"}],
                       shadows=[], refs=(taxonomy, master, sources))
        assert result["observations"][0]["mushroom_master_id"] is None



def test_four_standalone_guide_links_reuse_exact_named_photos_without_classification():
    """The next four are display-only joins, never automatic photo identification."""
    import detail_ui
    import mushroom_knowledge as knowledge

    manifest = json.loads((Path(__file__).resolve().parents[1] / "data/guide-links.json").read_text(encoding="utf-8"))
    links = {
        "アカモミタケ": "akamomitake",
        "アミタケ": "amitake",
        "ウラベニホテイシメジ": "urabenihoteisimeji",
        "オニイグチモドキ": "oniigutimodoki",
    }
    assert len(manifest) == 34
    assert all(manifest.get(name) == key for name, key in links.items())
    taxonomy = main.load_subject_taxonomy()
    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    by_name = {row["canonical_name"]: row for row in taxonomy["entries"]}
    masters = {row["mushroom_id"]: row for row in master["entries"]}
    for name, key in links.items():
        assert name not in by_name
        assert masters[key]["canonical_name_ja"] == name
        assert masters[key]["food_safety"]["status"] == "edibility_reported"
        assert masters[key]["food_safety"]["notes"] == detail_ui.NEXT_FOUR_SOURCE_NOTE
        assert masters[key]["scientific_name"]["source_ids"]

    original_names = list(links) + ["アミタケ？", "アミタケ sp.", "アミタケ cf.", "アミタケ(広義)", "全く別のキノコ"]
    photo_rows = [{"alt": name, "src": f"test-{i}.jpg"} for i, name in enumerate(original_names)]
    def build_with(links):
        return portal_data.build_portal_data(
            production_entries=photo_rows, shadow_metadata=[], article_metadata={},
            exif_cache={}, taxonomy=taxonomy, mushroom_master=master, sources=sources,
            production_mode="phase3c_hybrid", cutover_active=True, guide_links=links
        )
    before = build_with({})
    after = build_with(links)
    expected = deepcopy(before)
    for observation in expected["observations"]:
        observation["mushroom_master_id"] = links.get(observation["gallery_name"])
    for subject in expected["subjects"]:
        key = links.get(subject["gallery_name"])
        subject["mushroom_master_id"] = key
        subject["knowledge_available"] = key is not None
    expected["summary"]["master_linked_subject_count"] += 4
    expected["summary"]["master_unlinked_subject_count"] -= 4
    assert after == expected
    assert [e["src"] for e in after["observations"]] == [e["src"] for e in photo_rows]
    assert [e["gallery_name"] for e in after["observations"]] == original_names

    views = detail_ui.build_detail_views(after)
    for name, key in links.items():
        rendered = detail_ui.render_detail_sections(views[name])
        assert views[name]["knowledge"] is not None
        assert views[name]["knowledge"]["sources"]
        assert detail_ui.NEXT_FOUR_DISPLAY_NOTE in rendered
        assert "資料には食用との記載があります" in rendered
        assert "キノコを採ったり、調理したり、食べたりする判断には使わないでください" in rendered
    for name in original_names[4:]:
        assert views[name]["knowledge"] is None


def test_third_four_standalone_guide_links_preserve_photos_food_status_and_sources():
    """Review candidate copy without changing the source facts or gallery identities."""
    import detail_ui
    import mushroom_knowledge as knowledge

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "data/guide-links.json").read_text(encoding="utf-8"))
    third = {
        "カニノツメ": ("kaninotume", "unknown", "食毒の区分は確認できていません"),
        "カワリハツ": ("kawarihatu", "edibility_reported", "資料には食用との記載があります"),
        "ガンタケ": ("gantake", "poisonous_confirmed", "公的・専門資料には毒性の記載があります"),
        "キツネタケ": ("kitunetake", "edibility_reported", "資料には食用との記載があります"),
    }
    assert len(manifest) == 34
    assert all(manifest.get(name) == ident for name, (ident, _, _) in third.items())

    taxonomy = main.load_subject_taxonomy()
    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    master_by_id = {entry["mushroom_id"]: entry for entry in master["entries"]}
    source_ids = {src["source_id"] for src in sources["sources"]}
    taxonomy_names = {row["canonical_name"] for row in taxonomy["entries"]}

    for name, (ident, status, label) in third.items():
        assert name not in taxonomy_names
        original = master_by_id[ident]
        assert original["canonical_name_ja"] == name
        assert original["food_safety"]["status"] == status
        assert original["scientific_name"]["source_ids"]
        assert set(original["scientific_name"]["source_ids"]) <= source_ids
        assert set(original["food_safety"]["source_ids"]) <= source_ids
        assert detail_ui.THIRD_FOUR_FOOD_NOTE_CANDIDATES[ident] == (
            name, original["food_safety"]["notes"],
            detail_ui.THIRD_FOUR_FOOD_NOTE_CANDIDATES[ident][2],
        )
        assert detail_ui.THIRD_FOUR_FOOD_NOTE_CANDIDATES[ident][2].endswith("。")

    ambiguous = ["カニノツメ？", "カワリハツ sp.", "ガンタケ cf.", "キツネタケ（広義）",
                 "ガンタケかもしれない", "不明"]
    names = list(third) + ambiguous
    production = [{"alt": name, "src": f"third-{i}.jpg"} for i, name in enumerate(names)]
    def project(links):
        return portal_data.build_portal_data(
            production_entries=production, shadow_metadata=[], article_metadata={},
            exif_cache={}, taxonomy=taxonomy, mushroom_master=master, sources=sources,
            production_mode="phase3c_hybrid", cutover_active=True, guide_links=links,
        )

    before = project({})
    after = project({name: val[0] for name, val in third.items()})
    expected = deepcopy(before)
    for photo in expected["observations"]:
        photo["mushroom_master_id"] = manifest.get(photo["gallery_name"])
    for row in expected["subjects"]:
        linked = manifest.get(row["gallery_name"])
        row["mushroom_master_id"] = linked
        row["knowledge_available"] = linked is not None
    expected["summary"]["master_linked_subject_count"] += 4
    expected["summary"]["master_unlinked_subject_count"] -= 4
    assert after == expected
    assert [(row["src"], row["gallery_name"], row["classification"])
            for row in after["observations"]] == [
            (row["src"], row["gallery_name"], row["classification"])
            for row in before["observations"]]

    views = detail_ui.build_detail_views(after)
    for name, (ident, status, label) in third.items():
        section = views[name]
        assert section["knowledge"] is not None
        assert section["knowledge"]["sources"]
        assert section["food_safety_status"] == status
        html = detail_ui.render_detail_sections(section)
        assert label in html, name
        assert detail_ui.THIRD_FOUR_FOOD_NOTE_CANDIDATES[ident][2] in html, name
        assert "食用可否の自己判断には使用しない。" not in html, name
        assert "キノコを採ったり、調理したり、食べたりする判断には使わないでください" in html, name
    for name in ambiguous:
        assert views[name]["knowledge"] is None
    gantake = detail_ui.render_detail_sections(views["ガンタケ"])
    assert "食用にすべきでない" in gantake
    assert "加熱すれば安全だと判断することはできません" in gantake
    assert "公的・専門資料には毒性の記載があります" in gantake
    assert "石川県の資料では、食毒欄に「不食」" in detail_ui.render_detail_sections(views["カニノツメ"])


def test_third_four_display_text_is_not_reused_if_source_changes():
    import detail_ui
    import mushroom_knowledge as knowledge

    master = knowledge.load_mushroom_master()
    base = {row["mushroom_id"]: row for row in master["entries"]}["gantake"]
    existing = detail_ui._knowledge(base, {})
    food = next(row for row in existing["rows"] if row["label"] == "食毒情報")
    assert food["note"] == detail_ui.THIRD_FOUR_FOOD_NOTE_CANDIDATES["gantake"][2]

    changed = deepcopy(base)
    changed["food_safety"]["notes"] += " 未確認の新情報。"
    new = detail_ui._knowledge(changed, {})
    food = next(row for row in new["rows"] if row["label"] == "食毒情報")
    assert food["note"] != detail_ui.THIRD_FOUR_FOOD_NOTE_CANDIDATES["gantake"][2]
    assert "未確認の新情報" in food["note"]

    changed = deepcopy(base)
    changed["canonical_name_ja"] = "別の菌名"
    renamed = detail_ui._knowledge(changed, {})
    food = next(row for row in renamed["rows"] if row["label"] == "食毒情報")
    assert food["note"] != detail_ui.THIRD_FOUR_FOOD_NOTE_CANDIDATES["gantake"][2]



def test_fourth_four_exact_links_conflict_warning_and_source_integrity():
    """Expose a food-status conflict without changing source evidence or photo identity."""
    import detail_ui
    import mushroom_knowledge as knowledge

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "data/guide-links.json").read_text(encoding="utf-8"))
    fourth = {
        "キララタケ": ("kiraratake", "edibility_reported",
                  detail_ui.KIRARATAKE_CONFLICT_LABEL),
        "クチベニタケ": ("kutibenitake", "unknown",
                   "食毒の区分は確認できていません"),
        "クリタケ": ("kuritake", "edibility_reported",
                "資料には食用との記載があります"),
        "コタマゴテングタケ": ("kotamagotengutake", "poisonous_confirmed",
                       "公的・専門資料には毒性の記載があります"),
    }
    assert len(manifest) == 34
    assert all(manifest.get(name) == ident
               for name, (ident, _, _) in fourth.items())

    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    taxonomy = main.load_subject_taxonomy()
    by_id = {row["mushroom_id"]: row for row in master["entries"]}
    known_sources = {row["source_id"] for row in sources["sources"]}
    existing_taxonomy = {row["canonical_name"] for row in taxonomy["entries"]}
    for name, (ident, status, label) in fourth.items():
        record = by_id[ident]
        assert name not in existing_taxonomy
        assert record["canonical_name_ja"] == name
        assert record["food_safety"]["status"] == status
        assert record["scientific_name"]["source_ids"]
        assert set(record["scientific_name"]["source_ids"]) <= known_sources
        assert set(record["food_safety"]["source_ids"]) <= known_sources
        name2, note, polished = detail_ui.FOURTH_FOUR_FOOD_NOTE_REVIEWED[ident]
        assert (name2, note) == (name, record["food_safety"]["notes"])
        assert polished.endswith("。")
        assert label

    speculative = [
        "キララタケ？", "キララタケ cf.", "クチベニタケ sp.",
        "クリタケ（広義）", "コタマゴテングタケ？", "不明",
    ]
    names = list(fourth) + speculative
    photos = [{"alt": name, "src": f"fourth-photo-{i}.jpg"}
              for i, name in enumerate(names)]

    def project(links):
        return portal_data.build_portal_data(
            production_entries=photos, shadow_metadata=[], article_metadata={},
            exif_cache={}, taxonomy=taxonomy, mushroom_master=master,
            sources=sources, production_mode="phase3c_hybrid", cutover_active=True,
            guide_links=links,
        )

    before = project({})
    only_four = {name: data[0] for name, data in fourth.items()}
    after = project(only_four)
    expected = deepcopy(before)
    for row in expected["observations"]:
        row["mushroom_master_id"] = only_four.get(row["gallery_name"])
    for row in expected["subjects"]:
        ident = only_four.get(row["gallery_name"])
        row["mushroom_master_id"] = ident
        row["knowledge_available"] = ident is not None
    expected["summary"]["master_linked_subject_count"] += 4
    expected["summary"]["master_unlinked_subject_count"] -= 4
    assert after == expected
    assert [(row["src"], row["gallery_name"], row["classification"])
            for row in after["observations"]] == [
            (row["src"], row["gallery_name"], row["classification"])
            for row in before["observations"]]

    views = detail_ui.build_detail_views(after)
    for name, (ident, status, label) in fourth.items():
        section = views[name]
        assert section["knowledge"] is not None
        assert section["knowledge"]["sources"]
        assert section["food_safety_status"] == status
        info = next(row for row in section["knowledge"]["rows"]
                    if row["label"] == "食毒情報")
        assert info["value"] == label, name
        assert info["note"] == detail_ui.FOURTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        html = detail_ui.render_detail_sections(section)
        assert label in html
        assert info["note"].replace("&", "&amp;") in html
        assert "キノコを採ったり、調理したり、食べたりする判断には使わないでください" in html
        assert "食用可否の自己判断には使用しない。" not in html
    for name in speculative:
        assert views[name]["knowledge"] is None

    kirara = detail_ui.render_detail_sections(views["キララタケ"])
    assert "資料によって食毒の記載が異なります" in kirara
    assert "島根県" in kirara and "「毒」" in kirara
    assert "中国" in kirara and "消化器症状" in kirara
    assert "コプリンが含まれると確定したものではありません" in kirara
    assert "資料には食用との記載があります" not in kirara


def test_fourth_four_review_does_not_reapply_stale_source_prose():
    import detail_ui
    import mushroom_knowledge as knowledge

    master = knowledge.load_mushroom_master()
    by_id = {e["mushroom_id"]: e for e in master["entries"]}
    for ident in ("kiraratake", "kutibenitake", "kuritake", "kotamagotengutake"):
        record = by_id[ident]
        exact = detail_ui._knowledge(record, {})
        food = next(e for e in exact["rows"] if e["label"] == "食毒情報")
        assert food["note"] == detail_ui.FOURTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]

        modified = deepcopy(record)
        modified["food_safety"]["notes"] += " 再審査が必要な追加情報。"
        changed = detail_ui._knowledge(modified, {})
        food = next(e for e in changed["rows"] if e["label"] == "食毒情報")
        assert food["note"] != detail_ui.FOURTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        assert "再審査が必要な追加情報" in food["note"]

        changed_name = deepcopy(record)
        changed_name["canonical_name_ja"] = "別の菌名"
        renamed = detail_ui._knowledge(changed_name, {})
        food = next(e for e in renamed["rows"] if e["label"] == "食毒情報")
        assert food["note"] != detail_ui.FOURTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]


def test_fifth_four_exact_gallery_names_do_not_change_identity_or_toxicity():
    """Ensure the fifth-group pages only display original source-linked facts."""
    import detail_ui
    import mushroom_knowledge as knowledge

    path = Path(__file__).resolve().parents[1] / "data/guide-links.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    fifth = {
        "ツルタケ": ("turutake", "edibility_reported", "資料には食用との記載があります"),
        "テングタケ": ("tengutake", "poisonous_confirmed", "公的・専門資料には毒性の記載があります"),
        "ニガクリタケ": ("nigakuritake", "poisonous_confirmed", "公的・専門資料には毒性の記載があります"),
        "ヌメリイグチ": ("numeriiguti", "edibility_reported", "資料には食用との記載があります"),
    }
    assert len(manifest) == 34
    assert all(manifest.get(name) == ident for name, (ident, _, _) in fifth.items())

    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    taxonomy = main.load_subject_taxonomy()
    by_id = {row["mushroom_id"]: row for row in master["entries"]}
    source_ids = {row["source_id"] for row in sources["sources"]}
    taxonomy_names = {row["canonical_name"] for row in taxonomy["entries"]}
    for name, (ident, expected_status, expected_label) in fifth.items():
        row = by_id[ident]
        assert name not in taxonomy_names
        assert row["canonical_name_ja"] == name
        assert row["food_safety"]["status"] == expected_status
        assert row["scientific_name"]["source_ids"]
        assert set(row["scientific_name"]["source_ids"]) <= source_ids
        assert set(row["food_safety"]["source_ids"]) <= source_ids
        approved = detail_ui.FIFTH_FOUR_FOOD_NOTE_REVIEWED[ident]
        assert approved[:2] == (name, row["food_safety"]["notes"])
        assert approved[2].endswith("。")
        assert expected_label

    ambiguous = [
        "ツルタケ？", "ツルタケ sp.", "テングタケ cf.",
        "ニガクリタケ（広義）", "ヌメリイグチ？", "不明",
    ]
    names = list(fifth) + ambiguous
    original = [{"alt": name, "src": f"fifth-photo-{i}.jpg"}
                for i, name in enumerate(names)]

    def build(links):
        return portal_data.build_portal_data(
            production_entries=original, shadow_metadata=[], article_metadata={},
            exif_cache={}, taxonomy=taxonomy, mushroom_master=master,
            sources=sources, production_mode="phase3c_hybrid", cutover_active=True,
            guide_links=links,
        )

    before = build({})
    chosen = {name: row[0] for name, row in fifth.items()}
    after = build(chosen)
    expected = deepcopy(before)
    for obs in expected["observations"]:
        obs["mushroom_master_id"] = chosen.get(obs["gallery_name"])
    for row in expected["subjects"]:
        key = chosen.get(row["gallery_name"])
        row["mushroom_master_id"] = key
        row["knowledge_available"] = key is not None
    expected["summary"]["master_linked_subject_count"] += 4
    expected["summary"]["master_unlinked_subject_count"] -= 4
    assert after == expected
    assert [(x["src"], x["gallery_name"], x["classification"])
            for x in after["observations"]] == [
            (x["src"], x["gallery_name"], x["classification"])
            for x in before["observations"]]

    views = detail_ui.build_detail_views(after)
    for name, (ident, expected_status, expected_label) in fifth.items():
        section = views[name]
        assert section["knowledge"] is not None
        assert section["knowledge"]["sources"]
        assert section["food_safety_status"] == expected_status
        food = next(x for x in section["knowledge"]["rows"] if x["label"] == "食毒情報")
        assert food["value"] == expected_label
        assert food["note"] == detail_ui.FIFTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        markup = detail_ui.render_detail_sections(section)
        assert expected_label in markup
        assert food["note"] in markup
        assert "このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。" in markup
        assert "食用可否の自己判断には使用しない。" not in markup
    for name in ambiguous:
        assert views[name]["knowledge"] is None

    nigakuritake = detail_ui.render_detail_sections(views["ニガクリタケ"])
    assert "死亡例" in nigakuritake
    assert "重篤な中毒事例" in nigakuritake
    assert "原因物質が確定したという意味ではありません" in nigakuritake
    tengutake = detail_ui.render_detail_sections(views["テングタケ"])
    assert "神経系の症状" in tengutake


def test_fifth_four_polite_copy_fails_closed_when_original_source_changes():
    import detail_ui
    import mushroom_knowledge as knowledge

    rows = knowledge.load_mushroom_master()["entries"]
    by_id = {row["mushroom_id"]: row for row in rows}
    for ident in ("turutake", "tengutake", "nigakuritake", "numeriiguti"):
        master = by_id[ident]
        original = detail_ui._knowledge(master, {})
        food = next(x for x in original["rows"] if x["label"] == "食毒情報")
        expected_note = detail_ui.FIFTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        assert food["note"] == expected_note
        changed = deepcopy(master)
        changed["food_safety"]["notes"] += " 新しい未承認の情報。"
        after = detail_ui._knowledge(changed, {})
        food = next(x for x in after["rows"] if x["label"] == "食毒情報")
        assert food["note"] != expected_note
        assert "新しい未承認の情報" in food["note"]
        renamed = deepcopy(master)
        renamed["canonical_name_ja"] = "別の名前"
        other = detail_ui._knowledge(renamed, {})
        food = next(x for x in other["rows"] if x["label"] == "食毒情報")
        assert food["note"] != expected_note


def test_sixth_four_exact_links_keep_master_and_observations_unchanged():
    """Link four already named subjects, without inferring identity from similar labels."""
    import detail_ui
    import mushroom_knowledge as knowledge

    manifest = json.loads((Path(__file__).resolve().parents[1] /
                           "data/guide-links.json").read_text(encoding="utf-8"))
    sixth = {
        "ヌメリスギタケ": ("numerisugitake", "edibility_reported",
                     "資料には食用との記載があります"),
        "ハタケシメジ": ("hatakesimeji", "edibility_reported",
                    "資料には食用との記載があります"),
        "ハチノスタケ": ("hatinosutake", "unknown",
                    "食毒の区分は確認できていません"),
        "ハツタケ": ("hatutake", "edibility_reported",
                  "資料には食用との記載があります"),
    }
    assert len(manifest) == 34
    assert {name: manifest[name] for name in sixth} == {
        name: data[0] for name, data in sixth.items()
    }

    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    taxonomy = main.load_subject_taxonomy()
    rows = {x["mushroom_id"]: x for x in master["entries"]}
    source_ids = {x["source_id"] for x in sources["sources"]}
    taxonomy_names = {x["canonical_name"] for x in taxonomy["entries"]}
    for name, (ident, status, label) in sixth.items():
        row = rows[ident]
        assert name not in taxonomy_names
        assert row["canonical_name_ja"] == name
        assert row["food_safety"]["status"] == status
        assert set(row["food_safety"]["source_ids"]) <= source_ids
        assert set(row["scientific_name"]["source_ids"]) <= source_ids
        reviewed = detail_ui.SIXTH_FOUR_FOOD_NOTE_REVIEWED[ident]
        assert reviewed[:2] == (name, row["food_safety"]["notes"])
        assert reviewed[2].endswith("。")
        assert label

    ambiguous = [
        "ヌメリスギタケ？", "ハタケシメジ sp.", "ハチノスタケ cf.",
        "ハツタケ（広義）", "ハツタケ？", "不明",
    ]
    observations = [{"alt": name, "src": f"sixth-photo-{i}.jpg"}
                    for i, name in enumerate(list(sixth) + ambiguous)]

    def build(links):
        return portal_data.build_portal_data(
            production_entries=observations, shadow_metadata=[],
            article_metadata={}, exif_cache={}, taxonomy=taxonomy,
            mushroom_master=master, sources=sources,
            production_mode="phase3c_hybrid", cutover_active=True,
            guide_links=links,
        )

    before = build({})
    chosen = {name: data[0] for name, data in sixth.items()}
    after = build(chosen)
    expected = deepcopy(before)
    for observation in expected["observations"]:
        observation["mushroom_master_id"] = chosen.get(observation["gallery_name"])
    for row in expected["subjects"]:
        ident = chosen.get(row["gallery_name"])
        row["mushroom_master_id"] = ident
        row["knowledge_available"] = ident is not None
    expected["summary"]["master_linked_subject_count"] += 4
    expected["summary"]["master_unlinked_subject_count"] -= 4
    assert after == expected

    views = detail_ui.build_detail_views(after)
    for name, (ident, status, label) in sixth.items():
        view = views[name]
        assert view["knowledge"] is not None
        assert view["knowledge"]["sources"]
        assert view["food_safety_status"] == status
        food = next(x for x in view["knowledge"]["rows"] if x["label"] == "食毒情報")
        assert food["value"] == label
        assert food["note"] == detail_ui.SIXTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        markup = detail_ui.render_detail_sections(view)
        assert food["note"] in markup
        assert "このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。" in markup
        assert "食用可否の自己判断には使用しない。" not in markup
    for name in ambiguous:
        assert views[name]["knowledge"] is None

    non_food = views["ハチノスタケ"]
    rendered = detail_ui.render_detail_sections(non_food)
    assert "「不食」" in rendered
    assert "毒性が確認されたとは判断できません" in rendered
    assert "毒性の記載があります" not in rendered


def test_sixth_four_display_notes_require_original_source_and_name():
    """A changed note, Japanese name or ID cannot inherit old reviewed prose."""
    import detail_ui
    import mushroom_knowledge as knowledge

    rows = {x["mushroom_id"]: x
            for x in knowledge.load_mushroom_master()["entries"]}
    for ident in ("numerisugitake", "hatakesimeji", "hatinosutake", "hatutake"):
        original = rows[ident]
        rendered = detail_ui._knowledge(original, {})
        note = next(x for x in rendered["rows"] if x["label"] == "食毒情報")["note"]
        approved = detail_ui.SIXTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        assert note == approved
        edited = deepcopy(original)
        edited["food_safety"]["notes"] += " 新しい未承認の注意事項。"
        changed = detail_ui._knowledge(edited, {})
        changed_note = next(x for x in changed["rows"] if x["label"] == "食毒情報")["note"]
        assert changed_note != approved
        assert "新しい未承認の注意事項" in changed_note
        renamed = deepcopy(original)
        renamed["canonical_name_ja"] = "別の掲載名"
        other = detail_ui._knowledge(renamed, {})
        other_note = next(x for x in other["rows"] if x["label"] == "食毒情報")["note"]
        assert other_note != approved


def test_seventh_four_exact_links_preserve_gallery_and_source_data():
    """Use only previously named gallery subjects; do not infer taxonomy."""
    import detail_ui
    import mushroom_knowledge as knowledge

    manifest = json.loads((Path(__file__).resolve().parents[1] /
                           "data/guide-links.json").read_text(encoding="utf-8"))
    seventh = {
        "ハラタケ": ("haratake", "edibility_reported"),
        "ホコリタケ": ("hokoritake", "edibility_reported"),
        "ムキタケ": ("mukitake", "edibility_reported"),
        "ルリハツタケ": ("rurihatutake", "edibility_reported"),
    }
    assert len(manifest) == 34
    assert {name: manifest[name] for name in seventh} == {
        name: data[0] for name, data in seventh.items()
    }

    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    taxonomy = main.load_subject_taxonomy()
    by_id = {row["mushroom_id"]: row for row in master["entries"]}
    source_ids = {row["source_id"] for row in sources["sources"]}
    taxonomy_names = {row["canonical_name"] for row in taxonomy["entries"]}
    for name, (ident, status) in seventh.items():
        row = by_id[ident]
        assert name not in taxonomy_names
        assert row["canonical_name_ja"] == name
        assert row["food_safety"]["status"] == status
        assert set(row["food_safety"]["source_ids"]) <= source_ids
        assert set(row["scientific_name"]["source_ids"]) <= source_ids
        approved = detail_ui.SEVENTH_FOUR_FOOD_NOTE_REVIEWED[ident]
        assert approved[:2] == (name, row["food_safety"]["notes"])
        assert approved[2].endswith("。")

    ambiguous = [
        "ハラタケ？", "ホコリタケ sp.", "ムキタケ cf.",
        "ルリハツタケ（広義）", "ルリハツタケ？", "不明",
    ]
    original = [{"alt": name, "src": f"seventh-photo-{i}.jpg"}
                for i, name in enumerate(list(seventh) + ambiguous)]

    def build(links):
        return portal_data.build_portal_data(
            production_entries=original, shadow_metadata=[],
            article_metadata={}, exif_cache={}, taxonomy=taxonomy,
            mushroom_master=master, sources=sources,
            production_mode="phase3c_hybrid", cutover_active=True,
            guide_links=links,
        )
    before = build({})
    chosen = {name: item[0] for name, item in seventh.items()}
    after = build(chosen)
    expected = deepcopy(before)
    for obs in expected["observations"]:
        obs["mushroom_master_id"] = chosen.get(obs["gallery_name"])
    for item in expected["subjects"]:
        ident = chosen.get(item["gallery_name"])
        item["mushroom_master_id"] = ident
        item["knowledge_available"] = ident is not None
    expected["summary"]["master_linked_subject_count"] += 4
    expected["summary"]["master_unlinked_subject_count"] -= 4
    assert after == expected

    views = detail_ui.build_detail_views(after)
    for name, (ident, status) in seventh.items():
        view = views[name]
        assert view["knowledge"] is not None
        assert view["knowledge"]["sources"]
        assert view["food_safety_status"] == status
        food = next(x for x in view["knowledge"]["rows"] if x["label"] == "食毒情報")
        assert food["value"] == "資料には食用との記載があります"
        assert food["note"] == detail_ui.SEVENTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        markup = detail_ui.render_detail_sections(view)
        assert food["note"] in markup
        assert "このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。" in markup
    for name in ambiguous:
        assert views[name]["knowledge"] is None

    young = next(row for row in views["ホコリタケ"]["knowledge"]["rows"]
                 if row["label"] == "食毒情報")
    assert "幼時食" in young["note"]
    assert "成長した個体まで食用と判断できるものではありません" in young["note"]


def test_seventh_four_source_changes_do_not_inherit_approved_display_note():
    import detail_ui
    import mushroom_knowledge as knowledge
    by_id = {r["mushroom_id"]: r for r in knowledge.load_mushroom_master()["entries"]}
    for ident in ("haratake", "hokoritake", "mukitake", "rurihatutake"):
        original = by_id[ident]
        expected = detail_ui.SEVENTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        food = next(row for row in detail_ui._knowledge(original, {})["rows"]
                    if row["label"] == "食毒情報")
        assert food["note"] == expected
        changed = deepcopy(original)
        changed["food_safety"]["notes"] += " 新しい未承認の注意情報。"
        changed_note = next(row for row in detail_ui._knowledge(changed, {})["rows"]
                            if row["label"] == "食毒情報")["note"]
        assert changed_note != expected
        assert "新しい未承認の注意情報" in changed_note
        renamed = deepcopy(original)
        renamed["canonical_name_ja"] = "未承認の別名"
        other_note = next(row for row in detail_ui._knowledge(renamed, {})["rows"]
                          if row["label"] == "食毒情報")["note"]
        assert other_note != expected


def test_eighth_four_exact_links_keep_photo_identity_and_source_evidence():
    """Four newly eligible names must link without new identifications or status changes."""
    import detail_ui
    import mushroom_knowledge as knowledge

    manifest = json.loads((Path(__file__).resolve().parents[1] /
                           "data/guide-links.json").read_text(encoding="utf-8"))
    eighth = {
        "アンズタケ": ("anzutake", "edibility_reported",
                  "資料に食用記載と注意情報があります"),
        "カキシメジ": ("kakisimeji", "poisonous_confirmed",
                   "公的・専門資料には毒性の記載があります"),
        "カバイロツルタケ": ("kabairoturutake", "unknown",
                       "食毒の区分は確認できていません"),
        "クサウラベニタケ": ("kusaurabenitake", "poisonous_confirmed",
                       "公的・専門資料には毒性の記載があります"),
    }
    assert len(manifest) == 34
    assert {name: manifest[name] for name in eighth} == {
        name: data[0] for name, data in eighth.items()
    }

    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    taxonomy = main.load_subject_taxonomy()
    by_id = {row["mushroom_id"]: row for row in master["entries"]}
    source_ids = {row["source_id"] for row in sources["sources"]}
    taxonomy_names = {row["canonical_name"] for row in taxonomy["entries"]}
    for name, (ident, expected_status, _) in eighth.items():
        master_row = by_id[ident]
        assert name not in taxonomy_names
        assert master_row["canonical_name_ja"] == name
        assert master_row["food_safety"]["status"] == expected_status
        assert master_row["scientific_name"]["name_status"] == "source_reported"
        assert set(master_row["food_safety"]["source_ids"]) <= source_ids
        assert set(master_row["scientific_name"]["source_ids"]) <= source_ids
        approved = detail_ui.EIGHTH_FOUR_FOOD_NOTE_REVIEWED[ident]
        assert approved[:2] == (name, master_row["food_safety"]["notes"])
        assert approved[2].endswith("。")

    ambiguous = [
        "アンズタケ？", "カキシメジ sp.",
        "カバイロツルタケ cf.", "クサウラベニタケ（広義）",
        "カバイロツルタケ？", "不明",
    ]
    observations = [{"alt": name, "src": f"eighth-photo-{i}.jpg"}
                    for i, name in enumerate(list(eighth) + ambiguous)]

    def build(links):
        return portal_data.build_portal_data(
            production_entries=observations, shadow_metadata=[],
            article_metadata={}, exif_cache={}, taxonomy=taxonomy,
            mushroom_master=master, sources=sources,
            production_mode="phase3c_hybrid", cutover_active=True,
            guide_links=links,
        )

    before = build({})
    chosen = {name: row[0] for name, row in eighth.items()}
    after = build(chosen)
    expected = deepcopy(before)
    for observation in expected["observations"]:
        observation["mushroom_master_id"] = chosen.get(observation["gallery_name"])
    for row in expected["subjects"]:
        ident = chosen.get(row["gallery_name"])
        row["mushroom_master_id"] = ident
        row["knowledge_available"] = ident is not None
    expected["summary"]["master_linked_subject_count"] += 4
    expected["summary"]["master_unlinked_subject_count"] -= 4
    assert after == expected

    views = detail_ui.build_detail_views(after)
    for name, (ident, status, label) in eighth.items():
        view = views[name]
        assert view["knowledge"] is not None
        assert view["knowledge"]["sources"]
        assert view["food_safety_status"] == status
        food = next(x for x in view["knowledge"]["rows"] if x["label"] == "食毒情報")
        assert food["value"] == label
        assert food["note"] == detail_ui.EIGHTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        markup = detail_ui.render_detail_sections(view)
        assert label in markup
        assert food["note"] in markup
        assert "このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。" in markup
        assert "食用可否の自己判断には使用しない。" not in markup
    for name in ambiguous:
        assert views[name]["knowledge"] is None

    anzutake = next(x for x in views["アンズタケ"]["knowledge"]["rows"] if x["label"] == "食毒情報")
    assert "アンズタケ（注意）" in anzutake["note"]
    assert "注意が必要な理由までは確認できない" in anzutake["note"]
    kabairo = next(x for x in views["カバイロツルタケ"]["knowledge"]["rows"] if x["label"] == "食毒情報")
    assert "生食すると毒だといわれる" in kabairo["note"]
    assert "加熱すれば安全という意味でもありません" in kabairo["note"]
    for name in ("カキシメジ", "クサウラベニタケ"):
        food = next(x for x in views[name]["knowledge"]["rows"] if x["label"] == "食毒情報")
        assert "嘔吐や下痢" in food["note"]
        assert "個体の種を特定できるわけではありません" in food["note"]


def test_eighth_four_reviewed_copy_fails_closed_for_changed_source_and_name():
    """Reviewed display and caution label require the original exact source note."""
    import detail_ui
    import mushroom_knowledge as knowledge

    by_id = {row["mushroom_id"]: row
             for row in knowledge.load_mushroom_master()["entries"]}
    for ident in ("anzutake", "kakisimeji", "kabairoturutake", "kusaurabenitake"):
        original = by_id[ident]
        approved = detail_ui.EIGHTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        original_food = next(row for row in detail_ui._knowledge(original, {})["rows"]
                             if row["label"] == "食毒情報")
        assert original_food["note"] == approved
        if ident == "anzutake":
            assert original_food["value"] == detail_ui.EIGHTH_ANZUTAKE_WARNING_LABEL
        changed = deepcopy(original)
        changed["food_safety"]["notes"] += " 新しい未承認情報。"
        changed_food = next(row for row in detail_ui._knowledge(changed, {})["rows"]
                            if row["label"] == "食毒情報")
        assert changed_food["note"] != approved
        assert "新しい未承認情報" in changed_food["note"]
        if ident == "anzutake":
            assert changed_food["value"] == "資料には食用との記載があります"
        renamed = deepcopy(original)
        renamed["canonical_name_ja"] = "未承認の別名"
        renamed_food = next(row for row in detail_ui._knowledge(renamed, {})["rows"]
                            if row["label"] == "食毒情報")
        assert renamed_food["note"] != approved
        if ident == "anzutake":
            assert renamed_food["value"] != detail_ui.EIGHTH_ANZUTAKE_WARNING_LABEL


def test_ninth_four_exact_links_preserve_photo_identity_and_cautions():
    """Four existing subjects only; '要注意' and '不食' are not toxic diagnoses."""
    import detail_ui
    import mushroom_knowledge as knowledge

    manifest = json.loads((Path(__file__).resolve().parents[1] /
                           "data/guide-links.json").read_text(encoding="utf-8"))
    ninth = {
        "クロハツ": ("kurohatu", "unknown",
                  "資料には食用を避けるよう注意があります"),
        "コツブタケ": ("kotubutake", "unknown",
                    "食毒の区分は確認できていません"),
        "チャナメツムタケ": ("cyanamemututake", "edibility_reported",
                       "資料には食用との記載があります"),
        "ツチグリ": ("tutiguri", "unknown",
                  "食毒の区分は確認できていません"),
    }
    assert len(manifest) == 34
    assert {name: manifest[name] for name in ninth} == {
        name: val[0] for name, val in ninth.items()
    }

    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    taxonomy = main.load_subject_taxonomy()
    by_id = {row["mushroom_id"]: row for row in master["entries"]}
    source_ids = {row["source_id"] for row in sources["sources"]}
    taxonomy_names = {row["canonical_name"] for row in taxonomy["entries"]}
    for name, (ident, status, _) in ninth.items():
        row = by_id[ident]
        assert name not in taxonomy_names
        assert row["canonical_name_ja"] == name
        assert row["food_safety"]["status"] == status
        assert set(row["food_safety"]["source_ids"]) <= source_ids
        assert set(row["scientific_name"]["source_ids"]) <= source_ids
        approved = detail_ui.NINTH_FOUR_FOOD_NOTE_REVIEWED[ident]
        assert approved[:2] == (name, row["food_safety"]["notes"])
        assert approved[2].endswith("。")

    ambiguous = [
        "クロハツ？", "コツブタケ sp.", "チャナメツムタケ cf.",
        "ツチグリ（広義）", "ツチグリ？", "不明",
    ]
    production_entries = [{"alt": name, "src": f"ninth-photo-{i}.jpg"}
                          for i, name in enumerate(list(ninth) + ambiguous)]

    def build(links):
        return portal_data.build_portal_data(
            production_entries=production_entries, shadow_metadata=[],
            article_metadata={}, exif_cache={}, taxonomy=taxonomy,
            mushroom_master=master, sources=sources,
            production_mode="phase3c_hybrid", cutover_active=True,
            guide_links=links,
        )

    original = build({})
    chosen = {name: data[0] for name, data in ninth.items()}
    updated = build(chosen)
    expected = deepcopy(original)
    for observation in expected["observations"]:
        observation["mushroom_master_id"] = chosen.get(observation["gallery_name"])
    for subject in expected["subjects"]:
        ident = chosen.get(subject["gallery_name"])
        subject["mushroom_master_id"] = ident
        subject["knowledge_available"] = ident is not None
    expected["summary"]["master_linked_subject_count"] += 4
    expected["summary"]["master_unlinked_subject_count"] -= 4
    assert updated == expected
    assert [(o["src"], o["gallery_name"], o["classification"])
            for o in updated["observations"]] == [
            (o["src"], o["gallery_name"], o["classification"])
            for o in original["observations"]]

    views = detail_ui.build_detail_views(updated)
    for name, (ident, status, label) in ninth.items():
        view = views[name]
        assert view["knowledge"] is not None
        assert view["knowledge"]["sources"]
        assert view["food_safety_status"] == status
        food = next(x for x in view["knowledge"]["rows"] if x["label"] == "食毒情報")
        assert food["value"] == label
        assert food["note"] == detail_ui.NINTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        markup = detail_ui.render_detail_sections(view)
        assert food["note"] in markup
        assert "このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。" in markup
        assert "食用可否の自己判断には使用しない。" not in markup
    for name in ambiguous:
        assert views[name]["knowledge"] is None

    caution = next(x for x in views["クロハツ"]["knowledge"]["rows"]
                   if x["label"] == "食毒情報")
    assert "要注意" in caution["note"]
    assert "食用にすべきでない" in caution["note"]
    assert "加熱すれば安全という意味ではありません" in caution["note"]
    for name in ("コツブタケ", "ツチグリ"):
        food = next(x for x in views[name]["knowledge"]["rows"]
                    if x["label"] == "食毒情報")
        assert "「不食」" in food["note"]
        assert "毒性が確認されたとは判断できません" in food["note"]
        assert "毒性の記載があります" not in food["note"]


def test_ninth_four_reviewed_notes_fall_back_if_source_or_name_changes():
    """Human-approved prose and special headline never survive new source facts."""
    import detail_ui
    import mushroom_knowledge as knowledge

    by_id = {x["mushroom_id"]: x
             for x in knowledge.load_mushroom_master()["entries"]}
    for ident in ("kurohatu", "kotubutake", "cyanamemututake", "tutiguri"):
        original = by_id[ident]
        approved = detail_ui.NINTH_FOUR_FOOD_NOTE_REVIEWED[ident][2]
        food = next(row for row in detail_ui._knowledge(original, {})["rows"]
                    if row["label"] == "食毒情報")
        assert food["note"] == approved
        if ident == "kurohatu":
            assert food["value"] == detail_ui.NINTH_KUROHATU_WARNING_LABEL
        altered = deepcopy(original)
        altered["food_safety"]["notes"] += " 未承認の追加報告。"
        changed_food = next(row for row in detail_ui._knowledge(altered, {})["rows"]
                            if row["label"] == "食毒情報")
        assert changed_food["note"] != approved
        assert "未承認の追加報告" in changed_food["note"]
        if ident == "kurohatu":
            assert changed_food["value"] == "食毒の区分は確認できていません"
        renamed = deepcopy(original)
        renamed["canonical_name_ja"] = "別の和名"
        renamed_food = next(row for row in detail_ui._knowledge(renamed, {})["rows"]
                            if row["label"] == "食毒情報")
        assert renamed_food["note"] != approved
        if ident == "kurohatu":
            assert renamed_food["value"] != detail_ui.NINTH_KUROHATU_WARNING_LABEL


def test_tenth_two_exact_links_protect_gallery_and_cautious_source_notes():
    """Last two photo-backed exact name matches: add knowledge, not identification."""
    import detail_ui
    import mushroom_knowledge as knowledge

    manifest = json.loads((Path(__file__).resolve().parents[1] /
                           "data/guide-links.json").read_text(encoding="utf-8"))
    tenth = {
        "ナラタケ": ("naratake", "edibility_reported",
                  "資料に食用記載と注意情報があります"),
        "マンネンタケ": ("mannentake", "unknown",
                    "資料には薬用・鑑賞との記載があります"),
    }
    assert len(manifest) == 34
    assert {name: manifest[name] for name in tenth} == {
        name: data[0] for name, data in tenth.items()
    }

    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    taxonomy = main.load_subject_taxonomy()
    by_id = {x["mushroom_id"]: x for x in master["entries"]}
    source_ids = {x["source_id"] for x in sources["sources"]}
    taxonomy_names = {x["canonical_name"] for x in taxonomy["entries"]}
    for name, (ident, status, _) in tenth.items():
        row = by_id[ident]
        assert name not in taxonomy_names
        assert row["canonical_name_ja"] == name
        assert row["food_safety"]["status"] == status
        assert row["scientific_name"]["name_status"] == "source_reported"
        assert set(row["food_safety"]["source_ids"]) <= source_ids
        assert set(row["scientific_name"]["source_ids"]) <= source_ids
        approved = detail_ui.TENTH_TWO_FOOD_NOTE_REVIEWED[ident]
        assert approved[:2] == (name, row["food_safety"]["notes"])
        assert approved[2].endswith("。")

    ambiguous = [
        "ナラタケ？", "マンネンタケ sp.", "ナラタケ cf.",
        "マンネンタケ（広義）", "マンネンタケ？", "不明",
    ]
    originals = [{"alt": name, "src": f"tenth-photo-{i}.jpg"}
                 for i, name in enumerate(list(tenth) + ambiguous)]
    def build(links):
        return portal_data.build_portal_data(
            production_entries=originals, shadow_metadata=[],
            article_metadata={}, exif_cache={}, taxonomy=taxonomy,
            mushroom_master=master, sources=sources,
            production_mode="phase3c_hybrid", cutover_active=True,
            guide_links=links,
        )
    before = build({})
    chosen = {name: data[0] for name, data in tenth.items()}
    after = build(chosen)
    expected = deepcopy(before)
    for obs in expected["observations"]:
        obs["mushroom_master_id"] = chosen.get(obs["gallery_name"])
    for subject in expected["subjects"]:
        ident = chosen.get(subject["gallery_name"])
        subject["mushroom_master_id"] = ident
        subject["knowledge_available"] = ident is not None
    expected["summary"]["master_linked_subject_count"] += 2
    expected["summary"]["master_unlinked_subject_count"] -= 2
    assert after == expected

    views = detail_ui.build_detail_views(after)
    for name, (ident, status, label) in tenth.items():
        view = views[name]
        assert view["knowledge"] is not None
        assert view["knowledge"]["sources"]
        assert view["food_safety_status"] == status
        food = next(x for x in view["knowledge"]["rows"] if x["label"] == "食毒情報")
        assert food["value"] == label
        assert food["note"] == detail_ui.TENTH_TWO_FOOD_NOTE_REVIEWED[ident][2]
        markup = detail_ui.render_detail_sections(view)
        assert label in markup
        assert food["note"] in markup
        assert "このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。" in markup
    for name in ambiguous:
        assert views[name]["knowledge"] is None

    naratake = next(x for x in views["ナラタケ"]["knowledge"]["rows"]
                    if x["label"] == "食毒情報")
    assert "茨城県" in naratake["note"]
    assert "消化不良" in naratake["note"]
    assert "安全性を判断することはできません" in naratake["note"]
    mannentake = next(x for x in views["マンネンタケ"]["knowledge"]["rows"]
                      if x["label"] == "食毒情報")
    assert "薬用、鑑賞" in mannentake["note"]
    assert "薬としての効果" in mannentake["note"]
    assert "安全性を示すものではありません" in mannentake["note"]


def test_tenth_two_reviewed_copy_requires_original_name_note_and_status():
    import detail_ui
    import mushroom_knowledge as knowledge

    by_id = {x["mushroom_id"]: x
             for x in knowledge.load_mushroom_master()["entries"]}
    for ident in ("naratake", "mannentake"):
        orig = by_id[ident]
        expected = detail_ui.TENTH_TWO_FOOD_NOTE_REVIEWED[ident][2]
        food = next(x for x in detail_ui._knowledge(orig, {})["rows"]
                    if x["label"] == "食毒情報")
        assert food["note"] == expected
        changed = deepcopy(orig)
        changed["food_safety"]["notes"] += " 未承認の追加情報。"
        updated_food = next(x for x in detail_ui._knowledge(changed, {})["rows"]
                            if x["label"] == "食毒情報")
        assert updated_food["note"] != expected
        assert "未承認の追加情報" in updated_food["note"]
        if ident == "naratake":
            assert updated_food["value"] == "資料には食用との記載があります"
        else:
            assert updated_food["value"] == "食毒の区分は確認できていません"
        renamed = deepcopy(orig)
        renamed["canonical_name_ja"] = "未確認の別名"
        renamed_food = next(x for x in detail_ui._knowledge(renamed, {})["rows"]
                            if x["label"] == "食毒情報")
        assert renamed_food["note"] != expected
        assert renamed_food["value"] != food["value"]

    # Reclassifying food status without source review must drop special headline.
    naratake = deepcopy(by_id["naratake"])
    naratake["food_safety"]["status"] = "unknown"
    naratake_food = next(x for x in detail_ui._knowledge(naratake, {})["rows"]
                         if x["label"] == "食毒情報")
    assert naratake_food["value"] == "食毒の区分は確認できていません"
    mannentake = deepcopy(by_id["mannentake"])
    mannentake["food_safety"]["status"] = "edibility_reported"
    mannentake_food = next(x for x in detail_ui._knowledge(mannentake, {})["rows"]
                           if x["label"] == "食毒情報")
    assert mannentake_food["value"] == "資料には食用との記載があります"


@pytest.mark.parametrize("invalid", [
    {"アミタケ": "not-in-master"},
    {"アミタケ？": "amitake"},
    {"アミタケ sp.": "amitake"},
    {"アミタケ cf.": "amitake"},
    {"アミタケ(広義)": "amitake"},
    {"菌名": "fungus-id"},  # already exists in subject taxonomy
    [],
])
def test_standalone_guide_links_fail_closed_on_unknown_or_ambiguous_data(invalid):
    if isinstance(invalid, dict) and "菌名" not in invalid:
        taxonomy = {"version": 1, "entries": []}
        master = {"version": 1, "entries": [{"mushroom_id": "amitake", "canonical_name_ja": "アミタケ"}]}
    else:
        taxonomy, master, _ = references()
    with pytest.raises(ValueError):
        portal_data.build_portal_data(
            production_entries=[{"alt": "菌名", "src": "photo.jpg"}],
            shadow_metadata=[], article_metadata={}, exif_cache={},
            taxonomy=taxonomy, mushroom_master=master, sources={"version": 1, "sources": []},
            production_mode="phase3c_hybrid", cutover_active=True, guide_links=invalid
        )


def test_classification_statuses_use_existing_provenance_only():
    cases = [
        ("不明", shadow(gallery_name="不明"), "confirmed_mushroom_identity_uncertain"),
        ("旧名", shadow(gallery_name="菌名", legacy_alt="旧名"), "manual_review_name_conflict"),
        ("菌名", shadow(subject_type="review"), "legacy_review"),
        ("菌名", shadow(detected_label=None), "legacy_undetected"),
        ("菌名", None, "legacy_shadow_missing"),
    ]
    for name, row, expected in cases:
        result = build(entries=[{"alt": name, "src": "image.jpg"}],
                       shadows=[] if row is None else [row])
        assert result["observations"][0]["classification"]["status"] == expected


def test_matching_exact_legacy_gallery_fallback_and_missing():
    entries = [
        {"alt": "菌名", "src": "gallery.jpg"},
        {"alt": "旧名", "src": "legacy.jpg"},
        {"alt": "別名", "src": "fallback.jpg"},
        {"alt": "なし", "src": "missing.jpg"},
    ]
    shadows = [shadow("gallery.jpg"), shadow("legacy.jpg"), shadow("fallback.jpg")]
    result = build(entries, shadows)
    assert [row["shadow_match_status"] for row in result["observations"]] == [
        "exact_gallery_name", "exact_legacy_alt", "src_only_fallback", "shadow_missing"
    ]


def test_matching_preserves_shadow_order_and_never_uses_non_mushroom():
    entries = [{"alt": "菌名", "src": "same.jpg"}] * 2
    non_mushroom = shadow("same.jpg", subject_type="non_mushroom")
    first = shadow("same.jpg", path="first.html")
    second = shadow("same.jpg", path="second.html")
    rows = build(entries, [non_mushroom, first, second])["observations"]
    assert [row["article"]["article_path"] for row in rows] == ["first.html", "second.html"]


def test_builder_does_not_mutate_inputs():
    entries, shadows = [{"alt": "菌名", "src": "image.jpg"}], [shadow()]
    taxonomy, master, sources = references()
    values = [entries, shadows, {}, {}, taxonomy, master, sources]
    before = deepcopy(values)
    build(entries, shadows, refs=(taxonomy, master, sources))
    assert values == before


def test_export_failure_and_status_save_failure_are_isolated(monkeypatch):
    entries = [{"alt": "菌名", "src": "image.jpg"}]
    saved = []
    monkeypatch.setattr(main, "load_mushroom_master", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(main, "save_json", lambda path, value: saved.append((path, value)))
    status = main.export_portal_data(
        production_entries=entries, shadow_metadata=[], article_metadata={},
        exif_cache={}, taxonomy={"version": 1, "entries": []},
        production_mode="phase3c_hybrid",
    )
    assert status["build_ok"] is False
    assert saved[0][1]["production_image_count"] == 1
    assert entries == [{"alt": "菌名", "src": "image.jpg"}]
    monkeypatch.setattr(main, "save_json", lambda *args: (_ for _ in ()).throw(OSError("disk")))
    main.export_portal_data(
        production_entries=entries, shadow_metadata=[], article_metadata={},
        exif_cache={}, taxonomy=None, production_mode="legacy_fallback",
    )

def test_four_existing_subjects_link_to_real_master_and_cited_detail_sections():
    """Exact name-only joins preserve all four gallery labels and photo references."""
    import detail_ui
    import mushroom_knowledge as knowledge

    links = {
        "ヤマドリタケモドキ": "yamadoritakemodoki",
        "シイタケ": "shiitake",
        "ベニテングタケ": "benitengutake",
        "ドクヤマドリ": "dokuyamadori",
    }
    taxonomy = main.load_subject_taxonomy()
    master = knowledge.load_mushroom_master()
    sources = knowledge.load_sources()
    entries = {row["canonical_name"]: row for row in taxonomy["entries"]}
    master_by_id = {row["mushroom_id"]: row for row in master["entries"]}
    source_ids = {row["source_id"] for row in sources["sources"]}
    for name, mushroom_id in links.items():
        assert entries[name]["subject_type"] == "mushroom"
        assert entries[name]["mushroom_master_id"] == mushroom_id
        assert entries[name]["verification_status"] == "project_seed"
        assert master_by_id[mushroom_id]["canonical_name_ja"] == name
        assert master_by_id[mushroom_id]["scientific_name"]["source_ids"]
        assert set(master_by_id[mushroom_id]["scientific_name"]["source_ids"]) <= source_ids

    photo_rows = [{"alt": name, "src": f"linked-photo-{i}.jpg"}
                  for i, name in enumerate(links)]
    shadows = [shadow(src=f"linked-photo-{i}.jpg", gallery_name=name,
                      legacy_alt=name, detected_label=name, path=f"linked-article-{i}.html")
               for i, name in enumerate(links)]
    result = portal_data.build_portal_data(
        production_entries=photo_rows, shadow_metadata=shadows,
        article_metadata={}, exif_cache={}, taxonomy=taxonomy,
        mushroom_master=master, sources=sources,
        production_mode="phase3c_hybrid", cutover_active=True,
    )
    assert [(row["gallery_name"], row["src"]) for row in result["observations"]] == [
        (row["alt"], row["src"]) for row in photo_rows
    ]
    assert result["summary"]["master_linked_subject_count"] == 4
    views = detail_ui.build_detail_views(result)
    for name, mushroom_id in links.items():
        subject = next(row for row in result["subjects"] if row["gallery_name"] == name)
        assert subject["mushroom_master_id"] == mushroom_id
        assert subject["knowledge_available"] is True
        assert views[name]["knowledge"] is not None
        assert views[name]["knowledge"]["sources"]
        html = detail_ui.render_detail_sections(views[name])
        assert '<section class="knowledge-panel">' in html
        assert "出典を見る" in html
        assert "このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。" in html
        assert "毒性についての記載がなくても、安全とは限りません。" in html
