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


def test_runtime_files_are_exact_approved_bytes(package):
    for runtime, approved in (
        ("feature-facets.json", "feature-facets-runtime-candidate-2026-10-03.json"),
        ("mushroom-master.json", "mushroom-master-final-candidate-2026-10-03.json"),
        ("sources.json", "sources-final-candidate-2026-10-03.json"),
    ):
        assert (ROOT / "data" / runtime).read_bytes() == (V2 / approved).read_bytes()
    assert package["feature"]["version"] == 2
    assert len(package["master"]["entries"]) == 141
    assert len(package["sources"]["sources"]) == 419
    assert _validate(package, "production") is True


def test_main_feature_cutover_uses_production_gate(package, monkeypatch, tmp_path):
    import main

    portal = {"version": 1, "subjects": [
        {"gallery_name": "test", "cover_src": "test.jpg", "mushroom_master_id": "kaentake"}
    ], "reference_data": {"mushroom_master": package["master"]}}
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda _: portal)
    monkeypatch.setattr(main, "FEATURE_FACETS_FILE", ROOT / "data/feature-facets.json")
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "ASSETS_DIR", str(ROOT / "assets"))
    assert main.generate_feature_page_if_fresh({"build_ok": True}) is True
    page = (tmp_path / "features.html").read_text()
    assert "feature-qualifier" in page
    assert "判定する機能ではありません" in page
    assert TRUSTED_FEATURE_V2_MANIFEST_SHA256 not in page


def test_main_rejects_missing_approval_without_render_or_fallback(package, monkeypatch, tmp_path):
    import main
    from feature_ui import load_feature_v2_inputs

    inputs = load_feature_v2_inputs()
    inputs["approval_manifest"] = None
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda _: {"version": 1, "subjects": []})
    monkeypatch.setattr(main, "FEATURE_FACETS_FILE", ROOT / "data/feature-facets.json")
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "load_feature_v2_inputs", lambda: inputs)
    monkeypatch.setattr(main, "generate_feature_page", lambda *a, **k: pytest.fail("must not render"))
    assert main.generate_feature_page_if_fresh({"build_ok": True}) is False
    assert not (tmp_path / "features.html").exists()


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

def test_independent_evidence_and_source_set_difference_are_valid(package):
    assignment = _assignment(package, "dokutsurutake", "cap_sticky")
    master = next(row for row in package["master"]["entries"]
                  if row["mushroom_id"] == "dokutsurutake")
    assert assignment["evidence_text"] not in master["features"]["summary"]
    assert set(assignment["source_ids"]) != set(master["features"]["source_ids"])
    assert _validate(package) is True


@pytest.mark.parametrize("mutation,match", [
    (lambda p: p["ledger"]["evidence_records"][0].update(source_id="missing"),
     "unknown source"),
    (lambda p: p["ledger"]["evidence_records"][0].update(decision_id="wrong"),
     "decision binding"),
    (lambda p: p["ledger"]["evidence_records"][0].update(evidence_kind="source_quote"),
     "evidence_kind mismatch"),
    (lambda p: p["ledger"]["evidence_records"][0].update(evidence_text="wrong"),
     "evidence_text mismatch"),
    (lambda p: p["ledger"]["evidence_records"][0].update(qualifiers=["wrong"]),
     "qualifier mismatch"),
    (lambda p: p["ledger"]["evidence_records"][0].update(extracted_text_sha256="0" * 64),
     "extracted_text_sha256 mismatch"),
    (lambda p: p["ledger"]["evidence_records"][0].update(text_snapshot_sha256="0" * 64),
     "text_snapshot_sha256 mismatch"),
    (lambda p: p["ledger"]["evidence_records"][0].update(original_response_sha256="0" * 64),
     "original_response_sha256 mismatch"),
])
def test_record_to_runtime_and_snapshot_binding_failures(package, mutation, match):
    mutation(package)
    with pytest.raises(FeatureFacetError, match=match):
        _validate(package)


def test_duplicate_approved_decision_id_fails(package):
    rows = package["ledger"]["approved_assignments"]
    rows[1]["decision_id"] = rows[0]["decision_id"]
    with pytest.raises(FeatureFacetError, match="duplicate decision_id"):
        _validate(package)


def test_candidate_human_approval_cannot_be_rewritten(package):
    _assignment(package)["review"]["human_approval"] = True
    with pytest.raises(FeatureFacetError, match="historical null"):
        _validate(package)


def test_extra_snapshot_and_snapshot_source_binding_fail(package):
    rows = [json.loads(line) for line in package["snapshots"].splitlines()]
    extra = copy.deepcopy(rows[0])
    extra["source_id"] = "unexpected-extra-snapshot"
    rows.append(extra)
    package["snapshots"] = rows
    with pytest.raises(FeatureFacetError, match="snapshot source set/count"):
        _validate(package)

    package["snapshots"] = [json.loads(line) for line in _jsonl().splitlines()]
    package["snapshots"][0]["source_url"] = "https://example.invalid/"
    with pytest.raises(FeatureFacetError, match="snapshot source binding"):
        _validate(package)


def _jsonl():
    return (V2 / "phase4c9-feature-source-snapshots-2026-10-03.jsonl").read_text()


@pytest.mark.parametrize("target,key,match", [
    ("feature", "eligible_mushroom_ids", "candidate eligible coverage mismatch"),
    ("feature", "included_mushroom_ids", "candidate included coverage mismatch"),
    ("ledger", "eligible_mushroom_ids", "ledger eligible coverage mismatch"),
    ("ledger", "included_mushroom_ids", "ledger included coverage mismatch"),
])
def test_recorded_coverage_id_sets_must_match_recomputed_sets(package, target, key, match):
    package[target]["coverage"][key].pop()
    with pytest.raises(FeatureFacetError, match=match):
        _validate(package)


@pytest.mark.parametrize("target,key,value,match", [
    ("feature", "assignment_count", 372, "candidate coverage count mismatch"),
    ("feature", "entry_count", 126, "candidate coverage count mismatch"),
    ("feature", "active_facet_count", 19, "candidate coverage count mismatch"),
    ("ledger", "assignment_count", 372, "ledger coverage count mismatch"),
])
def test_recorded_coverage_counts_must_match_runtime(package, target, key, value, match):
    package[target]["coverage"][key] = value
    with pytest.raises(FeatureFacetError, match=match):
        _validate(package)


def test_recorded_held_assignment_set_must_match_ledger(package):
    package["feature"]["coverage"]["held_assignments"].pop()
    with pytest.raises(FeatureFacetError, match="candidate held assignment coverage mismatch"):
        _validate(package)


@pytest.mark.parametrize("mushroom,facet,expected", [
    ("dokutsurutake", "cap_sticky", "湿時という条件を保持"),
    ("haratake", "stem_solid", "成長段階"),
    ("benitengutake", "cap_scales_warts", "脱落／成長による消失"),
    ("dokutsurutake", "volva", "完全な袋状つぼに限定しない"),
    ("dokuyamadori", "blue_stain", "変色する部位・損傷条件"),
    ("yakoutake", "gelatinous", "傘の被覆層のみ"),
])
def test_representative_qualifier_categories_survive_model_and_render(
        package, mushroom, facet, expected):
    assignment = _assignment(package, mushroom, facet)
    portal = {"version": 1, "subjects": [{
        "gallery_name": f"条件表示-{mushroom}",
        "cover_src": "x.jpg",
        "mushroom_master_id": mushroom,
    }]}
    model = build_feature_search_model(portal, package["feature"], lambda _: "detail")
    detail = next(row for row in model["results"][0]["assignments"]
                  if row["facet_id"] == facet)
    assert detail["evidence_text"] == assignment["evidence_text"]
    assert detail["qualifiers"] == assignment["qualifiers"]
    page = render_feature_page(model)
    assert assignment["evidence_text"] in page
    assert expected in page
    assert all(value in page for value in assignment["qualifiers"])


def test_exact_substring_flag_must_match_quote(package):
    record = next(row for row in package["ledger"]["evidence_records"]
                  if row["evidence_kind"] == "source_quote")
    record["evidence_text_exact_substring_of_this_quote"] = False
    with pytest.raises(FeatureFacetError, match="exact-substring flag mismatch"):
        _validate(package)

def test_unused_active_facet_fails(package):
    package["feature"]["facets"].append({
        "facet_id": "audit_unused_facet",
        "group_id": package["feature"]["groups"][0]["group_id"],
        "label": "監査用未使用facet",
    })
    with pytest.raises(FeatureFacetError, match="unused facet_id"):
        _validate(package)


def test_non_supporting_active_evidence_fails(package):
    package["ledger"]["evidence_records"][0]["review_result"] = "does_not_support_this_facet"
    with pytest.raises(FeatureFacetError, match="not supporting evidence"):
        _validate(package)


def test_uncovered_species_cannot_gain_inferred_assignment(package):
    excluded_id = package["feature"]["coverage"]["excluded_mushrooms"][0]["mushroom_id"]
    copied = copy.deepcopy(package["feature"]["entries"][0]["assignments"][0])
    package["feature"]["entries"].append({
        "mushroom_id": excluded_id,
        "assignments": [copied],
    })
    with pytest.raises(FeatureFacetError):
        _validate(package)


def test_production_rejects_mutated_manifest_and_snapshot_bundle(package):
    package["manifest"]["approval_timestamp"] = "2099-01-01T00:00:00+09:00"
    with pytest.raises(FeatureFacetError, match="hash-pinned approved package"):
        _validate(package, "production")

    package = copy.deepcopy(package)
    package["manifest"] = _json("phase4c9-feature-approval-manifest-2026-10-03.json")
    rows = [json.loads(line) for line in package["snapshots"].splitlines()]
    package["snapshots"] = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in reversed(rows)
    ) + "\n"
    with pytest.raises(FeatureFacetError, match="hash-pinned approved package"):
        _validate(package, "production")


def test_trusted_manifest_pin_mismatch_fails(package, monkeypatch):
    import feature_ui

    filename, _ = feature_ui._V2_FILES["manifest"]
    monkeypatch.setitem(
        feature_ui._V2_FILES,
        "manifest",
        (filename, "0" * 64),
    )
    with pytest.raises(FeatureFacetError, match="trusted manifest artifact hash mismatch"):
        _validate(package, "production")

def test_ring_mobility_evidence_text_survives_model_and_render(package):
    assignment = _assignment(package, "karakasatake", "ring")
    assert "可動性" in assignment["evidence_text"]
    portal = {"version": 1, "subjects": [{
        "gallery_name": "可動性つば表示",
        "cover_src": "x.jpg",
        "mushroom_master_id": "karakasatake",
    }]}
    model = build_feature_search_model(portal, package["feature"], lambda _: "detail")
    detail = next(row for row in model["results"][0]["assignments"]
                  if row["facet_id"] == "ring")
    assert detail["evidence_text"] == assignment["evidence_text"]
    page = render_feature_page(model)
    assert "可動性のつば" in page
