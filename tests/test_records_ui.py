import copy
from pathlib import Path
import main
import pytest
from records_ui import build_observation_records, render_records_page


def observation(index, *, article_id="a", path="/a", url="https://example/a", published="2026-09-25T10:00:00+09:00", categories=None, name="A", src=None):
    return {"production_index": index, "gallery_name": name, "src": src or f"img{index}",
            "capture": {"date": "1900/01/01"},
            "article": {"article_id": article_id, "article_path": path, "title": "2026年9月18日静岡県浜松市<&", "url": url,
                        "published": published, "updated": "2099-01-01T00:00:00Z",
                        "categories": ["キノコ探索日記"] if categories is None else categories}}


def portal(*rows):
    return {"version": 1, "observations": list(rows)}


def test_exact_category_only():
    rows = [observation(i, article_id=str(i), categories=[category]) for i, category in enumerate(("キノコ探索日記", "キノコ探索日記2", "キノコ"))]
    rows.append(observation(4, article_id="4", categories=[]))
    assert [r["article_id"] for r in build_observation_records(portal(*rows))] == ["0"]


def test_dedup_cover_and_counts():
    rows = [observation(i, src=f"s{i}", name=("A", "A", "B")[i]) for i in (2, 0, 1)]
    record = build_observation_records(portal(*rows))[0]
    assert record["photo_count"] == 3
    assert record["subject_count"] == 2
    assert record["cover_src"] == "s0"
    assert record["first_production_index"] == 0


@pytest.mark.parametrize("missing, expected", [((), 1), (("article_id",), 1), (("article_id", "article_path"), 1), (("article_id", "article_path", "url"), 0)])
def test_identity_priority_and_missing(missing, expected):
    row = observation(0)
    for key in missing:
        row["article"][key] = None
    assert len(build_observation_records(portal(row))) == expected


def test_chronology_uses_published_and_invalid_is_deterministic():
    rows = [observation(0, article_id="old", published="2025-01-01T00:00:00Z"),
            observation(1, article_id="new", published="2026-01-01T00:00:00Z"),
            observation(2, article_id="z", published="bad"), observation(3, article_id="a", published=None)]
    assert [r["article_id"] for r in build_observation_records(portal(*rows))] == ["new", "old", "a", "z"]


def test_records_page_contract_escape_and_navigation():
    page = render_records_page(portal(observation(0), observation(1, article_id="b", url=None)))
    assert "assets/gallery.css" in page and "assets/gallery.js" in page and "assets/records.css" in page
    assert 'class="back-btn"' in page and 'target="_top"' in page
    assert page.count("record-card-badge") == 1
    assert "NEW!" in page and "現在の図鑑掲載 1枚・1種類" in page
    assert "2026年9月18日静岡県浜松市&lt;&amp;" in page
    assert "写真の撮影日とは別" in page and "観察日" not in page


def test_future_schema_rejected():
    with pytest.raises(ValueError):
        build_observation_records({"version": 2})


def test_index_preview_optional_and_limited(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "copy_shared_assets", lambda: None)
    records = build_observation_records(portal(*[observation(i, article_id=str(i), published=f"2026-01-0{i+1}T00:00:00Z") for i in range(4)]))
    main.generate_index({}, {}, observation_records=records)
    text = (tmp_path / "index.html").read_text()
    assert "📔 観察記録" in text and text.count('target="_top"') == 2
    assert text.count("record-card-badge") == 1
    assert "NEW!" in text and "img3?width=500" in text and "img2?width=500" not in text
    assert 'href="https://exsudoporus-ruber.hatenablog.jp/"' in text
    assert 'class="aiuo-link feature-action-link record-more-link record-external-link"' in text
    assert 'href="records.html"' not in text and text.count('class="record-card record-external-link"') == 1
    main.generate_index({}, {}, observation_records=[])
    assert "📔 観察記録" not in (tmp_path / "index.html").read_text()


def test_record_preview_css_and_external_return_contract():
    root = Path(__file__).resolve().parents[1]
    css = (root / "assets" / "records.css").read_text()
    script = (root / "assets" / "gallery.js").read_text()
    assert ".record-list-preview" in css and "max-width: 620px" in css
    assert ".record-list-preview .record-card" in css and "grid-template-columns" in css
    assert ".record-more-link { margin-top: 20px; }" in css
    assert "@keyframes record-new-pulse" in css
    assert "@media (prefers-reduced-motion: reduce)" in css and "animation: none" in css
    assert 'a.record-external-link[target=\'_top\']' in script
    assert "sessionStorage.setItem(RECORD_EXTERNAL_RETURN_KEY" in script
    assert "sessionStorage.removeItem(RECORD_EXTERNAL_RETURN_KEY)" in script
    assert 'location.pathname.endsWith("/index.html")' in script
    assert "refreshAfterExternalRecord && isGalleryIndex" in script


def test_records_failure_isolation_and_no_stale_read(monkeypatch):
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: (_ for _ in ()).throw(AssertionError("stale")))
    assert main.generate_records_page_if_fresh({"build_ok": False}) == []
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: {"version": 1})
    monkeypatch.setattr(main, "generate_records_page", lambda *args: (_ for _ in ()).throw(RuntimeError("boom")))
    assert main.generate_records_page_if_fresh({"build_ok": True}) == []
