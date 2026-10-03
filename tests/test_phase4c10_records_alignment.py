from pathlib import Path

import main


def test_detail_gojuon_buttons_match_guide_spacing_without_full_width_stretch():
    detail_css = (Path(main.ASSETS_DIR) / "detail.css").read_text(encoding="utf-8")
    guide_css = (Path(main.ASSETS_DIR) / "guide.css").read_text(encoding="utf-8")

    for shared in (
        "grid-template-columns:repeat(5,minmax(0,1fr))",
        "gap:8px",
        "padding:10px 6px",
        "font-size:.8rem",
        "line-height:1",
        "text-align:center",
    ):
        assert shared in guide_css
        assert shared in detail_css

    assert "width:min(100%,500px)" in detail_css
    assert ".detail-page .detail-aiuo-links { gap:6px; }" in detail_css
    assert ".detail-page .detail-aiuo-links .aiuo-link { padding:9px 4px; font-size:.76rem; }" in detail_css
