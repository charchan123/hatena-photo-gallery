import copy

import main
import pytest
from detail_ui import build_detail_views, render_detail_sections


def fixture_portal():
    master = {
        "mushroom_id": "linked", "canonical_name_ja": "別名", "name_ja_sources": ["s1"],
        "scientific_name": {"value": "Fungus <test>", "name_status": "source_reported", "source_ids": ["s1"]},
        "taxonomy": {"family": {"value": "科", "source_ids": ["s1"]},
                     "genus": {"value": "属", "source_ids": ["missing"]}},
        "features": {"summary": "特徴", "source_ids": ["s1"]},
        "habitat": {"summary": "林内", "source_ids": ["s2"]},
        "season": {"summary": "夏", "source_ids": ["s2"]},
        "food_safety": {"status": "edibility_reported", "notes": "注<&", "source_ids": ["s1"]},
        "toxins": [{"name": "成分A", "source_ids": ["s2"]}],
    }
    article = lambda aid, published, title="記事<&", url="https://example.test/?a=1&b=2": {
        "article_id": aid, "article_path": f"/{aid}" if aid else None, "url": url,
        "title": title, "published": published, "updated": "2099-01-01T00:00:00Z",
    }
    return {
        "version": 1,
        "subjects": [
            {"gallery_name": "リンク名？", "mushroom_master_id": "linked"},
            {"gallery_name": "別名", "mushroom_master_id": None},
        ],
        "observations": [
            {"gallery_name": "リンク名？", "article": article("old", "2025-01-01T00:00:00Z")},
            {"gallery_name": "リンク名？", "article": article("new", "2026-01-01T00:00:00Z")},
            {"gallery_name": "リンク名？", "article": article("new", "2026-01-01T00:00:00Z")},
            {"gallery_name": "リンク名？", "article": article("bad", "invalid")},
            {"gallery_name": "別名", "article": article("only", None, url=None)},
            {"gallery_name": "other", "article": article("no", "2099-01-01T00:00:00Z")},
        ],
        "reference_data": {
            "mushroom_master": {"version": 1, "entries": [master]},
            "sources": {"version": 1, "sources": [
                {"source_id": "s1", "organization": "組織", "title": "資料1", "url": "https://source.test/1"},
                {"source_id": "s2", "organization": "組織2", "title": "資料2", "url": None},
            ]},
            "subject_taxonomy": {},
        },
    }


def test_schema_and_explicit_master_link_only():
    with pytest.raises(ValueError):
        build_detail_views({"version": 2})
    views = build_detail_views(fixture_portal())
    assert views["リンク名？"]["knowledge"] is not None
    assert views["別名"]["knowledge"] is None  # canonical-name equality is irrelevant
    assert views["別名"]["articles"]


def test_fields_safety_provenance_and_escaping():
    rendered = render_detail_sections(build_detail_views(fixture_portal())["リンク名？"])
    for value in ("学名", "科", "属", "特徴", "生育環境", "資料に記載された発生時期", "資料に食用の記載あり", "成分A"):
        assert value in rendered
    assert "Fungus &lt;test&gt;" in rendered and "資料記載名" in rendered
    assert ">安全<" not in rendered and "食べられる" not in rendered
    assert "採取・調理・飲食の判断には使用しないでください" in rendered
    assert "情報がないことは安全を意味しません" in rendered
    assert rendered.count("資料1") == 1 and rendered.count("資料2") == 1
    assert "missing" not in rendered and "https://source.test/1" in rendered
    assert 'target="_blank" rel="noopener noreferrer"' in rendered
    assert "組織2：資料2</li>" in rendered
    assert "注&lt;&amp;" in rendered and "None" not in rendered


@pytest.mark.parametrize("status, wording", [
    ("poisonous_confirmed", "公的・専門資料に毒性の記載あり"),
    ("unknown", "食毒情報は未確認"),
])
def test_other_food_safety_wording(status, wording):
    data = fixture_portal()
    data["reference_data"]["mushroom_master"]["entries"][0]["food_safety"]["status"] = status
    assert wording in render_detail_sections(build_detail_views(data)["リンク名？"])


def test_articles_exact_dedup_chronology_and_links():
    view = build_detail_views(fixture_portal())["リンク名？"]
    assert [row["published"] for row in view["articles"]] == [
        "2026-01-01T00:00:00Z", "2025-01-01T00:00:00Z", "invalid"]
    rendered = render_detail_sections(view)
    assert rendered.count("記事&lt;&amp;") == 3
    assert 'target="_top"' in rendered and "2099" not in rendered
    unlinked = render_detail_sections(build_detail_views(fixture_portal())["別名"])
    assert "knowledge-panel" not in unlinked and "subject-records" in unlinked
    assert 'target="_top"' not in unlinked


def test_missing_fields_do_not_render_empty_rows():
    data = fixture_portal()
    master = data["reference_data"]["mushroom_master"]["entries"][0]
    master["scientific_name"]["value"] = None
    master["taxonomy"]["family"]["value"] = ""
    rendered = render_detail_sections(build_detail_views(data)["リンク名？"])
    assert ">学名<" not in rendered and ">科<" not in rendered and "None" not in rendered


def test_generate_gallery_optional_detail_integration(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "copy_shared_assets", lambda: None)
    entries = [{"alt": "リンク名？", "src": "image"}, {"alt": "別名", "src": "image2"}]
    grouped = main.generate_gallery(entries, {}, detail_views=build_detail_views(fixture_portal()))
    linked = (tmp_path / f"{main.safe_filename('リンク名？')}.html").read_text()
    unlinked = (tmp_path / "別名.html").read_text()
    assert grouped == {"リンク名？": ["image"], "別名": ["image2"]}
    assert linked.index("class='gallery'") < linked.index("knowledge-panel") < linked.index("aiuo-links")
    assert linked.count("gallery-item") == 1 and "thumb-fav" in linked
    assert "lightgallery@2.8.3" in linked and "assets/detail.css" in linked
    assert "knowledge-panel" not in unlinked and "subject-records" in unlinked
    main.generate_gallery(entries, {}, detail_views=None)
    assert "knowledge-panel" not in (tmp_path / f"{main.safe_filename('リンク名？')}.html").read_text()


def test_failure_isolation_and_no_stale_read(monkeypatch):
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: (_ for _ in ()).throw(AssertionError("stale")))
    assert main.build_detail_views_if_fresh({"build_ok": False}) == {}
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: {"version": 1})
    monkeypatch.setattr(main, "build_detail_views", lambda portal: (_ for _ in ()).throw(RuntimeError("boom")))
    assert main.build_detail_views_if_fresh({"build_ok": True}) == {}


def test_source_data_is_not_mutated():
    data = fixture_portal(); original = copy.deepcopy(data)
    build_detail_views(data)
    assert data == original
