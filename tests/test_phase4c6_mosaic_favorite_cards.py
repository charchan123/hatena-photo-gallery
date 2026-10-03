from pathlib import Path

import main


def test_detail_photo_layout_is_natural_ratio_mosaic_with_only_outer_corners():
    css = (Path(main.ASSETS_DIR) / "detail.css").read_text(encoding="utf-8")
    script = (Path(main.ASSETS_DIR) / "gallery.js").read_text(encoding="utf-8")

    assert "grid-template-columns:repeat(var(--detail-mosaic-columns,5),minmax(0,1fr))" in css
    assert ".detail-page .detail-mosaic-column" in css
    assert "justify-content:space-between" in css
    assert "aspect-ratio:1/1" not in css
    assert "height:auto" in css
    assert "border-radius:0" in css
    for corner in ("tl", "tr", "bl", "br"):
        assert f"mosaic-corner-{corner}" in css
        assert f'"mosaic-corner-{corner}"' in script

    assert "function configureDetailMosaic(gallery)" in script
    assert "function partitionDetailMosaic(items, columns, columnWidth)" in script
    assert "function rebuildDetailMosaic(gallery)" in script
    assert 'column.className = "detail-mosaic-column"' in script


def test_observation_note_cards_match_gojuon_card_dimensions_and_keep_star_hook():
    favorite_css = (Path(main.ASSETS_DIR) / "favorite.css").read_text(encoding="utf-8")
    aiuo_css = (Path(main.ASSETS_DIR) / "aiuo.css").read_text(encoding="utf-8")
    script = (Path(main.ASSETS_DIR) / "gallery.js").read_text(encoding="utf-8")

    for shared_rule in (
        "grid-template-columns:repeat(4,minmax(0,1fr))",
        "gap:14px",
        "border:1px solid #e0e8de",
        "border-radius:14px",
        "box-shadow:0 5px 16px rgba(39,67,45,.06)",
        "padding-top:64%",
        "padding:11px 12px 13px",
    ):
        assert shared_rule in aiuo_css
        assert shared_rule in favorite_css

    assert 'a.className = "gallery-item mushroom-card favorite-mushroom-card"' in script
    assert 'thumb.className = "mushroom-card-thumb"' in script
    assert 'star.className = "thumb-fav card-fav is-fav"' in script
    assert 'nameEl.className = "mushroom-card-name"' in script
    assert 'nameEl.textContent = name || "名称不明"' in script
