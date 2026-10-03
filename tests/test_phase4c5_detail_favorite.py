from pathlib import Path

import main


def _entries():
    return [
        {"alt": "タマゴタケ", "src": "https://example.invalid/tamagotake-1.jpg"},
        {"alt": "タマゴタケ", "src": "https://example.invalid/tamagotake-2.jpg"},
        {"alt": "ドクツルタケ", "src": "https://example.invalid/dokutsurutake.jpg"},
    ]


def test_detail_page_uses_phase4c5_shell_without_changing_gallery_hooks(monkeypatch, tmp_path):
    output = tmp_path / "output"
    monkeypatch.setattr(main, "OUTPUT_DIR", str(output))

    main.generate_gallery(_entries(), {})
    page = (output / "タマゴタケ.html").read_text(encoding="utf-8")

    assert page.startswith("<!doctype html>")
    assert '<body class="detail-page">' in page
    assert '<main id="gallery-content-root" class="detail-shell">' in page
    assert 'class="detail-hero"' in page
    assert "MUSHROOM DETAIL" in page
    assert '<h2 id="detail-title">タマゴタケ</h2>' in page
    assert "2枚の写真があります。" in page
    assert page.count('class="gallery-item"') == 2
    assert page.count('class="thumb-fav"') == 2
    assert 'class="detail-aiuo-links"' in page
    assert 'href="assets/detail.css"' in page
    assert 'src="assets/gallery.js"' in page


def test_favorite_page_uses_observation_note_shell_and_shared_hooks(monkeypatch, tmp_path):
    output = tmp_path / "output"
    monkeypatch.setattr(main, "OUTPUT_DIR", str(output))
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})

    grouped = {"タマゴタケ": ["https://example.invalid/tamagotake-1.jpg"]}
    main.generate_favorite_page(grouped)
    page = (output / "favorite.html").read_text(encoding="utf-8")

    assert page.startswith("<!doctype html>")
    assert '<body class="favorite-page">' in page
    assert '<main id="gallery-content-root" class="favorite-shell">' in page
    assert "OBSERVATION NOTE" in page
    assert '<h1 id="favorite-title">観察ノート</h1>' in page
    assert '<div class="favorite-gallery"></div>' in page
    assert 'href="assets/favorite.css"' in page
    assert 'src="assets/gallery.js"' in page
    assert (output / "assets" / "favorite.css").read_bytes() == (
        Path(main.ASSETS_DIR) / "favorite.css"
    ).read_bytes()


def test_guide_favorite_count_uses_japanese_item_suffix():
    script = (Path(main.ASSETS_DIR) / "gallery.js").read_text(encoding="utf-8")
    assert 'count > 0 ? `（${count}件）` : ""' in script
    assert 'localStorage.getItem(LG_FAVORITES_KEY)' in script
