from pathlib import Path

import main
import pytest

from research_ui import (build_research_cases, build_research_model,
                         generate_research_page, is_research_observation,
                         render_research_page)


ROOT = Path(__file__).parents[1]


def observation(index, name="不明", *, article_id="a", article_path="/a",
                url="https://example.test/a?x=1&y=2", capture="2026/07/08",
                published="2026-07-09T00:00:00Z", status="legacy_review",
                observation_id=None, title="2026年7月8日静岡県掛川市"):
    return {"production_index": index, "observation_id": observation_id or f"o{index}",
            "gallery_name": name, "src": f"https://img.test/{index}.jpg?a=1&b=2",
            "capture": {"date": capture}, "classification": {"status": status,
            "detected_label": "公開しない内部候補"}, "taxonomy": {"name": "推測候補"},
            "article": {"article_id": article_id, "article_path": article_path,
                        "url": url, "title": title, "published": published}}


def portal(*rows):
    return {"version": 1, "observations": list(rows)}


@pytest.mark.parametrize(("name", "included"), [
    ("不明", True), ("候補?", True), ("候補？", True), ("候補", False)])
def test_exact_eligibility_rule(name, included):
    assert is_research_observation(observation(0, name)) is included


def test_legacy_review_alone_is_not_eligible():
    assert build_research_cases(portal(observation(0, "候補", status="legacy_review"))) == []


def test_grouping_uses_exact_name_and_article_identity():
    rows = [observation(3, "不明"), observation(1, "不明"),
            observation(2, "不明", article_id="b"),
            observation(4, "候補?", article_id="a")]
    cases = build_research_cases(portal(*rows))
    assert len(cases) == 3
    grouped = next(case for case in cases if case["gallery_name"] == "不明"
                   and case["article"]["article_id"] == "a")
    assert [photo["production_index"] for photo in grouped["photos"]] == [1, 3]
    assert grouped["photo_count"] == 2
    assert sum(case["photo_count"] for case in cases) == 4


@pytest.mark.parametrize(("missing", "expected_identity"), [
    ((), "article_id"), (("article_id",), "article_path"),
    (("article_id", "article_path"), "url")])
def test_article_identity_priority(missing, expected_identity):
    first, second = observation(0), observation(1)
    for key in missing:
        first["article"][key] = second["article"][key] = None
    first["article"][expected_identity] = second["article"][expected_identity] = "same"
    # Lower-priority values must not split an identity selected earlier.
    if expected_identity != "url":
        second["article"]["url"] = "https://different.test"
    assert len(build_research_cases(portal(first, second))) == 1


def test_missing_article_identity_never_merges_observations():
    rows = [observation(i) for i in (0, 1)]
    for row in rows:
        row["article"] = {"title": "same"}
    assert len(build_research_cases(portal(*rows))) == 2


def test_status_priority_and_candidate_is_exact_only():
    conflict = observation(0, "不明", status="manual_review_name_conflict")
    cases = build_research_cases(portal(conflict, observation(1, "不明", article_id="b"),
                                         observation(2, "候補？", article_id="c")))
    assert {case["status"] for case in cases} == {"名称確認中", "未同定", "候補名あり"}
    page = render_research_page(build_research_model(portal(conflict, observation(2, "候補？", article_id="c"))))
    assert "現在の候補名" in page and "候補？" in page
    for forbidden in ("legacy_review", "manual_review_name_conflict", "detected_label",
                      "公開しない内部候補", "推測候補"):
        assert forbidden not in page


def test_capture_dates_use_capture_only_dedup_and_missing_display():
    rows = [observation(0, capture="2026/07/08", title="2099年1月1日富士山"),
            observation(1, capture="2026-07-08"), observation(2, capture="2026/07/09")]
    case = build_research_cases(portal(*rows))[0]
    assert case["capture_dates"] == ["2026-07-08", "2026-07-09"]
    assert case["latest_capture_date"] == "2026-07-09"
    page = render_research_page(build_research_model(portal(observation(4, "候補?", capture=None,
        title="2026年7月8日浜松市"))))
    assert "撮影日</dt><dd>不明" in page
    assert "2026年7月8日浜松市" in page  # Article context only.


def test_sorting_capture_then_published_then_stable_identity():
    rows = [observation(0, article_id="old", capture="2025/01/01"),
            observation(1, article_id="new", capture="2026/01/01"),
            observation(2, article_id="undated-new", capture=None, published="2026-01-01T00:00:00Z"),
            observation(3, article_id="undated-bad", capture="bad", published="bad")]
    assert [case["article"]["article_id"] for case in build_research_cases(portal(*rows))] == [
        "new", "old", "undated-new", "undated-bad"]


def test_render_escapes_article_and_photo_and_links_only_valid_urls():
    linked = observation(0, "候補?<script>", title="記事<&")
    unlinked = observation(1, article_id="b", url="javascript:alert(1)", title="本文<&")
    page = render_research_page(build_research_model(portal(linked, unlinked)))
    assert "<script>" not in page and "候補?&lt;script&gt;" in page
    assert "記事&lt;&amp;" in page and "本文&lt;&amp;" in page
    assert 'href="https://example.test/a?x=1&amp;y=2" target="_top"' in page
    assert 'href="javascript:' not in page
    assert 'href="https://img.test/0.jpg?a=1&amp;b=2"' in page


def test_page_and_css_design_contract():
    page = render_research_page(build_research_model(portal(observation(0))))
    css = (ROOT / "assets/research.css").read_text()
    assert "❓ 不明キノコ研究室" in page and "同定が確定していることを意味しません" in page
    assert 'assets/research.css' in page and 'class="research-photos"' in page
    assert 'src="assets/gallery.js"' in page
    assert "@media (max-width: 600px)" in css and "padding: 18px 12px" in css
    assert "overflow-wrap: anywhere" in css and "background: #fff" in css
    assert "padding: 0" in css and "opacity: 1" in css
    assert "outer-panel" not in page + css


def test_generated_counts_are_derived_and_assets_copied(tmp_path):
    assets = tmp_path / "source-assets"; assets.mkdir()
    (assets / "research.css").write_text("mobile")
    model = generate_research_page(portal(observation(0), observation(1)), tmp_path, assets)
    assert model["case_count"] == 1 and model["photo_count"] == 2
    assert "調査中 <strong>1</strong>件" in (tmp_path / "research.html").read_text()
    assert (tmp_path / "assets/research.css").read_text() == "mobile"


def test_failure_isolation_and_no_stale_read(monkeypatch):
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: (_ for _ in ()).throw(AssertionError("stale")))
    assert main.generate_research_page_if_fresh({"build_ok": False}) is None
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: {"version": 1})
    monkeypatch.setattr(main, "generate_research_page", lambda *args: (_ for _ in ()).throw(RuntimeError("boom")))
    assert main.generate_research_page_if_fresh({"build_ok": True}) is None


def test_index_link_only_after_success_with_derived_count(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "copy_shared_assets", lambda: None)
    main.generate_index({}, {}, feature_search_available=True,
                        research_summary={"case_count": 2, "photo_count": 9})
    page = (tmp_path / "index.html").read_text()
    assert "特徴から探す" in page and page.index("特徴から探す") < page.index("不明キノコ研究室")
    assert "研究室を見る（2件）" in page
    main.generate_index({}, {}, research_summary=None)
    assert "不明キノコ研究室" not in (tmp_path / "index.html").read_text()


def test_future_schema_rejected():
    with pytest.raises(ValueError, match="version 1"):
        build_research_cases({"version": 2})
