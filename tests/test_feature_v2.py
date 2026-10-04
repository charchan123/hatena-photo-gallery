import copy
import json
from pathlib import Path

import pytest

from feature_ui import (FeatureFacetError, TRUSTED_FEATURE_V2_MANIFEST_SHA256,
                        build_feature_search_model, generate_feature_page,
                        render_feature_page, validate_feature_facets)

ROOT = Path(__file__).parents[1]
V2 = ROOT / "audit" / "phase4c9" / "v2"


def _json(name):
    return json.loads((V2 / name).read_text(encoding="utf-8"))


@pytest.fixture
def package():
    return {
        "feature": _json("feature-facets-runtime-candidate-2026-10-03.json"),
        "master": _json("mushroom-master-final-candidate-2026-10-03.json"),
        "sources": _json("sources-final-candidate-2026-10-03.json"),
        "ledger": _json("phase4c9-feature-evidence-ledger-approved-2026-10-03.json"),
        "snapshots": (V2 / "phase4c9-feature-source-snapshots-2026-10-03.jsonl").read_text(),
        "manifest": _json("phase4c9-feature-approval-manifest-2026-10-03.json"),
    }


def _validate(p, mode="review"):
    return validate_feature_facets(
        p["feature"], p["master"], sources=p["sources"],
        evidence_ledger=p["ledger"], source_snapshots=p["snapshots"],
        approval_manifest=p.get("manifest"), mode=mode)


def _assignment(p, mushroom="kaentake", facet="rod_cylindrical"):
    entry = next(row for row in p["feature"]["entries"] if row["mushroom_id"] == mushroom)
    return next(row for row in entry["assignments"] if row["facet_id"] == facet)


def test_exact_approved_package_passes_review_and_production(package):
    before = copy.deepcopy(package)
    assert _validate(package) is True
    assert _validate(package, "production") is True
    assert package == before
    assert TRUSTED_FEATURE_V2_MANIFEST_SHA256 == "2d6f21f31d7e0e33a513c02a5188f563baa4a8e8bbe1f40866501c3780521d05"
    assert sum(len(row["assignments"]) for row in package["feature"]["entries"]) == 373
    assert len(package["ledger"]["held_decisions"]) == 10
    assert len(package["ledger"]["evidence_records"]) == 377
    assert len(package["feature"]["coverage"]["excluded_mushrooms"]) == 12


def test_v1_contract_stays_strict_and_bool_version_is_rejected():
    feature = {"version": 1, "groups": [{"group_id": "g"}],
               "facets": [{"facet_id": "f", "group_id": "g"}],
               "entries": [{"mushroom_id": "m", "assignments": [
                   {"facet_id": "f", "evidence_text": "needle", "source_ids": ["s"]}]}]}
    master = {"entries": [{"mushroom_id": "m", "features":
                            {"summary": "needle text", "source_ids": ["s"]}}]}
    assert validate_feature_facets(feature, master)
    bad = copy.deepcopy(feature); bad["entries"][0]["assignments"][0]["evidence_text"] = "other"
    with pytest.raises(FeatureFacetError, match="exact summary substring"):
        validate_feature_facets(bad, master)
    bad = copy.deepcopy(feature); bad["entries"][0]["assignments"][0]["source_ids"] = ["other"]
    with pytest.raises(FeatureFacetError, match="source_ids do not match"):
        validate_feature_facets(bad, master)
    feature["version"] = True
    with pytest.raises(FeatureFacetError, match="integer"):
        validate_feature_facets(feature, master)


@pytest.mark.parametrize("mutation,match", [
    (lambda p: _assignment(p).update(source_ids=[]), "source_ids.*non-empty"),
    (lambda p: _assignment(p).update(source_ids=["mhlw-kaentake", "mhlw-kaentake"]), "duplicate"),
    (lambda p: _assignment(p).update(source_ids=["missing"]), "unknown source"),
    (lambda p: _assignment(p).update(source_ids=["mhlw-kaentake", "mhlw-dokutsurutake"]), "source set"),
    (lambda p: _assignment(p).update(facet_id="missing"), "unknown facet"),
    (lambda p: p["feature"]["entries"][0].update(mushroom_id="missing"), "unknown mushroom"),
    (lambda p: p["feature"]["entries"][0].update(assignments=[]), "assignments must be non-empty"),
    (lambda p: p["feature"]["entries"][0]["assignments"].append(copy.deepcopy(p["feature"]["entries"][0]["assignments"][0])), "duplicate assignment"),
    (lambda p: _assignment(p).update(evidence_text="semantic mutation"), "digest mismatch"),
    (lambda p: _assignment(p).update(evidence_kind="source_quote"), "digest mismatch"),
    (lambda p: _assignment(p).update(evidence_refs=["FCE-002-1"]), "another mushroom"),
    (lambda p: _assignment(p, "dokutsurutake", "cap_sticky").update(evidence_refs=["FCE-003-1"]), "another facet"),
    (lambda p: p["feature"].update(version=99), "unsupported.*version"),
])
def test_v2_structure_and_binding_failures(package, mutation, match):
    mutation(package)
    with pytest.raises(FeatureFacetError, match=match):
        _validate(package)


@pytest.mark.parametrize("field,value,match", [
    ("quote", "mutated", "quote/offset"),
    ("quote_sha256", "0" * 64, "quote hash"),
    ("char_start", 0, "quote/offset"),
    ("char_end", 1, "quote/offset"),
    ("snapshot_line_start", 1, "line range"),
    ("snapshot_identity", "wrong", "snapshot identity"),
])
def test_evidence_chain_mutations_fail(package, field, value, match):
    package["ledger"]["evidence_records"][0][field] = value
    with pytest.raises(FeatureFacetError, match=match):
        _validate(package)


def test_snapshot_mutations_and_missing_snapshot_fail(package):
    rows = [json.loads(line) for line in package["snapshots"].splitlines()]
    rows[0]["full_extracted_text"] += "x"
    package["snapshots"] = rows
    with pytest.raises(FeatureFacetError, match="snapshot text hash"):
        _validate(package)
    package = copy.deepcopy(package)


def test_coverage_and_ia029_mutations_fail(package):
    package["ledger"]["coverage"]["excluded_mushrooms"][0]["reason"] = ""
    with pytest.raises(FeatureFacetError, match="reason/status"):
        _validate(package)


def test_ia029_ring_cannot_be_added(package):
    entry = next(row for row in package["feature"]["entries"] if row["mushroom_id"] == "tamagotakemodoki")
    assert {row["facet_id"] for row in entry["assignments"]} == {"cap_sticky", "gills", "volva", "stem_scales_pattern"}
    added = copy.deepcopy(entry["assignments"][0]); added["facet_id"] = "ring"
    entry["assignments"].append(added)
    with pytest.raises(FeatureFacetError):
        _validate(package)


@pytest.mark.parametrize("key", ["manifest", "ledger", "feature", "master", "sources"])
def test_production_rejects_absent_or_mutated_approval_inputs(package, key):
    if key == "manifest":
        package["manifest"] = None
        match = "requires approval manifest"
    else:
        target = package[key]
        target["candidate_mutation"] = True
        match = "hash-pinned approved package"
    with pytest.raises(FeatureFacetError, match=match):
        _validate(package, "production")


def test_v2_generation_requires_production_validation(package, tmp_path):
    portal = {"version": 1, "subjects": []}
    with pytest.raises(FeatureFacetError, match="requires approval manifest"):
        generate_feature_page(portal, package["feature"], tmp_path, ROOT / "assets", str,
                              mushroom_master=package["master"], sources=package["sources"],
                              evidence_ledger=package["ledger"], source_snapshots=package["snapshots"])


def test_qualifiers_survive_model_and_render(package):
    qualified = [(entry["mushroom_id"], assignment) for entry in package["feature"]["entries"]
                 for assignment in entry["assignments"] if assignment.get("qualifiers")]
    mushroom_id, assignment = qualified[0]
    portal = {"version": 1, "subjects": [{"gallery_name": "条件表示", "cover_src": "x.jpg",
                                           "mushroom_master_id": mushroom_id}]}
    model = build_feature_search_model(portal, package["feature"], lambda _: "detail")
    detail = next(row for row in model["results"][0]["assignments"]
                  if row["facet_id"] == assignment["facet_id"])
    assert detail["evidence_text"] == assignment["evidence_text"]
    assert detail["qualifiers"] == assignment["qualifiers"]
    page = render_feature_page(model)
    assert assignment["evidence_text"] in page
    assert all(value in page for value in assignment["qualifiers"])
    assert "同じ個体で同時に現れることを保証" in page
    assert "特徴だけでキノコの種類を判定" in page


def test_missing_and_identity_swapped_snapshots_fail(package):
    rows = [json.loads(line) for line in package["snapshots"].splitlines()]
    package["snapshots"] = rows[1:]
    with pytest.raises(FeatureFacetError, match="missing snapshot"):
        _validate(package)
    package["snapshots"] = rows
    rows[0]["snapshot_identity"], rows[1]["snapshot_identity"] = rows[1]["snapshot_identity"], rows[0]["snapshot_identity"]
    with pytest.raises(FeatureFacetError, match="snapshot identity"):
        _validate(package)


def test_held_and_retired_evidence_cannot_be_promoted(package):
    held_ref = package["ledger"]["held_decisions"][0]["evidence_records"][0]["evidence_id"]
    _assignment(package)["evidence_refs"] = [held_ref]
    with pytest.raises(FeatureFacetError, match="held or retired"):
        _validate(package)
    retired_ref = package["ledger"]["retired_citations"][0]["evidence_id"]
    _assignment(package)["evidence_refs"] = [retired_ref]
    with pytest.raises(FeatureFacetError, match="held or retired"):
        _validate(package)


@pytest.mark.parametrize("mutation", [
    lambda p: p["ledger"]["coverage"]["excluded_mushrooms"].pop(),
    lambda p: p["ledger"]["coverage"]["excluded_mushrooms"].append(
        {"mushroom_id": p["feature"]["entries"][0]["mushroom_id"], "reason": "x", "status": "x"}),
    lambda p: p["master"]["entries"].pop(0),
])
def test_coverage_set_failures(package, mutation):
    mutation(package)
    with pytest.raises(FeatureFacetError):
        _validate(package)


def test_held_boundary_and_candidate_self_approval_fail(package):
    package["ledger"]["held_decisions"].pop()
    with pytest.raises(FeatureFacetError, match="boundary"):
        _validate(package)
    package["ledger"] = _json("phase4c9-feature-evidence-ledger-approved-2026-10-03.json")
    package["feature"]["approved"] = True
    with pytest.raises(FeatureFacetError, match="hash-pinned"):
        _validate(package, "production")
