from datetime import datetime, timezone
import copy
from pathlib import Path
import main
import pytest
from bs4 import BeautifulSoup
from records_ui import build_observation_records, render_record_preview_rows, render_records_page


def observation(index, *, article_id="a", path="/a", url="https://example/a", published="2026-09-25T10:00:00+09:00", categories=None, name="A", src=None):
    return {"production_index": index, "gallery_name": name, "src": src or f"img{index}",
            "capture": {"date": "1900/01/01"},
            "article": {"article_id": article_id, "article_path": path, "title": "2026年9月18日静岡県浜松市<&", "url": url,
                        "published": published, "updated": "2099-01-01T00:00:00Z",
                        "categories": ["キノコ探索日記"] if categories is None else categories, "excerpt": "本文の冒頭<&"}}


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
    page = render_records_page(portal(observation(0), observation(1, article_id="b", url=None)),
                               now=datetime(2026, 9, 26, tzinfo=timezone.utc))
    assert "assets/gallery.css" in page and "assets/gallery.js" in page and "assets/records.css" in page
    assert '<body class="records-index">' in page
    assert '<main id="gallery-content-root" class="records-shell">' in page
    assert 'class="records-hero"' in page and "FIELD NOTES" in page
    assert '<h1 id="records-title">観察記録</h1>' in page
    assert 'href="new-top.html"' in page and 'class="back-btn"' in page and 'target="_top"' in page
    assert page.count("update-badge--new") == 2
    assert "NEW!" in page and "現在の図鑑掲載 1枚・1種類" in page
    assert "2026年9月18日静岡県浜松市&lt;&amp;" in page
    assert "写真の撮影日とは別" in page and "観察日" not in page


def test_future_schema_rejected():
    with pytest.raises(ValueError):
        build_observation_records({"version": 2})


def test_guide_index_intentionally_omits_record_preview(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "copy_shared_assets", lambda: None)
    records = build_observation_records(
        portal(*[
            observation(i, article_id=str(i), published=f"2026-01-0{i+1}T00:00:00Z")
            for i in range(4)
        ])
    )

    main.generate_index({}, {}, observation_records=records)
    text = (tmp_path / "index.html").read_text()

    assert "観察記録" not in text
    assert "record-list-preview" not in text
    assert "record-card-badge" not in text
    assert 'href="https://exsudoporus-ruber.hatenablog.jp/"' not in text
    assert 'class="record-card record-external-link"' not in text

def test_record_preview_css_and_external_return_contract():
    root = Path(__file__).resolve().parents[1]
    css = (root / "assets" / "records.css").read_text()
    script = (root / "assets" / "gallery.js").read_text()
    assert ".record-list-preview" in css and "max-width: 620px" in css
    assert ".record-list-preview .record-card" in css and "grid-template-columns" in css
    assert ".record-more-link { margin-top: 20px; }" in css
    assert "@keyframes record-new-pulse" not in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert 'a.record-external-link[target=\'_top\']' in script
    assert "sessionStorage.setItem(RECORD_EXTERNAL_RETURN_KEY" in script
    assert "sessionStorage.removeItem(RECORD_EXTERNAL_RETURN_KEY)" in script
    assert 'pathname.endsWith("/index.html")' in script
    assert "shouldReloadGalleryIndex(event, location.pathname)" in script
    assert "window.location.reload()" in script
    assert "refreshAfterExternalRecord && isGalleryIndex" not in script


def test_records_failure_isolation_and_no_stale_read(monkeypatch):
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: (_ for _ in ()).throw(AssertionError("stale")))
    assert main.generate_records_page_if_fresh({"build_ok": False}) == []
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: {"version": 1})
    monkeypatch.setattr(main, "generate_records_page", lambda *args: (_ for _ in ()).throw(RuntimeError("boom")))
    assert main.generate_records_page_if_fresh({"build_ok": True}) == []


def test_excerpt_is_preserved_and_compact_preview_is_escaped():
    records = build_observation_records(portal(observation(0)))
    assert records[0]["excerpt"] == "本文の冒頭<&"
    preview = render_record_preview_rows(records, now=datetime(2026, 10, 4, tzinfo=timezone.utc))
    assert "本文の冒頭&lt;&amp;" in preview and 'target="_top"' in preview
    assert "img0?width=500" in preview
    assert "現在の図鑑掲載" not in preview and "NEW!" not in preview

def test_records_page_matches_new_top_field_notes_visual_contract():
    root = Path(__file__).resolve().parents[1]
    css = (root / "assets" / "records.css").read_text(encoding="utf-8")
    assert "body.records-index" in css
    assert "width:min(100%,1180px)" in css
    assert 'url("field-notes-observation-final.webp")' in css
    assert ".records-index .records-hub" in css
    assert ".records-index .record-list" in css
    assert "grid-template-columns:1fr" in css
    assert "grid-template-columns:190px minmax(0,1fr)" in css
    assert ".records-index .records-footer .back-btn" in css
    assert "@media (max-width:760px)" in css


def test_native_star_previews_separate_links_and_bind_only_original_permalinks():
    rows = [{"title": f"写真のタイトル {i}<&", "url": f"https://exsudoporus-ruber.hatenablog.jp/entry/2026/10/15/{i}",
             "published": "2026-10-15T00:00:00Z", "cover_src": f"https://example.test/{i}.jpg", "excerpt": "本文<&"}
            for i in range(4)]
    soup = BeautifulSoup(render_record_preview_rows(rows), "html.parser")
    assert len(soup.select("article.record-star-entry")) == 3
    assert not soup.select("a a, a button, a iframe, a .record-stars")
    for i, row in enumerate(soup.select("article.record-star-entry")):
        links = row.select("a")
        assert len(links) == 4
        assert all(a["href"] == rows[i]["url"] and a["target"] == "_top" for a in links)
        assert all(a.get("rel") == ["noopener", "noreferrer"] for a in links)
        assert row.select_one(".record-preview-meta time").get_text() == "2026年10月15日 公開"
        assert row.select_one(".record-stars-native").parent.get("role") == "group"
        assert row.select_one(".record-stars-total").get_text() == "スター"  # No guessed count or synthetic stars.
        assert row.select_one(".record-preview-title").get_text() == rows[i]["title"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,hello", "https://user:password@example.test/x", "//example.test/entry/x"])
def test_preview_rejects_unsafe_navigation_without_star_registration(url):
    soup = BeautifulSoup(render_record_preview_rows([{"title": "安全確認", "url": url}]), "html.parser")
    assert not soup.select("a, .record-stars, .record-star-entry")


@pytest.mark.parametrize("url", ["https://example.test/entry/x", "https://exsudoporus-ruber.hatenablog.jp.evil.test/entry/x", "https://exsudoporus-ruber.hatenablog.jp/entry/x?x=1", "http://exsudoporus-ruber.hatenablog.jp/entry/x"])
def test_star_is_not_attached_to_guess_or_alternate_uri(url):
    soup = BeautifulSoup(render_record_preview_rows([{"title": "対応付け", "url": url}]), "html.parser")
    assert soup.select_one("a.record-star-permalink")["href"] == url
    assert not soup.select(".record-stars, .record-star-entry")


@pytest.mark.parametrize('published, expected', [
    ('2026-10-15T06:41:55+09:00', '2026年10月15日 公開'),
    ('2026-10-14T21:41:55Z', '2026年10月15日 公開'),
    ('invalid', '公開日不明'),
])
def test_top_preview_published_date_uses_jst_without_changing_stored_timestamp(published, expected):
    rows = [{'url': 'https://example.test/article', 'published': published}]
    before = copy.deepcopy(rows)
    soup = BeautifulSoup(render_record_preview_rows(rows), 'html.parser')
    assert soup.select_one('time').get_text() == expected
    assert rows == before
