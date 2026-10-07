"""Presentation-only eligibility across the existing list renderers."""
import copy
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
import pytest
import main
from detail_ui import build_detail_views, render_detail_sections
from feature_ui import build_feature_search_model, render_feature_page
from season_ui import render_season_page


def portal(status):
    return {
        "version": 1,
        "subjects": [
            {"gallery_name": "アリンク", "mushroom_master_id": "explicit", "cover_src": "photo.jpg", "capture_month_counts": {"5": 1}},
            # Same canonical name as master, but deliberately NOT linked.
            {"gallery_name": "ア毒キノコ", "mushroom_master_id": None, "cover_src": "other.jpg", "capture_month_counts": {"5": 1}},
        ],
        "reference_data": {"mushroom_master": {"entries": [{
            "mushroom_id": "explicit", "canonical_name_ja": "ア毒キノコ",
            "food_safety": {"status": status, "source_ids": []},
            "features": {"summary": "毒 注意という文言から推測してはいけない"},
        }]}},
    }


def facets():
    return {"version": 1, "groups": [{"group_id": "cap", "label": "傘"}],
            "facets": [{"facet_id": "cap_sticky", "group_id": "cap", "label": "粘性"}],
            "entries": [{"mushroom_id": "explicit", "assignments": [{"facet_id": "cap_sticky"}]}]}


@pytest.mark.parametrize("status", ["poisonous_confirmed", "edibility_reported", "unknown", "caution", "unconfirmed", "", None])
def test_only_explicit_poison_status_in_all_list_renderers(status, monkeypatch, tmp_path):
    data = portal(status)
    before = copy.deepcopy(data)
    views = build_detail_views(data)
    expected = ["アリンク"] if status == "poisonous_confirmed" else []
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    grouped = main.generate_gallery([
        {"alt": "アリンク", "src": "photo.jpg"},
        {"alt": "ア毒キノコ", "src": "other.jpg"},
    ], {}, detail_views=views)
    main.generate_index(grouped, {}, detail_views=views)
    pages = [
        (tmp_path / "あ行.html").read_text(),
        render_season_page(data, lambda value: value),
        render_feature_page(build_feature_search_model(data, facets())),
    ]
    for page in pages:
        soup = BeautifulSoup(page, "html.parser")
        marked = soup.select('.mushroom-card[data-food-safety="poisonous_confirmed"]')
        assert [card["data-name"] for card in marked] == expected
        assert not soup.select(".poison-spore, .poison-spore-burst")
        assert soup.select_one('script[src="assets/poison-spores.js"]')
    index = (tmp_path / "index.html").read_text()
    rows = json.loads(re.search(r"window.ALL_MUSHROOMS = (.*);", index)[1])
    assert [row["name"] for row in rows if row["food_safety_status"] == "poisonous_confirmed"] == expected
    detail = (tmp_path / "アリンク.html").read_text()
    assert 'data-food-safety=' not in detail
    assert 'src="assets/poison-spores.js"' not in detail
    if status == "poisonous_confirmed":
        assert "公的・専門資料に毒性の記載あり" in render_detail_sections(views["アリンク"])
    assert data == before  # No source data mutation, even in memory.
    assert (tmp_path / "assets/poison-spores.js").read_bytes() == Path("assets/poison-spores.js").read_bytes()


def test_no_inference_when_fresh_detail_views_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    grouped = main.generate_gallery([{"alt": "ア毒キノコ", "src": "photo.jpg"}], {}, detail_views={})
    main.generate_index(grouped, {})
    assert 'data-food-safety=' not in (tmp_path / "あ行.html").read_text()
    assert '"food_safety_status": null' in (tmp_path / "index.html").read_text()


def test_feature_filter_inputs_unchanged_by_food_metadata():
    poison = build_feature_search_model(portal("poisonous_confirmed"), facets())
    unknown = build_feature_search_model(portal("unknown"), facets())
    for model in (poison, unknown):
        for row in model["results"]:
            row.pop("food_safety_status")
    assert poison == unknown
