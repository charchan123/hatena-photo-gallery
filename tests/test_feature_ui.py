import copy
import json
from pathlib import Path

import pytest

from feature_ui import (FeatureFacetError, build_feature_search_model,
                        load_feature_facets, render_feature_page,
                        validate_feature_facets)

ROOT = Path(__file__).parents[1]

@pytest.fixture
def data():
    return load_feature_facets(ROOT / "data/feature-facets.json")

@pytest.fixture
def master():
    return json.loads((ROOT / "data/mushroom-master.json").read_text())

def test_repository_data_is_complete_and_evidence_backed(data, master):
    before = copy.deepcopy((data, master))
    assert validate_feature_facets(data, master) is True
    assert (data, master) == before
    assert {e["mushroom_id"] for e in data["entries"]} == {
        e["mushroom_id"] for e in master["entries"]
        if (e.get("features") or {}).get("summary")
    }

def test_future_version_rejected(data, master):
    data["version"] = 2
    with pytest.raises(FeatureFacetError, match="version"):
        validate_feature_facets(data, master)

@pytest.mark.parametrize("collection,key", [("groups","group_id"),("facets","facet_id"),("entries","mushroom_id")])
def test_duplicates_rejected(data, master, collection, key):
    data[collection].append(copy.deepcopy(data[collection][0]))
    with pytest.raises(FeatureFacetError, match=f"duplicate {key}"):
        validate_feature_facets(data, master)

def test_assignment_evidence_and_sources_rejected(data, master):
    assignment = data["entries"][0]["assignments"][0]
    assignment["evidence_text"] = "not exact"
    with pytest.raises(FeatureFacetError, match="kaentake.*rod_cylindrical.*exact"):
        validate_feature_facets(data, master)
    assignment["evidence_text"] = "細長い棒状または円柱状"
    assignment["source_ids"] = []
    with pytest.raises(FeatureFacetError, match="kaentake.*rod_cylindrical.*non-empty"):
        validate_feature_facets(data, master)

def test_model_uses_only_explicit_master_link(data):
    portal = {"version": 1, "subjects": [
        {"gallery_name":"カエンタケ", "cover_src":"a.jpg", "mushroom_master_id":None},
        {"gallery_name":"表示名？", "cover_src":"b.jpg", "mushroom_master_id":"kaentake"},
        {"gallery_name":"unlinked", "cover_src":"c.jpg", "mushroom_master_id":"missing"},
    ]}
    before = copy.deepcopy((portal, data))
    model = build_feature_search_model(portal, data, lambda value: "safe-" + value)
    assert model["coverage_count"] == 1
    assert model["results"][0] == {"gallery_name":"表示名？", "cover_src":"b.jpg", "href":"safe-表示名？.html", "facet_ids":["rod_cylindrical"], "facet_labels":["棒状・円柱状の形"]}
    assert (portal, data) == before

def test_render_has_accessible_and_filter_contract(data):
    portal = {"version":1,"subjects":[{"gallery_name":"表示名", "cover_src":"x.jpg", "mushroom_master_id":"kaentake"}]}
    page = render_feature_page(build_feature_search_model(portal, data, lambda _: "detail"))
    assert "特徴から探す｜キノコ図鑑" in page
    assert 'data-facet="rod_cylindrical"' in page and 'aria-pressed="false"' in page
    assert 'aria-live="polite"' in page and "選択をクリア" in page
    assert 'data-facets="rod_cylindrical"' in page and 'href="detail.html"' in page
    assert "判定する機能ではありません" in page and 'target="_top"' not in page
    assert 'class="mushroom-list feature-results"' in page
    assert 'class="mushroom-card feature-card"' in page
    assert 'class="mushroom-card-thumb"' in page
    assert '<span class="card-fav">☆</span>' in page
    assert 'src="x.jpg?width=400"' in page and 'alt="表示名"' in page
    assert 'class="mushroom-card-name">表示名</div>' in page
    assert "feature-chip" not in page and "feature-chips" not in page

def test_feature_css_leaves_card_layout_to_shared_gallery_styles():
    css = (ROOT / "assets/features.css").read_text()
    assert "grid-template-columns" not in css
    assert ".feature-card" not in css
    assert ".feature-chip" not in css
