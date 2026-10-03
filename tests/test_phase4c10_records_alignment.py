from pathlib import Path

import main


def test_detail_gojuon_buttons_stay_on_one_compact_row():
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

    assert "grid-template-columns:repeat(5,minmax(0,1fr))" not in detail_css
    assert ".detail-page .detail-aiuo-links { gap:3px; }" in detail_css
    assert ".detail-page .detail-aiuo-links .aiuo-link { min-width:44px; padding:7px 8px; font-size:.74rem; }" in detail_css
