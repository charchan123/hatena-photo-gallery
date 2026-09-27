from pathlib import Path

import main
import season_ui


def render(monkeypatch, tmp_path, **kwargs):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.generate_index({}, {}, **kwargs)
    return (tmp_path / "index.html").read_text(encoding="utf-8")


def test_portal_intro_structure_and_core_entrances(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path)
    assert '<body class="portal-index">' in page
    assert '<section class="portal-intro"' in page
    assert "親子のキノコ観察記録" in page
    assert "🍄 キノコを探しに行こう" in page
    assert '<nav class="portal-grid" aria-label="キノコ図鑑の主な入口">' in page
    assert 'class="portal-card portal-card--guide" href="#mushroom-guide"' in page
    assert 'class="portal-card portal-card--season" href="season.html"' in page
    assert 'id="mushroom-guide"' in page
    assert 'aria-hidden="true"' in page


def test_optional_portal_entrances_follow_existing_conditions(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "render_record_cards", lambda *args, **kwargs: "record")
    page = render(monkeypatch, tmp_path)
    for modifier in ("features", "research", "best-shots", "records"):
        assert f"portal-card--{modifier}" not in page

    page = render(
        monkeypatch, tmp_path,
        feature_search_available=True,
        research_summary={"case_count": 1},
        best_shot_summary={"entry_count": 2},
        observation_records=[{"record": 1}],
    )
    for modifier, href in (("features", "features.html"), ("research", "research.html"),
                           ("best-shots", "best-shots.html"), ("records", "records.html")):
        assert f'class="portal-card portal-card--{modifier}" href="{href}"' in page


def test_best_shot_zero_does_not_render_placeholder(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path, best_shot_summary={"entry_count": 0})
    assert "portal-card--best-shots" not in page
    assert "ベストショット" not in page


def test_secondary_features_and_recommendation_selection_remain(monkeypatch, tmp_path):
    grouped = {"新しい菌": ["new.jpg"], "古い菌": ["old.jpg"], "ベニテングタケ": ["popular.jpg"]}
    exif = {"new.jpg": {"date": "2026/09/01"}, "old.jpg": {"date": "2025/01/01"}}
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.generate_index(grouped, exif)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    for expected in ("全キノコ横断検索", "五十音別分類", "📓 観察ノート", "🍄 おすすめキノコ"):
        assert expected in page
    assert page.index("新しい菌") < page.index("古い菌")
    assert "popular.jpg?width=400" in page


def test_portal_stylesheet_is_copied_and_scoped_to_index(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path)
    assert 'href="assets/portal.css"' in page
    assert (tmp_path / "assets" / "portal.css").exists()
    season = season_ui.render_season_page({"version": 1, "subjects": []}, main.safe_filename)
    assert "portal.css" not in season
    css = (Path(main.ASSETS_DIR) / "portal.css").read_text(encoding="utf-8")
    assert ".portal-index" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion: reduce" in css
