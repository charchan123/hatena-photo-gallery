from pathlib import Path
from PIL import Image
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
    assert 'class="portal-card portal-card--guide" href="index.html"' in page and "図鑑を見る" in page
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
    assert "portal-guide-grid portal-guide-grid--three" in page
    assert "3つの視点" in page
    assert page.count('<svg class="portal-icon"') >= 9
    assert page.count('aria-hidden="true" focusable="false"') >= 9
    for emoji in ("📔", "🍄", "📖", "🗓️", "🔎", "❓", "📸"):
        assert emoji not in page
    assert "ベストショット" not in render(monkeypatch, tmp_path, best_shot_summary={"entry_count": 0})
    assert "portal-independent-links" not in render(monkeypatch, tmp_path)
    without_features = render(monkeypatch, tmp_path)
    assert "portal-guide-grid portal-guide-grid--two" in without_features
    assert "3つの視点" not in without_features


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
    for expected in (".portal-records-visual", ".portal-section-visual", ".record-preview-row", ".record-preview-thumb img", ".portal-guide-grid", ".portal-independent-links", ".portal-about", ":focus-visible", "prefers-reduced-motion"):
        assert expected in css
    assert ".portal-card__arrow" not in css and "scale(1.08)" in css
    assert "#f7fcf4" in css
    assert "#f3f0e6" not in css
    assert ".portal-index .portal-shell { width:min(100%,1180px); margin:0 auto; padding:24px 22px 52px;" in css
    desktop = css[css.index("@media (min-width:900px)"):css.index("@media (max-width:680px)")]
    for expected in (
        "grid-template-columns:repeat(2,minmax(0,1fr))",
        "column-gap:20px",
        "row-gap:18px",
        "align-items:stretch",
        ".portal-records-visual,.portal-section-visual { height:190px; }",
        ".portal-explore { margin-top:0; }",
        ".portal-independent-links { grid-column:1/-1; width:100%; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px;",
        ".portal-independent-links .portal-card { min-height:155px; }",
        ".portal-about { grid-column:1/-1;",
    ):
        assert expected in desktop
    assert "920px" not in css
    tablet = css[css.index("@media (max-width:899px)"):css.index("@media (max-width:680px)")]
    assert ".portal-independent-links { grid-template-columns:1fr; }" in tablet
    mobile = css[css.index("@media (max-width:680px)"):]
    for expected in (
        ".portal-records-visual,.portal-section-visual { height:150px; }",
        ".portal-guide-grid,.portal-independent-links,.portal-about-links { grid-template-columns:1fr;",
        ".portal-independent-links .portal-card { min-height:155px; }",
    ):
        assert expected in mobile
    artwork = Path(main.ASSETS_DIR) / "field-notes-observation-final.webp"
    assert artwork.is_file()
    deployed_artwork = tmp_path / "assets" / "field-notes-observation-final.webp"
    assert deployed_artwork.is_file()
    assert deployed_artwork.read_bytes() == artwork.read_bytes()
    records_visual = css[css.index(".portal-records-visual { "):css.index("}", css.index(".portal-records-visual { "))]
    assert 'background-image:url("field-notes-observation-final.webp")' in records_visual
    assert "background-size:cover" in records_visual
    assert "background-position:center center" in records_visual
    assert css.count("field-notes-observation-final.webp") == 1
    for placeholder in (
        ".portal-section-visual--explore",
        ".portal-card--research .portal-card__visual",
        ".portal-card--best-shots .portal-card__visual",
    ):
        rule = css[css.index(placeholder):css.index("}", css.index(placeholder))]
        assert "field-notes-observation-final.webp" not in rule
    main.generate_index({}, {})
    assert "portal.css" not in (tmp_path / "index.html").read_text()


def test_reference_overlay_and_footer_contract(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path, feature_search_available=True,
                  research_summary={"case_count": 1}, best_shot_summary={"entry_count": 1})
    records_visual = page[page.index('<div class="portal-records-visual">'):page.index('</div>', page.index('<div class="portal-records-visual">'))]
    guide_visual = page[page.index('<div class="portal-section-visual'):page.index('</div>', page.index('<div class="portal-section-visual'))]
    assert 'class="portal-records-heading"' in records_visual and "FIELD NOTES" in records_visual
    assert 'class="portal-section-heading"' in guide_visual and "MUSHROOM GUIDE" in guide_visual
    assert records_visual.index("portal-eyebrow") < records_visual.index("観察記録")
    assert guide_visual.index("portal-eyebrow") < guide_visual.index("キノコを探す")
    independent = page[page.index('<section class="portal-independent-links"'):page.index('</section>', page.index('<section class="portal-independent-links"'))]
    assert independent.count('class="portal-card__visual" aria-hidden="true"') == 2
    assert independent.count('class="portal-card__content"') == 2
    for label in ("RESEARCH LAB", "BEST SHOTS"):
        assert label in independent
    assert "portal-lead-card" not in page
    about = page[page.index('<footer class="portal-about"'):page.index('</footer>')]
    for description in ("このブログを書いている人", "田舎での暮らしや日々のこと", "関連サイトやおすすめリンク"):
        assert description in about
    css = (Path(main.ASSETS_DIR) / "portal.css").read_text()
    assert ".portal-about-links { display:grid; grid-template-columns:repeat(3,minmax(0,1fr));" in css
    assert "filter:" not in css and "blur(" not in css and "sepia(" not in css

def test_hero_banner_assets_are_deployed_verbatim(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.copy_shared_assets()

    assets = Path(main.ASSETS_DIR)
    background = assets / "hero-amanita-background.webp"
    cutout = assets / "hero-amanita-cutout.png"
    deployed_background = tmp_path / "assets" / background.name
    deployed_cutout = tmp_path / "assets" / cutout.name

    for source, deployed in (
        (background, deployed_background),
        (cutout, deployed_cutout),
    ):
        assert source.is_file()
        assert deployed.is_file()
        assert deployed.read_bytes() == source.read_bytes()

    with Image.open(background) as image:
        assert image.format == "WEBP"
        assert image.size == (2048, 408)

    with Image.open(cutout) as image:
        assert image.format == "PNG"
        assert image.size == (725, 1000)
        assert image.mode == "RGBA"
        assert image.getchannel("A").getextrema() == (0, 255)

def test_portal_artwork_assets_are_deployed_verbatim(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.copy_shared_assets()

    assets = Path(main.ASSETS_DIR)
    expected = {
        "mushroom-guide-final.webp": (2048, 768),
        "research-lab-final.webp": (2048, 768),
        "best-shots-final.webp": (2048, 768),
    }

    for filename, dimensions in expected.items():
        source = assets / filename
        deployed = tmp_path / "assets" / filename
        assert source.is_file()
        assert deployed.is_file()
        assert deployed.read_bytes() == source.read_bytes()
        with Image.open(source) as image:
            assert image.format == "WEBP"
            assert image.size == dimensions

    css = (assets / "portal.css").read_text()
    assert 'background-image:url("mushroom-guide-final.webp")' in css
    assert 'background-image:url("research-lab-final.webp")' in css
    assert 'background-image:url("best-shots-final.webp")' in css
    assert ".portal-records-visual,.portal-section-visual { height:190px; }" in css

def test_reference_portal_card_proportions_and_lower_artwork_assignment():
    css = (Path(main.ASSETS_DIR) / "portal.css").read_text()

    assert '.portal-card--research .portal-card__visual { background-image:url("best-shots-final.webp")' in css
    assert '.portal-card--best-shots .portal-card__visual { background-image:url("research-lab-final.webp")' in css

    desktop = css[css.index("@media (min-width:900px)"):css.index("@media (max-width:680px)")]
    assert ".portal-records-visual,.portal-section-visual { height:190px; }" in desktop
    assert "column-gap:20px" in desktop
    assert "row-gap:18px" in desktop
    assert "align-items:start" in desktop
    assert ".portal-independent-links .portal-card { min-height:155px; }" in desktop

    assert ".portal-guide-grid { display:grid; flex:0 0 auto; gap:12px; }" in css
    assert "grid-template-columns:150px minmax(0,1fr)" in css
    assert ".record-preview-thumb { display:block; height:96px;" in css

def test_guide_help_fills_equal_height_without_stretching_entry_cards(monkeypatch, tmp_path):
    page = render(monkeypatch, tmp_path, feature_search_available=True,
                  observation_records=[record(i) for i in range(3)])

    assert 'class="portal-guide-help"' in page
    assert "こんなときは" in page
    assert "名前が分かる" in page and "図鑑を見る" in page
    assert "撮影時期が分かる" in page and "季節から探す" in page
    assert "名前が分からない" in page and "特徴から探す" in page

    without_features = render(monkeypatch, tmp_path, feature_search_available=False)
    help_section = without_features[without_features.index('class="portal-guide-help"'):]
    assert "名前が分からない" not in help_section

    css = (Path(main.ASSETS_DIR) / "portal.css").read_text()
    desktop = css[css.index("@media (min-width:900px)"):css.index("@media (max-width:680px)")]
    assert "align-items:stretch" in desktop
    assert ".portal-records-visual,.portal-section-visual { height:190px; }" in desktop
    assert ".portal-guide-grid .portal-card__copy strong { gap:6px; font-size:1rem; white-space:nowrap; }" in css
    assert ".portal-guide-help { display:flex; flex:1 1 auto; min-height:112px;" in css
    assert ".portal-guide-grid .portal-card { min-height:135px; }" in desktop
