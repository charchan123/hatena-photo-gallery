from pathlib import Path

import main
import portal_data
import season_ui


def subject(name, counts, cover="photo.jpg"):
    return {
        "gallery_name": name,
        "cover_src": cover,
        "photo_count": sum(counts.values()),
        "capture_months": sorted(counts),
        "capture_month_counts": {str(month): count for month, count in counts.items()},
    }


def data(*subjects):
    return {"version": 1, "subjects": list(subjects)}


def test_season_grouping_uses_defined_months_and_counts():
    grouped = season_ui.group_subjects_by_season(data(
        subject("通年菌", {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6,
                         7: 7, 8: 8, 9: 9, 10: 10, 11: 11, 12: 12})
    ))
    assert list(grouped) == ["spring", "summer", "autumn", "winter"]
    assert [row[0]["season_month_counts"] for row in grouped.values()] == [
        {3: 3, 4: 4, 5: 5}, {6: 6, 7: 7, 8: 8},
        {9: 9, 10: 10, 11: 11}, {12: 12, 1: 1, 2: 2},
    ]


def test_undated_subject_is_not_inferred_into_any_season():
    grouped = season_ui.group_subjects_by_season(data(subject("日付なし", {})))
    assert all(not subjects for subjects in grouped.values())


def test_subject_with_observations_in_multiple_seasons_appears_in_each():
    grouped = season_ui.group_subjects_by_season(data(subject("二季菌", {5: 2, 9: 1})))
    assert [key for key, rows in grouped.items() if rows] == ["spring", "autumn"]


def test_uncertain_and_provisional_names_are_preserved_verbatim():
    names = ["不明", "菌名？", "菌名(仮称)", "菌名(広義)"]
    rendered = season_ui.render_season_page(
        data(*(subject(name, {7: 1}, f"{index}.jpg") for index, name in enumerate(names))),
        main.safe_filename,
    )
    for name in names:
        assert name in rendered


def test_generated_cards_link_to_existing_gallery_filename_rule():
    rendered = season_ui.render_season_page(
        data(subject("菌/名?", {12: 2})), main.safe_filename
    )
    assert 'href="菌_名_.html"' in rendered
    assert "撮影月：12月" in rendered
    assert "この季節の観察写真 2枚" in rendered


def test_season_page_reuses_shared_gallery_ui_and_scripts():
    rendered = season_ui.render_season_page(
        data(subject("春菌", {4: 1})), main.safe_filename
    )
    for expected in (
        'href="assets/gallery.css"',
        'src="assets/gallery.js"',
        'class="aiuo-page season-page"',
        'class="aiuo-title"',
        'class="mushroom-list"',
        'class="mushroom-card"',
        'class="mushroom-card-thumb"',
        'class="card-fav"',
        'class="mushroom-card-name"',
        'class="back-btn"',
    ):
        assert expected in rendered
    assert "OBSERVATION ARCHIVE" not in rendered
    assert "Georgia" not in rendered


def test_season_card_link_is_handled_by_shared_html_navigation_bridge():
    rendered = season_ui.render_season_page(
        data(subject("春菌", {4: 1})), main.safe_filename
    )
    assert 'class="mushroom-card" href="春菌.html"' in rendered
    gallery_source = (Path(main.ASSETS_DIR) / "gallery.js").read_text(encoding="utf-8")
    assert '/\\.html(\\?|$)/.test(href)' in gallery_source
    assert '{ type: "scrollToTitle" }' in gallery_source


def test_index_uses_simple_season_entry_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.generate_index({}, {})
    rendered = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "🗓️ 季節から探す" in rendered
    assert "写真の撮影月から探せます" in rendered
    assert "EXIF撮影月から探せます" not in rendered


def test_index_centers_only_the_two_standalone_feature_actions(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.generate_index({}, {})
    rendered = (tmp_path / "index.html").read_text(encoding="utf-8")
    css = (Path(main.ASSETS_DIR) / "gallery.css").read_text(encoding="utf-8")

    assert 'class="aiuo-link feature-action-link" href="season.html"' in rendered
    assert 'class="aiuo-link note-link feature-action-link" href="favorite.html"' in rendered
    assert 'class="aiuo-link feature-action-link" href="あ行.html"' not in rendered
    assert ".feature-action-link {" in css
    assert "width: fit-content;" in css


def test_page_explains_exif_source_and_not_general_occurrence_season():
    rendered = season_ui.render_season_page(data(), main.safe_filename)
    assert "実際に撮影した写真の撮影月" in rendered
    assert "撮影月は写真のEXIF情報を使用しています" in rendered
    assert "一般的なキノコの発生時期を示すものではありません" in rendered
    assert "推測配置していません" in rendered


def test_portal_failure_never_reads_stale_data_or_generates_season(monkeypatch):
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: (_ for _ in ()).throw(AssertionError("read")))
    monkeypatch.setattr(main, "generate_season_page", lambda *args: (_ for _ in ()).throw(AssertionError("generate")))
    assert main.generate_season_page_if_fresh({"build_ok": False}) is False


def test_season_generation_failure_is_isolated(monkeypatch):
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: {"version": 1})
    monkeypatch.setattr(main, "generate_season_page", lambda *args: (_ for _ in ()).throw(OSError("disk")))
    assert main.generate_season_page_if_fresh({"build_ok": True}) is False


def test_portal_contract_version_and_production_selection_code_are_unchanged():
    portal = portal_data.build_portal_data(
        production_entries=[], shadow_metadata=[], article_metadata={}, exif_cache={},
        taxonomy={"version": 1, "entries": []},
        mushroom_master={"version": 1, "entries": []},
        sources={"version": 1, "sources": []},
        production_mode="phase3c_hybrid", cutover_active=True,
    )
    assert portal["version"] == 1
    assert portal["production"] == {
        "mode": "phase3c_hybrid", "cutover_active": True, "image_count": 0,
    }


def test_season_ui_rejects_a_future_portal_schema():
    try:
        season_ui.render_season_page({"version": 2, "subjects": []}, main.safe_filename)
    except ValueError as error:
        assert "schema version 1" in str(error)
    else:
        raise AssertionError("future portal schema was accepted")
