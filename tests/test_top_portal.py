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
    assert 'class="portal-records-hero"' in page and page.index("観察記録") < page.index("キノコを探す")
    assert 'class="portal-lead-card" href="index.html"' in page and "図鑑を見る" in page
    assert "季節から探す" in page and 'href="records.html"' in page
    for i in range(3):
        assert f"photo{i}.jpg?width=500" in page and f"記事{i}" in page and f"本文{i}" in page
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
    explore = page[page.index('<section class="portal-explore"'):page.index('</section>', page.index('<section class="portal-explore"'))]
    assert "季節から探す" in explore and "特徴から探す" in explore
    assert "不明キノコ研究室" not in explore and "ベストショット" not in explore
    independent = page[page.index('<section class="portal-independent-links"'):page.index('</section>', page.index('<section class="portal-independent-links"'))]
    assert "不明キノコ研究室" in independent and "ベストショット" in independent
    for expected in ("FIELD NOTES", "MUSHROOM GUIDE", "RESEARCH LAB", "BEST SHOTS"):
        assert expected in page
    for visual in ("portal-section-visual--explore", "portal-card--research", "portal-card--best-shots"):
        assert visual in page
    assert "portal-card__arrow" not in page and ">→<" not in independent
    assert page.count('<svg class="portal-icon"') >= 9
    assert page.count('aria-hidden="true" focusable="false"') >= 9
    for emoji in ("📔", "🍄", "📖", "🗓️", "🔎", "❓", "📸"):
        assert emoji not in page
    assert "ベストショット" not in render(monkeypatch, tmp_path, best_shot_summary={"entry_count": 0})
    assert "portal-independent-links" not in render(monkeypatch, tmp_path)


def test_independent_links_each_stand_alone(monkeypatch, tmp_path):
    research = render(monkeypatch, tmp_path, research_summary={"case_count": 1})
    assert "portal-independent-links" in research and "不明キノコ研究室" in research
    assert "ベストショット" not in research
    best_shot = render(monkeypatch, tmp_path, best_shot_summary={"entry_count": 1})
    assert "portal-independent-links" in best_shot and "ベストショット" in best_shot
    assert "不明キノコ研究室" not in best_shot


def test_blog_about_links_are_last_and_escape_iframe(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path, research_summary={"case_count": 1},
                  best_shot_summary={"entry_count": 1})
    assert page.index("観察記録") < page.index("キノコを探す")
    assert page.index("キノコを探す") < page.index("不明キノコ研究室")
    assert page.index("ベストショット") < page.index("このブログについて")
    expected = {
        "自己紹介": "%E8%87%AA%E5%B7%B1%E7%B4%B9%E4%BB%8B",
        "日常記録": "%E6%97%A5%E5%B8%B8%E3%81%AE%E8%A8%98%E9%8C%B2",
        "リンク集": "%E3%83%AA%E3%83%B3%E3%82%AF%E9%9B%86",
    }
    about = page[page.index('<footer class="portal-about"'):page.index('</footer>')]
    for label, category in expected.items():
        assert label in about and f"/archive/category/{category}" in about
    assert about.count('target="_top"') == 3


def test_portal_styles_are_compact_and_scoped(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path)
    assert (tmp_path / "assets" / "portal.css").exists()
    css = (Path(main.ASSETS_DIR) / "portal.css").read_text()
    for expected in (".portal-records-visual", ".portal-section-visual", ".record-preview-row", ".record-preview-thumb img", ".portal-secondary-grid", ".portal-independent-links", ".portal-about", ":focus-visible", "prefers-reduced-motion"):
        assert expected in css
    assert ".portal-card__arrow" not in css and "scale(1.08)" in css
    assert "#f7fcf4" in css
    assert "#f3f0e6" not in css
    main.generate_index({}, {})
    assert "portal.css" not in (tmp_path / "index.html").read_text()
