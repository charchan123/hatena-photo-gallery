from pathlib import Path

import main


def test_phase4c8_detail_mosaic_uses_fixed_gap_and_computed_dimensions():
    css = (Path(main.ASSETS_DIR) / "detail.css").read_text(encoding="utf-8")
    script = (Path(main.ASSETS_DIR) / "gallery.js").read_text(encoding="utf-8")

    assert "--detail-mosaic-gap:10px" in css
    assert "justify-content:flex-start" in css
    assert "DetailMosaicLayout.computeMosaicLayout" in script
    assert "gallery.replaceChildren(fragment)" in script


def test_phase4c7_observation_note_reuses_gojuon_class_names():
    script = (Path(main.ASSETS_DIR) / "gallery.js").read_text(encoding="utf-8")
    favorite_css = (Path(main.ASSETS_DIR) / "favorite.css").read_text(encoding="utf-8")

    assert 'gallery-item mushroom-card favorite-mushroom-card' in script
    assert 'mushroom-card-thumb' in script
    assert 'thumb-fav card-fav is-fav' in script
    assert 'mushroom-card-name' in script
    assert ".favorite-page .mushroom-card {" in favorite_css
    assert ".favorite-page .mushroom-card-thumb {" in favorite_css
    assert ".favorite-page .mushroom-card-name {" in favorite_css


def test_phase4c7_new_top_notice_is_plain_footer_content(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.generate_new_top({}, {})
    page = (tmp_path / "new-top.html").read_text(encoding="utf-8")

    assert '<section class="portal-request"' in page
    assert "<h2 id=\"portal-request-heading\">お願い</h2>" in page
    assert "大目に見ていただけると幸いです。" in page
    assert "確信がもてない場合は、採取しないことをお勧めします。" in page
    assert "また掲載されている画像等の無断転載はご遠慮ください。" in page
