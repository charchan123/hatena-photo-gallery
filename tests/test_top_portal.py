from pathlib import Path
import main


def record(i):
    return {"cover_src": f"photo{i}.jpg", "title": f"記事{i}",
            "published": f"2026-09-{20-i:02d}T00:00:00Z", "excerpt": f"本文{i}",
            "url": f"https://example.test/{i}"}


def render(monkeypatch, tmp_path, **kwargs):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.generate_new_top({}, {}, **kwargs)
    return (tmp_path / "new-top.html").read_text(encoding="utf-8")


def test_existing_index_restores_gallery_presentation(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path)); main.generate_index({}, {})
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    for expected in ("写真でたどる、キノコの観察記録", "gallery-guide", "全キノコ横断検索", "五十音別分類", "おすすめキノコ", "観察ノート"):
        assert expected in page
    assert '<body class="portal-index">' not in page and "assets/portal.css" not in page


def test_records_first_information_architecture(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path, observation_records=[record(i) for i in range(4)])
    assert '<body class="portal-index">' in page and 'href="assets/portal.css"' in page
    assert 'class="portal-records-hero"' in page and page.index("📔 観察記録") < page.index("🍄 キノコを探す")
    assert 'class="portal-lead-card" href="index.html"' in page and "📖 図鑑を見る" in page
    assert "季節から探す" in page and 'href="records.html"' in page
    for i in range(3):
        assert f"photo{i}.jpg?width=300" in page and f"記事{i}" in page and f"本文{i}" in page
    assert "記事3" not in page
    for forbidden in ("親子", 'id="mushroom-guide"', "キノコを調べる", "全キノコ横断検索", "五十音別分類", "おすすめキノコ", "観察ノート", "portal-card--records"):
        assert forbidden not in page


def test_optional_entrances_and_best_shot_condition(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path)
    for name in ("特徴から探す", "不明キノコ研究室", "ベストショット"):
        assert name not in page
    page = render(monkeypatch, tmp_path, feature_search_available=True,
                  research_summary={"case_count": 1}, best_shot_summary={"entry_count": 2})
    for modifier in ("features", "research", "best-shots"):
        assert f"portal-card--{modifier}" in page
    assert "ベストショット" not in render(monkeypatch, tmp_path, best_shot_summary={"entry_count": 0})


def test_portal_styles_are_compact_and_scoped(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path)
    assert (tmp_path / "assets" / "portal.css").exists()
    css = (Path(main.ASSETS_DIR) / "portal.css").read_text()
    for expected in (".portal-records-visual", ".record-preview-row", ".portal-secondary-grid", ":focus-visible", "prefers-reduced-motion"):
        assert expected in css
    main.generate_index({}, {})
    assert "portal.css" not in (tmp_path / "index.html").read_text()
