from copy import deepcopy

import main
import portal_data


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
        "updated": "2026-09-20T01:00:00Z", "categories": ["キノコ"],
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
