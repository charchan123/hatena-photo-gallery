import copy
import json

import main
import pytest
from detail_ui import build_detail_views, reader_facing_food_note, render_detail_sections


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
    assert "Fungus &lt;test&gt;" in rendered and "出典資料に記載された学名" in rendered
    assert "資料記載名" not in rendered
    assert ">安全<" not in rendered and "食べられる" not in rendered
    assert "採取・調理・飲食の判断には使用しないでください" in rendered
    assert "情報がないことは安全を意味しません" in rendered
    assert rendered.count("資料1") == 1 and rendered.count("資料2") == 1
    assert "missing" not in rendered and "https://source.test/1" in rendered
    assert 'target="_blank" rel="noopener noreferrer"' in rendered
    assert "組織2：資料2</li>" in rendered
    assert "注&lt;&amp;" in rendered and "None" not in rendered


def test_name_only_source_is_not_rendered_as_provenance():
    data = fixture_portal()
    master = data["reference_data"]["mushroom_master"]["entries"][0]
    master["canonical_name_ja"] = "表示しない和名"
    master["name_ja_sources"] = ["s_name_only"]
    data["reference_data"]["sources"]["sources"].append({
        "source_id": "s_name_only",
        "organization": "名前専用組織",
        "title": "名前専用資料",
        "url": "https://source.test/name-only?x=1&y=2",
    })

    view = build_detail_views(data)["リンク名？"]
    assert all(row["label"] != "和名" for row in view["knowledge"]["rows"])
    rendered = render_detail_sections(view)
    assert "表示しない和名" not in rendered
    assert "s_name_only" not in rendered and "名前専用資料" not in rendered
    assert rendered.count("資料1") == 1 and rendered.count("資料2") == 1
    assert "Fungus &lt;test&gt;" in rendered
    assert 'target="_blank" rel="noopener noreferrer"' in rendered


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
    assert "記事公開日：2026年1月1日" in rendered
    assert "記事公開日：不明" in rendered


def test_reader_facing_food_notes_and_duplicate_suppression():
    assert reader_facing_food_note(
        "石川県の公的図鑑が「食」と記載しているというsource report。projectによる安全判定ではない。"
    ) == ("石川県の公的図鑑では「食」と記載されています。"
          "これは出典資料の記載を示すもので、本サイトが食用可否を判定したものではありません。")
    assert reader_facing_food_note(
        "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。"
    ) is None
    for note in ("幼時食というsource report。projectの判断ではない。",
                 "高山帯個体との同一性にはDNA解析が必要。",
                 "アルコール併用時の中毒症状。"):
        rendered = reader_facing_food_note(note)
        assert rendered
        assert not any(term in rendered for term in
                       ("source report", "project", "source", "food safety", "schema", "edibility status"))
    assert "幼時食" in reader_facing_food_note("幼時食というsource report。")
    assert "DNA解析" in reader_facing_food_note("同一性にはDNA解析が必要。")
    assert "アルコール" in reader_facing_food_note("アルコール併用時の中毒症状。")

    data = fixture_portal()
    data["reference_data"]["mushroom_master"]["entries"][0]["food_safety"]["notes"] = (
        "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。"
    )
    output = render_detail_sections(build_detail_views(data)["リンク名？"])
    assert "食用可否の自己判断には使用しない" not in output
    assert "採取・調理・飲食の判断には使用しないでください" in output


def test_all_repository_food_notes_hide_internal_terms_and_preserve_limits():
    master = json.loads(open("data/mushroom-master.json", encoding="utf-8").read())
    rendered = {
        row["canonical_name_ja"]: reader_facing_food_note((row.get("food_safety") or {}).get("notes"))
        for row in master["entries"]
    }
    internal_terms = ("source report", "project", "source", "food safety", "schema", "edibility status")
    assert all(not any(term in note for term in internal_terms)
               for note in rendered.values() if note is not None)
    assert "幼時食" in rendered["ノウタケ"]
    assert "DNA解析" in rendered["ツバアブラシメジ"]
    assert "アルコール" in rendered["ホテイシメジ"]
    assert "毒成分名" in rendered["オオワライタケ"]
    assert "安全を意味しない" in rendered["ウコンハツ"]


@pytest.mark.parametrize("count, expected", [(1, None), (5, None), (6, 1), (10, 5)])
def test_article_history_collapse(count, expected):
    data = fixture_portal()
    data["observations"] = [{
        "gallery_name": "リンク名？",
        "article": {"article_id": str(index), "title": f"記事{index}",
                    "url": None if index == count - 1 else f"https://example.test/{index}",
                    "published": f"2026-01-{count-index:02d}T00:00:00Z"},
    } for index in range(count)]
    view = build_detail_views(data)["リンク名？"]
    output = render_detail_sections(view)
    assert [article["title"] for article in view["articles"]] == [f"記事{i}" for i in range(count)]
    assert all(f"記事{i}" in output for i in range(count))
    if expected is None:
        assert "subject-record-more" not in output
    else:
        assert f"過去の観察記録をさらに見る（{expected}件）" in output
        assert output.count('target="_top"') == count - 1


@pytest.mark.parametrize("reason", [
    "manual_review_name_conflict", "confirmed_mushroom_identity_uncertain", "legacy_review",
])
def test_explicit_review_marks_unlinked_knowledge_pending(reason):
    data = fixture_portal()
    subject = data["subjects"][1]
    subject["classification_counts"] = {reason: 1}
    view = build_detail_views(data)["別名"]
    assert view["knowledge_pending"] is True
    assert "図鑑情報は現在整理中です" in render_detail_sections(view)


def test_pending_uses_explicit_data_not_name_punctuation():
    data = fixture_portal()
    data["subjects"][1]["gallery_name"] = "テスト？"
    data["observations"][4]["gallery_name"] = "テスト？"
    plain = build_detail_views(data)["テスト？"]
    assert plain["knowledge_pending"] is False
    assert "knowledge-pending" not in render_detail_sections(plain)

    data["subjects"][1]["taxonomy"] = {"subject_type": "mushroom"}
    pending = build_detail_views(data)["テスト？"]
    assert pending["knowledge_pending"] is True
    assert "knowledge-pending" in render_detail_sections(pending)
    assert build_detail_views(data)["リンク名？"]["knowledge_pending"] is False


def test_empty_articles_have_no_section_and_css_contract():
    view = {"knowledge": None, "knowledge_pending": False, "articles": []}
    assert "subject-records" not in render_detail_sections(view)
    css = open("assets/detail.css", encoding="utf-8").read()
    assert ".subject-record-more" in css
    assert ".subject-record-more summary" in css
    assert ".knowledge-pending" in css
    assert "@media (max-width: 600px)" in css


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
