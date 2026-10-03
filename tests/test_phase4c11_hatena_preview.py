from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hatena_article_preview_patch_is_scoped_and_non_destructive():
    css_path = ROOT / "hatena" / "hatena-article-newtop-preview.css"
    notes_path = ROOT / "hatena" / "HATENA_ARTICLE_PREVIEW.md"
    assert css_path.is_file()
    assert notes_path.is_file()

    css = css_path.read_text(encoding="utf-8")
    notes = notes_path.read_text(encoding="utf-8")

    scope = "body.page-entry:not(.static-page-new-top)"
    assert scope in css
    assert "body.static-page-new-top ." not in css
    assert 'hero-amanita-background.webp' in css
    assert 'hero-amanita-cutout.png' in css
    assert "#f7fcf4" in css
    assert "#box2 .hatena-module" in css
    assert ".comment-box" in css
    assert ".hatena-star-container" in css
    assert ".social-buttons" in css
    assert "display:none" not in css
    assert "@media screen and (max-width:960px)" in css
    assert "@media screen and (max-width:680px)" in css

    assert "Append" in notes
    assert "Preview" in notes
    assert "Do not save/publish yet" in notes
    assert "/new-top remains visually unchanged" in notes
