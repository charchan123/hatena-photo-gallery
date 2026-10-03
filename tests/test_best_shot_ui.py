import copy
import json
from pathlib import Path

import pytest

import best_shot_ui
import main


def observation(oid="obs-1", captured="2025-09-17", name="タマゴタケ", src="photo.jpg", article=None):
    return {
        "observation_id": oid,
        "gallery_name": name,
        "src": src,
        "capture": {"date": captured, "month": 9},
        "article": article,
        "published": "2099-01-01",
        "updated": "2099-01-02",
    }


def portal(*rows):
    return {"version": 1, "observations": list(rows or (observation(),))}


def entry(sid="best-1", oid="obs-1", order=1, comment="本人が選んだ一枚", **extra):
    return {"selection_id": sid, "observation_id": oid, "comment": comment, "order": order, **extra}


def config(entries=None, annual=None):
    return {"version": 1, "entries": [entry()] if entries is None else entries,
            "annual_best": {} if annual is None else annual}


def test_schema_version_empty_and_safe_missing_annual_default():
    model = best_shot_ui.build_best_shot_model({"version": 1, "entries": []}, portal())
    assert model == {"entry_count": 0, "year_count": 0, "latest_year": None, "years": []}
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model({"version": 2, "entries": []}, portal())
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model({"version": 1}, portal())


@pytest.mark.parametrize("entries", [
    [entry(), entry("best-1", "obs-2")],
    [entry(), entry("best-2", "obs-1")],
])
def test_duplicate_stable_references_rejected(entries):
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model(config(entries), portal(observation(), observation("obs-2")))


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "1"])
def test_order_must_be_positive_integer(bad):
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model(config([entry(order=bad)]), portal())


def test_comment_contract():
    for comment in ("", "   ", "x" * 201):
        with pytest.raises(best_shot_ui.BestShotConfigError):
            best_shot_ui.build_best_shot_model(config([entry(comment=comment)]), portal())
    for annual_comment in ("", "   ", "x" * 201):
        with pytest.raises(best_shot_ui.BestShotConfigError):
            best_shot_ui.build_best_shot_model(
                config([entry(annual_comment=annual_comment)]), portal()
            )


def test_resolution_uses_portal_fields_and_capture_date_only():
    row = observation(article={"title": "2039年 富士山", "url": "https://example.com/day"})
    cfg = config([entry(location="明示した場所", year=1999)])
    with pytest.raises(best_shot_ui.BestShotConfigError):  # duplicated derived fields are forbidden
        best_shot_ui.build_best_shot_model(cfg, portal(row))
    resolved = best_shot_ui.build_best_shot_model(config([entry(location="明示した場所")]), portal(row))["years"][0]["months"][0]["entries"][0]
    assert (resolved["year"], resolved["month"], resolved["gallery_name"], resolved["src"]) == (2025, 9, "タマゴタケ", "photo.jpg")
    assert resolved["article_title"] == "2039年 富士山"
    assert resolved["location"] == "明示した場所"


def test_missing_or_nonunique_observation_and_capture_date_rejected():
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model(config(), portal(observation("other")))
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model(config(), portal(observation(), observation()))
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model(config(), portal(observation(captured=None)))


def test_month_limit_and_unique_order():
    rows = [observation(f"obs-{i}") for i in range(1, 5)]
    three = [entry(f"best-{i}", f"obs-{i}", i) for i in range(1, 4)]
    assert best_shot_ui.build_best_shot_model(config(three), portal(*rows))["entry_count"] == 3
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model(config(three + [entry("best-4", "obs-4", 4)]), portal(*rows))
    with pytest.raises(best_shot_ui.BestShotConfigError):
        best_shot_ui.build_best_shot_model(config([entry(), entry("best-2", "obs-2")]), portal(*rows))


def test_descending_year_month_and_ascending_manual_order_without_zero_months():
    rows = [observation("a", "2024-01-02"), observation("b", "2025-06-02"),
            observation("c", "2025-06-03"), observation("d", "2025-09-01")]
    entries = [entry("a", "a", 1), entry("b", "b", 2), entry("c", "c", 1), entry("d", "d", 1)]
    model = best_shot_ui.build_best_shot_model(config(entries), portal(*rows))
    assert [y["year"] for y in model["years"]] == [2025, 2024]
    assert [m["month"] for m in model["years"][0]["months"]] == [9, 6]
    assert [e["selection_id"] for e in model["years"][0]["months"][1]["entries"]] == ["c", "b"]
    assert "2月" not in best_shot_ui.render_best_shot_page(model)


def test_annual_best_validation_and_monthly_card_remains():
    model = best_shot_ui.build_best_shot_model(
        config([entry(annual_comment="年間だけのコメント")], annual={"2025": "best-1"}),
        portal(),
    )
    page = best_shot_ui.render_best_shot_page(model)
    assert "2025年 年間ベストショット" in page
    assert page.count('data-selection-id="best-1"') == 2
    assert "🏆 年間ベスト" in page
    assert page.count("本人が選んだ一枚") == 1
    assert page.count("年間だけのコメント") == 1
    for annual in ({"2025": "missing"}, {"2024": "best-1"}, {"2025": "best-1", "2026": "best-1"}):
        with pytest.raises(best_shot_ui.BestShotConfigError):
            best_shot_ui.build_best_shot_model(config(annual=annual), portal())
    assert "年間ベストショット" not in best_shot_ui.render_best_shot_page(
        best_shot_ui.build_best_shot_model(config(), portal()))


def test_html_is_escaped_location_is_explicit_and_only_http_article_links():
    row = observation(name='<b>名</b>', src='x&quot; onerror="bad',
                      article={"title": '記事" onclick="bad', "url": 'javascript:alert(1)'})
    model = best_shot_ui.build_best_shot_model(
        config([entry(comment="<script>bad</script>", location="<山>")]), portal(row))
    page = best_shot_ui.render_best_shot_page(model)
    assert "<script>bad</script>" not in page and "&lt;script&gt;bad&lt;/script&gt;" in page
    assert "&lt;b&gt;名&lt;/b&gt;" in page and "場所：&lt;山&gt;" in page
    assert "この日の観察記録を見る" not in page
    no_location = best_shot_ui.render_best_shot_page(
        best_shot_ui.build_best_shot_model(config(), portal(observation())))
    assert "場所：" not in no_location


def test_best_shot_document_loads_shared_gallery_js_for_visibility_and_iframe_height():
    page = best_shot_ui.render_best_shot_page(
        best_shot_ui.build_best_shot_model(config(), portal())
    )
    assert '<link rel="stylesheet" href="assets/gallery.css">' in page
    assert '<script src="assets/gallery.js" defer></script>' in page



def test_best_shot_pc_visual_contract():
    page = best_shot_ui.render_best_shot_page(
        best_shot_ui.build_best_shot_model(config(), portal())
    )
    css = (Path("assets") / "best-shots.css").read_text(encoding="utf-8")
    assert 'class="best-shots-index"' in page
    assert 'class="best-shots-hub"' in page
    assert 'class="best-shots-hero"' in page
    assert "BEST SHOTS" in page
    assert "← 図鑑へ戻る" in page
    assert 'id="gallery-content-root"' in page
    assert "body.best-shots-index" in css
    assert "width:min(100%,1180px)" in css
    assert 'url("research-lab-final.webp")' in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert ".best-shots-index .annual-best" in css
    assert ".best-shots-index .annual-best { margin:0 0 28px; padding:18px; border:1px solid #242a26; border-radius:16px; background:#0c0f0d;" in css
    assert ".best-shots-index .annual-best > h2 { margin:0 0 14px; color:#f2f5f2;" in css
    assert ".best-shots-index .best-shot-card--hero" in css
    assert "background:#fff" in css
    assert "background:#111412" not in css
    assert ".best-shots-index .best-shot-card--hero .best-shot-card__body h3 { color:#294a32; }" in css
    assert ".best-shots-index .best-shot-card--hero .best-shot-badge" in css
    assert "background:#fff0ad; color:#6d5200" in css
    assert "@media (max-width:680px)" in css


def test_archive_latest_capture_year_and_all_year_pages(tmp_path):
    rows = [observation("old", "2024-04-01"), observation("new", "2026-06-01")]
    cfg = config([entry("old", "old", 1), entry("new", "new", 1)])
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")
    assets = tmp_path / "source-assets"; assets.mkdir()
    (assets / "best-shots.css").write_text("body{}", encoding="utf-8")
    output = tmp_path / "output"
    model = best_shot_ui.generate_best_shot_pages(portal(*rows), config_path, output, assets)
    assert model["latest_year"] == 2026
    assert (output / "best-shots-2026.html").exists() and (output / "best-shots-2024.html").exists()
    landing = (output / "best-shots.html").read_text(encoding="utf-8")
    assert "2026年のベストショット" in landing and 'best-shots-2024.html' in landing
    assert 'best-shots-2026.html' not in landing


def test_empty_model_and_index_entrance_behavior(tmp_path, monkeypatch):
    production = best_shot_ui.load_best_shot_config(Path("data/best-shots.json"))
    assert production["version"] == 1
    assert isinstance(production["entries"], list)
    model = best_shot_ui.build_best_shot_model(
        {"version": 1, "entries": [], "annual_best": {}}, portal()
    )
    assert "ベストショットは現在選定中です" in best_shot_ui.render_best_shot_page(model)
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "copy_shared_assets", lambda: None)
    monkeypatch.setattr(main, "render_record_cards", lambda *args, **kwargs: "record")
    main.generate_index({}, {}, best_shot_summary={"entry_count": 0})
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "ベストショット" not in page
    main.generate_index({}, {}, observation_records=[{"x": 1}], research_summary={"case_count": 1},
                        best_shot_summary={"entry_count": 2})
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert page.index("不明キノコ研究室") < page.index("ベストショット")
    assert "観察記録" not in page
    assert "おすすめキノコ" not in page


def test_fresh_gate_and_failure_isolation(monkeypatch):
    called = []
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda path: called.append(path) or portal())
    monkeypatch.setattr(main, "generate_best_shot_pages", lambda *args: (_ for _ in ()).throw(ValueError("bad")))
    assert main.generate_best_shot_pages_if_fresh({"build_ok": False}) is None
    assert called == []
    assert main.generate_best_shot_pages_if_fresh({"build_ok": True}) is None
    assert called == [main.PORTAL_DATA_FILE]


def test_config_contract_contains_only_manual_metadata_and_reference():
    allowed = {"selection_id", "observation_id", "comment", "annual_comment", "location", "order"}
    assert best_shot_ui.ENTRY_FIELDS == allowed
    assert config(annual={"2025": "best-1"})["annual_best"]["2025"] == "best-1"
