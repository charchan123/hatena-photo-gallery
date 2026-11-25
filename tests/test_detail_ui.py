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


def test_sourced_guide_supplements_fill_empty_rows_without_overriding_master(tmp_path):
    portal = fixture_portal()
    master = portal["reference_data"]["mushroom_master"]["entries"][0]
    master["habitat"]["summary"] = None
    source = {"organization": "出典機関", "title": "資料", "url": "https://source.test/supplement"}
    entry = {
        "expected": {"name": "別名", "scientific": "Fungus <test>", "family": "科", "genus": "属"},
        "fields": {
            "features": {"value": "置換候補", "sources": ["ref"]},
            "habitat": {"value": "広葉樹林の地上", "sources": ["ref"]},
            "season": {"value": "春", "sources": ["missing"]},
            "name_reference": {"value": "分類に関する資料", "sources": ["ref"]},
            "food_reference": {
                "value": "相談資料の記録", "sources": ["ref"],
                "expected_status": "edibility_reported", "expected_notes": "注<&",
            },
        },
    }
    spec = {"version": 1, "entries": {"linked": entry}, "sources": {"ref": source}}
    display = tmp_path / "display.json"
    display.write_text(json.dumps(spec), encoding="utf-8")

    def read_panel():
        views = build_detail_views(portal, taxonomy_display_path=display)
        assert views["別名"]["knowledge"] is None
        return views["リンク名？"]["knowledge"]

    before = copy.deepcopy(portal)
    panel = read_panel()
    rows = {r["label"]: r["value"] for r in panel["rows"]}
    assert rows["特徴"] == "特徴"
    assert rows["生育環境"] == "広葉樹林の地上"
    assert rows["資料に記載された発生時期"] == "夏"
    assert rows["学名の資料比較"] == "分類に関する資料"
    assert rows["食毒資料の補足"] == "相談資料の記録"
    assert [s["url"] for s in panel["sources"]].count(source["url"]) == 1
    assert portal == before

    for key, value in (("notes", "審査後の記録"), ("status", "unknown")):
        original = master["food_safety"][key]
        master["food_safety"][key] = value
        assert all(row["label"] != "食毒資料の補足" for row in read_panel()["rows"])
        master["food_safety"][key] = original

    master["scientific_name"]["value"] = "Fungus updated"
    assert [row["label"] for row in read_panel()["rows"]] == [
        "学名", "科名", "属名", "生態", "特徴", "資料に記載された発生時期", "食毒情報", "資料に記載された成分",
    ]


def test_fields_safety_provenance_and_escaping():
    rendered = render_detail_sections(build_detail_views(fixture_portal())["リンク名？"])
    for value in ("学名", "科", "属", "特徴", "生育環境", "資料に記載された発生時期", "資料には食用との記載があります", "成分A"):
        assert value in rendered
    assert "Fungus &lt;test&gt;" in rendered and "出典資料に記載された学名" in rendered
    assert "資料記載名" not in rendered
    assert ">安全<" not in rendered and "食べられます" not in rendered
    assert "参考にした資料の情報を掲載しています" in rendered
    assert "食べられるかどうかについては、参考にした資料の情報を掲載しています。このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。毒性についての記載がなくても、安全とは限りません。" in rendered
    assert rendered.count("資料1") == 1 and rendered.count("資料2") == 1
    assert "missing" not in rendered and "https://source.test/1" in rendered
    assert 'target="_blank" rel="noopener noreferrer"' in rendered
    assert "組織2：資料2</li>" in rendered
    assert "注&lt;&amp;" in rendered and "None" not in rendered



def test_approved_ishikawa_note_only_on_yamadoritakemodoki():
    data = fixture_portal()
    row = data["reference_data"]["mushroom_master"]["entries"][0]
    row["canonical_name_ja"] = "ヤマドリタケモドキ"
    row["food_safety"]["notes"] = "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。"
    rendered = render_detail_sections(build_detail_views(data)["リンク名？"])
    assert "石川県の資料では、食毒欄に「食」と記載されています。これは公的資料に食用との記載があることを示すもので、実際に採ったキノコの安全性を保証するものではありません。毒性についての記載がなくても安全とは限らないため、食べられるかどうかを自分で判断するためには使わないでください。" in rendered
    assert "食べられるかどうかについては、参考にした資料の情報を掲載しています。このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。毒性についての記載がなくても、安全とは限りません。" in rendered
    assert "資料には食用との記載があります" in rendered
    assert "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。" not in rendered
    # Many entries share the same source note. Do not silently rewrite them all.
    row["canonical_name_ja"] = "ヒラタケ"
    other = render_detail_sections(build_detail_views(data)["リンク名？"])
    assert "石川県の資料では、食毒欄に「食」と記載されています。これは公的資料に食用との記載があることを示すもので、実際に採ったキノコの安全性を保証するものではありません。毒性についての記載がなくても安全とは限らないため、食べられるかどうかを自分で判断するためには使わないでください。" not in other
    assert "石川県の食毒欄は「食」" in other


def test_shared_subject_copy_without_changing_photo_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "copy_shared_assets", lambda: None)
    result = main.generate_gallery([{"alt": "リンク名？", "src": "original.jpg"}], {},
                                   detail_views=build_detail_views(fixture_portal()),
                                   multi_subject_overlays={"リンク名？": ["shared.jpg"]})
    markup = (tmp_path / "リンク名？.html").read_text(encoding="utf-8")
    assert "1枚の写真に複数の種類が写っている場合は、元の記事の記載をもとに、それぞれの図鑑ページにも写真を掲載しています。こうした写真は図鑑トップや観察記録の登録件数には含めず、未登録の写真にはお気に入りの星も表示していません。" in markup
    assert 'data-favorite-eligible="false"' in markup
    assert result == {"リンク名？": ["original.jpg"]}


def test_display_omits_repeated_stock_cautions_but_keeps_source_detail():
    boilerplate = ("食用可否の自己判断には使用しない。"
                   "毒性の記録がないことは安全を意味しない。")
    assert reader_facing_food_note(boilerplate) is None
    assert reader_facing_food_note(
        boilerplate + " 石川県の食毒欄は「要注意」。"
    ) == "石川県の食毒欄は「要注意」。"
    assert reader_facing_food_note(
        "石川県の食毒欄は「毒」。 " + boilerplate
    ) == "石川県の食毒欄は「毒」。"

    data = fixture_portal()
    row = data["reference_data"]["mushroom_master"]["entries"][0]
    row["food_safety"]["notes"] = boilerplate + " 石川県の食毒欄は「要注意」。"
    rendered = render_detail_sections(build_detail_views(data)["リンク名？"])
    assert "石川県の食毒欄は「要注意」。" in rendered
    assert "食用可否の自己判断には使用しない。" not in rendered
    assert "毒性の記録がないことは安全を意味しない。" not in rendered
    assert "このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。" in rendered
    assert "毒性についての記載がなくても、安全とは限りません。" in rendered


def test_shiitake_uses_exact_maff_source_note_only_for_itself():
    data = fixture_portal()
    master = data["reference_data"]["mushroom_master"]["entries"][0]
    master["canonical_name_ja"] = "シイタケ"
    master["food_safety"]["notes"] = (
        "食用可否の自己判断には使用しない。"
        "毒性の記録がないことは安全を意味しない。 "
        "農林水産省が食用きのこと明記した利用記録。"
        "野生個体の判定には使用しない。"
    )
    rendered = render_detail_sections(build_detail_views(data)["リンク名？"])
    assert ("農林水産省の資料では、シイタケを食用のキノコとして紹介しています。"
            "ただし、この情報だけで野生のキノコの種類や安全性を判断することはできません。") in rendered
    assert "食用可否の自己判断には使用しない。" not in rendered

    # Do not invent an identification or attribution for a different species.
    master["canonical_name_ja"] = "テスト菌"
    other = render_detail_sections(build_detail_views(data)["リンク名？"])
    assert "農林水産省の資料では、シイタケを食用のキノコとして紹介しています。" not in other
    assert "農林水産省が食用きのこと明記した利用記録。" in other


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
    ("poisonous_confirmed", "公的・専門資料には毒性の記載があります"),
    ("unknown", "食毒の区分は確認できていません"),
])
def test_other_food_safety_wording(status, wording):
    data = fixture_portal()
    data["reference_data"]["mushroom_master"]["entries"][0]["food_safety"]["status"] = status
    assert wording in render_detail_sections(build_detail_views(data)["リンク名？"])



def test_all_51_linked_food_notes_have_exact_reviewed_polite_display():
    """No silent status changes, unreviewed sources or lost species-specific cautions."""
    import detail_ui
    import main

    taxonomy = main.load_subject_taxonomy()
    master = json.loads(open("data/mushroom-master.json", encoding="utf-8").read())
    linked = {e["mushroom_master_id"] for e in taxonomy["entries"]
              if e.get("mushroom_master_id")}
    assert len(linked) == 51
    assert set(detail_ui.FOOD_NOTE_REVIEWED) == linked
    masters = {e["mushroom_id"]: e for e in master["entries"]}
    assert len(masters) == 141

    for mushroom_id in sorted(linked):
        mushroom = masters[mushroom_id]
        name, source_note, copy = detail_ui.FOOD_NOTE_REVIEWED[mushroom_id]
        assert name == mushroom["canonical_name_ja"]
        assert source_note == mushroom["food_safety"]["notes"]
        assert mushroom["food_safety"]["status"] in detail_ui.FOOD_SAFETY_LABELS
        assert copy is None or copy.endswith("。"), name
        assert copy is None or not any(
            term in copy for term in ("source report", "project", "unknown",
                                     "食用可否の自己判断には使用しない。", "記載あり",
                                     "保証ではない。", "ではない。", "である。")
        ), name

        output = detail_ui._knowledge(mushroom, {})
        food = next(row for row in output["rows"] if row["label"] == "食毒情報")
        assert food["value"] == detail_ui.FOOD_SAFETY_LABELS[mushroom["food_safety"]["status"]]
        assert food["note"] == copy, name
        rendered = render_detail_sections({"knowledge": output, "articles": []})
        assert ("このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。"
                in rendered)
        assert "食用可否の自己判断には使用しない。" not in rendered, name
        assert "公的・専門資料に毒性の記載あり" not in rendered, name
        assert "食毒情報は未確認" not in rendered, name
        if copy is not None:
            assert copy.replace("&", "&amp;").replace("<", "&lt;") in rendered

    assert detail_ui.FOOD_NOTE_REVIEWED["yamadoritakemodoki"][2] == detail_ui.YAMADORITAKEMODOKI_DISPLAY_NOTE
    assert detail_ui.FOOD_NOTE_REVIEWED["shiitake"][2] == detail_ui.SHIITAKE_DISPLAY_NOTE
    assert detail_ui.FOOD_NOTE_REVIEWED["benitengutake"][2] == detail_ui.FOOD_NOTE_REVIEWED["dokuyamadori"][2]


def test_new_or_changed_source_note_cannot_inherit_stale_reviewed_copy():
    """Exact mushroom ID + canonical name + note must match for the polished prose."""
    import detail_ui
    data = fixture_portal()
    master = data["reference_data"]["mushroom_master"]["entries"][0]
    reviewed = detail_ui.FOOD_NOTE_REVIEWED["shiitake"]
    master["mushroom_id"] = "shiitake"
    master["canonical_name_ja"] = reviewed[0]
    master["food_safety"]["notes"] = reviewed[1]
    correct = detail_ui._knowledge(master, {})
    assert next(row for row in correct["rows"] if row["label"] == "食毒情報")["note"] == reviewed[2]

    master["food_safety"]["notes"] += " 新しい未審査の注意書き。"
    changed = detail_ui._knowledge(master, {})
    note = next(row for row in changed["rows"] if row["label"] == "食毒情報")["note"]
    assert note != reviewed[2]
    assert "新しい未審査の注意書き" in note
    master["food_safety"]["notes"] = reviewed[1]
    master["canonical_name_ja"] = "別の菌名"
    renamed = detail_ui._knowledge(master, {})
    assert next(row for row in renamed["rows"] if row["label"] == "食毒情報")["note"] != reviewed[2]


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
    assert "食べられるかどうかについては、参考にした資料の情報を掲載しています。このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。毒性についての記載がなくても、安全とは限りません。" in output


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
    assert "飲酒" in rendered["ホテイシメジ"]
    assert "毒成分名" in rendered["オオワライタケ"]
    assert "安全を意味しない" in rendered["ウコンハツ"]
    # Source data remains untouched; only reader-facing duplication is removed.
    stock_sentences = ("食用可否の自己判断には使用しない。",
                       "毒性の記録がないことは安全を意味しない。")
    assert all(not any(sentence in note for sentence in stock_sentences)
               for note in rendered.values() if note)


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


def test_japanese_taxonomy_display_requires_exact_master_and_sources(tmp_path):
    data = fixture_portal()
    entries = data["reference_data"]["mushroom_master"]["entries"]
    mushroom = entries[0]
    original = copy.deepcopy(data)
    path = tmp_path / "display.json"
    path.write_text(json.dumps({
        "version": 1,
        "sources": {"sample": {"title": "表示出典", "url": "https://example.org/classification"}},
        "entries": {"linked": {
            "expected": {"name": "別名", "scientific": "Fungus <test>", "family": "科", "genus": "属"},
            "fields": {
                "family": {"value": "試験科", "latin": "Testaceae", "sources": ["sample"]},
                "ecology": {"value": "腐生菌", "sources": ["sample"]},
                "genus": {"value": "根拠欠落属", "sources": ["unknown"]},
            },
        }},
    }), encoding="utf-8")

    def view():
        return build_detail_views(data, taxonomy_display_path=path)["リンク名？"]

    first = render_detail_sections(view())
    assert "試験科" in first and "Testaceae" in first and "腐生菌" in first
    assert "https://example.org/classification" in first
    assert "根拠欠落属" not in first
    assert data == original
    mushroom["scientific_name"]["value"] = "Fungus changed"
    result = render_detail_sections(view())
    assert "試験科" not in result and "腐生菌" not in result and "未確認" in result
    assert "https://example.org/classification" not in result
