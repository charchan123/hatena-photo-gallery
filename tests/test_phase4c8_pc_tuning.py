from pathlib import Path

import main


def test_observation_note_overrides_legacy_square_anchor_and_grid_stretch():
    css = (Path(main.ASSETS_DIR) / "favorite.css").read_text(encoding="utf-8")
    assert "grid-auto-rows:max-content" in css
    assert "align-items:start" in css
    assert "align-self:start" in css
    assert "aspect-ratio:auto" in css
    assert "height:auto" in css
    assert "min-height:0" in css


def test_detail_mosaic_asset_and_protected_dom_contracts(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    entries = [
        {"alt": "テストタケ", "src": "https://example.test/one.jpg"},
        {"alt": "テストタケ", "src": "https://example.test/two.jpg"},
    ]
    main.generate_gallery(entries, {}, {})
    page = (tmp_path / f"{main.safe_filename('テストタケ')}.html").read_text(encoding="utf-8")
    script = (Path(main.ASSETS_DIR) / "gallery.js").read_text(encoding="utf-8")

    assert (tmp_path / "assets" / "mosaic-layout.js").exists()
    assert '<script src="assets/mosaic-layout.js"></script>' in page
    assert page.count('class="gallery-item"') == 2
    assert page.count('class="thumb-fav"') == 2
    assert 'selector: "a.gallery-item"' in script
    assert 'sendHeight("detail-mosaic")' in script
    assert "setTimeout(() => refreshDetailMosaic(gallery), 80)" in script
