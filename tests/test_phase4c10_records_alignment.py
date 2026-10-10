from pathlib import Path

import main


def test_detail_gojuon_desktop_row_and_mobile_five_by_two():
    detail_css = (Path(main.ASSETS_DIR) / "detail.css").read_text(encoding="utf-8")

    for expected in (
        "display:flex",
        "flex-wrap:nowrap",
        "justify-content:flex-start",
        "gap:4px",
        "overflow-x:auto",
        "overscroll-behavior-inline:contain",
        "min-width:48px",
        "padding:8px 9px",
        "font-size:.78rem",
        "line-height:1",
        "text-align:center",
        "white-space:nowrap",
    ):
        assert expected in detail_css

    assert "grid-template-columns:repeat(5,minmax(0,1fr))" in detail_css
    assert "gap:6px; overflow-x:visible" in detail_css
    assert ".detail-page .detail-aiuo-links .aiuo-link { min-width:0; padding:9px 4px; background:#fff; font-size:.76rem; }" in detail_css


def test_detail_mobile_gojuon_matches_guide_button_style():
    detail_css = (Path(main.ASSETS_DIR) / "detail.css").read_text(encoding="utf-8")
    guide_css = (Path(main.ASSETS_DIR) / "guide.css").read_text(encoding="utf-8")
    mobile = detail_css.split("@media (max-width:680px)", 1)[1]
    assert "min-height:44px" not in mobile
    for shared in ("padding:9px 4px", "font-size:.76rem"):
        assert shared in mobile and shared in guide_css
    assert ".detail-page .detail-aiuo-links { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:6px; overflow-x:visible; }" in mobile
    for shared in ("border:1px solid #cbdac9", "border-radius:10px", "color:#31563a",
                   "font-weight:700", "line-height:1", "text-align:center"):
        assert shared in detail_css and shared in guide_css
