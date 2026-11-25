from copy import deepcopy
import json

import pytest

from detail_ui import build_detail_views, render_detail_sections
from mushroom_knowledge import load_mushroom_master, load_sources
from portal_data import GUIDE_EXPANSION_FILE, project_guide_expansion


def published_subject(name, *, status="externally_verified"):
    return {
        "gallery_name": name, "mushroom_master_id": None, "knowledge_available": False,
        "photo_count": 1, "taxonomy": {
            "canonical_name": name, "subject_type": "mushroom", "mushroom_master_id": None,
            "verification_status": status,
        },
    }


def observation(name):
    return {
        "observation_id": name, "gallery_name": name, "mushroom_master_id": None,
        "classification": {
            "status": "confirmed_named_mushroom", "taxonomy_canonical_name": name,
            "taxonomy_match_type": "canonical_exact",
        },
    }


def test_real_expansion_preserves_baseline_and_gates_exact_published_subjects():
    names = ["タマゴテングタケモドキ", "テングタケダマシ", "キホウキタケ", "キタマゴタケ",
             "ヤマドリタケ？", "クリフウセンタケ", "ブドウニガイグチ", "ヤシャイグチ"]
    subjects = [published_subject(n) for n in names]
    photos = [observation(n) for n in names]
    subjects[3]["taxonomy"]["verification_status"] = "project_seed"
    photos[5]["classification"]["taxonomy_match_type"] = "alias_exact"
    photos[6]["classification"]["status"] = "legacy_undetected"
    subjects[7]["taxonomy"]["mushroom_master_id"] = "legacy-reference"
    data = {
        "version": 1, "subjects": subjects, "observations": photos,
        "summary": {"master_linked_subject_count": 0, "master_unlinked_subject_count": len(names)},
        "reference_data": {"sources": load_sources(), "mushroom_master": load_mushroom_master()},
    }
    baseline = deepcopy(data)
    actual = project_guide_expansion(data)
    assert data == baseline
    assert actual["reference_data"]["mushroom_master"] == baseline["reference_data"]["mushroom_master"]
    assert actual["reference_data"]["sources"] == baseline["reference_data"]["sources"]
    assert len(actual["reference_data"]["guide_expansion"]["entries"]) == 20
    assert actual["summary"]["knowledge_record_count"] == 161
    assert actual["summary"]["source_count"] == 453
    assert actual["summary"]["master_linked_subject_count"] == 3
    assert actual["summary"]["master_unlinked_subject_count"] == 5
    for original, updated in zip(baseline["observations"], actual["observations"]):
        assert original == {**updated, "mushroom_master_id": None}
    for original, updated in zip(baseline["subjects"], actual["subjects"]):
        if original["gallery_name"] in names[:3]:
            assert updated["knowledge_available"]
        assert original == {**updated, "mushroom_master_id": None, "knowledge_available": False}
    views = build_detail_views(actual)
    labels = ("毒性の記載があります", "不食との記載があります", "食毒の記載が異なります")
    for name, label in zip(names, labels):
        page = render_detail_sections(views[name])
        assert label in page and 'class="knowledge-warning"' in page
    assert all(views[name]["knowledge"] is None for name in names[3:])


def test_expansion_rejects_duplicate_ids_missing_sources_and_uncertain_labels(tmp_path):
    data = {"reference_data": {"sources": load_sources(), "mushroom_master": load_mushroom_master()}}
    expansion = json.loads(GUIDE_EXPANSION_FILE.read_text(encoding="utf-8"))
    path = tmp_path / "candidate.json"
    for field, replacement, problem in (
        ("canonical_name_ja", "ブドウニガイグチ？", "invalid guide expansion name"),
        ("mushroom_id", "shiitake", "duplicate mushroom_id"),
        ("name_ja_sources", ["bad-reference"], "unknown sources"),
    ):
        candidate = deepcopy(expansion)
        candidate["entries"][0][field] = replacement
        path.write_text(json.dumps(candidate), encoding="utf-8")
        with pytest.raises(ValueError, match=problem):
            project_guide_expansion(data, path)
