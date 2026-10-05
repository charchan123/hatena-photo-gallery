from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

import feature_overlay
from feature_overlay import (FeatureOverlayError, load_overlay_registry,
                             reconstruct_feature_production_state,
                             validate_feature_production_state)
from feature_ui import (_write_feature_page, generate_feature_page,
                        load_feature_v2_inputs, validate_feature_facets)


ROOT = Path(__file__).parents[1]


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def synthetic_package(tmp_path, *, decision="approved", facet="gills", mushroom="kiirosuppontake"):
    root = tmp_path
    (root / "audit/feature-overlays").mkdir(parents=True)
    package = root / "audit/knowledge-batches/overlay-001"; package.mkdir(parents=True)
    text = "synthetic evidence quote"
    digest = hashlib.sha256(text.encode()).hexdigest()
    snapshot = {"source_id":"test-source-overlay", "source_url":"https://example.test/source",
        "full_extracted_text":text, "encoding":"UTF-8", "snapshot_identity":"synthetic-1",
        "extracted_text_sha256":digest, "text_snapshot_sha256":digest,
        "original_response_sha256":"a"*64, "unicode_codepoint_length":len(text),
        "utf8_byte_length":len(text.encode()), "lf_line_count":1}
    evidence = {"evidence_id":"overlay-evidence-1", "decision_id":"overlay-decision-1",
        "mushroom_id":mushroom, "facet_id":facet, "source_id":"test-source-overlay",
        "source_url":"https://example.test/source", "evidence_kind":"source_quote",
        "evidence_text":"synthetic evidence", "qualifiers":[], "quote":text,
        "quote_sha256":digest, "char_start":0, "char_end":len(text),
        "snapshot_identity":"synthetic-1", "extracted_text_sha256":digest,
        "text_snapshot_sha256":digest, "original_response_sha256":"a"*64,
        "snapshot_line_start":1, "snapshot_line_end":1,
        "evidence_text_exact_substring_of_this_quote":True}
    assignment = {"facet_id":facet, "evidence_text":"synthetic evidence",
        "source_ids":["test-source-overlay"], "evidence_refs":["overlay-evidence-1"],
        "evidence_kind":"source_quote", "qualifiers":[],
        "review":{"decision_id":"overlay-decision-1", "status":"source_checked_candidate",
                  "reviewer_kind":"human_incremental_review", "human_approval":None}}
    source = {"source_id":"test-source-overlay", "organization":"Synthetic Test",
        "title":"Synthetic fixture", "source_type":"test", "url":"https://example.test/source",
        "record_id":None, "accessed_at":"2026-10-05", "notes":"test only"}
    delta = {"schema_version":1, "mushroom_additions":[], "source_additions":[source],
             "assignment_additions":[{"candidate_id":"candidate-1", "mushroom_id":mushroom,
                                      "assignment":assignment, "evidence_records":[evidence]}]}
    decisions = {"schema_version":1, "overlay_id":"overlay-001", "reviewed_at":"2026-10-05T00:00:00+00:00",
        "decisions":[{"candidate_id":"candidate-1", "mushroom_id":mushroom, "facet_id":facet,
                      "decision_id":"overlay-decision-1", "human_decision":decision,
                      "review_result":"supports_facet"}]}
    artifacts = {"promotion-delta.json":json.dumps(delta, ensure_ascii=False, indent=2).encode()+b"\n",
                 "decision-manifest.json":json.dumps(decisions, ensure_ascii=False, indent=2).encode()+b"\n",
                 "source-snapshots.jsonl":(json.dumps(snapshot, ensure_ascii=False)+"\n").encode()}
    for name,data in artifacts.items(): (package/name).write_bytes(data)
    manifest = {"schema_version":1,"overlay_id":"overlay-001","created_at":"2026-10-05T00:00:00+00:00",
        "baseline_contract":"phase4c9-v2-immutable",
        "baseline_manifest_sha256":feature_overlay.TRUSTED_FEATURE_V2_MANIFEST_SHA256,
        "additive_only":True,"artifacts":[{"path":n,"sha256":hashlib.sha256(d).hexdigest()} for n,d in artifacts.items()]}
    dump(package/"promotion-manifest.json",manifest)
    registry={"schema_version":1,"overlays":[{"overlay_id":"overlay-001",
        "manifest_path":"audit/knowledge-batches/overlay-001/promotion-manifest.json",
        "manifest_sha256":hashlib.sha256((package/"promotion-manifest.json").read_bytes()).hexdigest()}]}
    dump(root/"audit/feature-overlays/index.json",registry)
    return root, package, registry


def copy_baseline(tmp_path):
    for rel in ("audit/phase4c9/v2", "data"):
        target=tmp_path/rel; target.parent.mkdir(parents=True,exist_ok=True)
        import shutil; shutil.copytree(ROOT/rel,target)


def rehash(package, root):
    manifest=json.loads((package/"promotion-manifest.json").read_text())
    for row in manifest["artifacts"]: row["sha256"]=hashlib.sha256((package/row["path"]).read_bytes()).hexdigest()
    dump(package/"promotion-manifest.json",manifest)
    registry=json.loads((root/"audit/feature-overlays/index.json").read_text())
    registry["overlays"][0]["manifest_sha256"]=hashlib.sha256((package/"promotion-manifest.json").read_bytes()).hexdigest()
    dump(root/"audit/feature-overlays/index.json",registry)


def add_second_overlay(root, first_package, *, repeat_snapshot=False, missing_new_snapshot=False):
    package = root/"audit/knowledge-batches/overlay-002"; package.mkdir()
    first_delta = json.loads((first_package/"promotion-delta.json").read_text())
    candidate = deepcopy(first_delta["assignment_additions"][0])
    candidate["candidate_id"] = "candidate-2"
    candidate["assignment"]["facet_id"] = "cap_depressed"
    candidate["assignment"]["evidence_refs"] = ["overlay-evidence-2"]
    candidate["assignment"]["review"]["decision_id"] = "overlay-decision-2"
    evidence = candidate["evidence_records"][0]
    evidence.update({"evidence_id":"overlay-evidence-2", "decision_id":"overlay-decision-2",
                     "facet_id":"cap_depressed"})
    source_additions = []
    snapshots = b""
    if repeat_snapshot:
        snapshots = (first_package/"source-snapshots.jsonl").read_bytes()
    if missing_new_snapshot:
        source = deepcopy(first_delta["source_additions"][0])
        source.update({"source_id":"test-source-overlay-2", "url":"https://example.test/source-2"})
        source_additions = [source]
        candidate["assignment"]["source_ids"] = [source["source_id"]]
        evidence.update({"source_id":source["source_id"], "source_url":source["url"]})
    delta = {"schema_version":1, "mushroom_additions":[], "source_additions":source_additions,
             "assignment_additions":[candidate]}
    decisions = {"schema_version":1, "overlay_id":"overlay-002",
        "reviewed_at":"2026-10-05T00:00:00+00:00", "decisions":[{
            "candidate_id":"candidate-2", "mushroom_id":candidate["mushroom_id"],
            "facet_id":"cap_depressed", "decision_id":"overlay-decision-2",
            "human_decision":"approved", "review_result":"supports_facet"}]}
    artifacts = {"promotion-delta.json":json.dumps(delta, ensure_ascii=False, indent=2).encode()+b"\n",
                 "decision-manifest.json":json.dumps(decisions, ensure_ascii=False, indent=2).encode()+b"\n",
                 "source-snapshots.jsonl":snapshots}
    for name, data in artifacts.items(): (package/name).write_bytes(data)
    manifest = {"schema_version":1, "overlay_id":"overlay-002",
        "created_at":"2026-10-05T00:00:00+00:00", "baseline_contract":"phase4c9-v2-immutable",
        "baseline_manifest_sha256":feature_overlay.TRUSTED_FEATURE_V2_MANIFEST_SHA256,
        "additive_only":True, "artifacts":[{"path":name,"sha256":hashlib.sha256(data).hexdigest()}
                                             for name,data in artifacts.items()]}
    dump(package/"promotion-manifest.json", manifest)
    registry=json.loads((root/"audit/feature-overlays/index.json").read_text())
    registry["overlays"].append({"overlay_id":"overlay-002",
        "manifest_path":"audit/knowledge-batches/overlay-002/promotion-manifest.json",
        "manifest_sha256":hashlib.sha256((package/"promotion-manifest.json").read_bytes()).hexdigest()})
    dump(root/"audit/feature-overlays/index.json", registry)
    return package


def mutate_candidate(tmp_path, mutator):
    copy_baseline(tmp_path); root, package, _ = synthetic_package(tmp_path)
    delta = json.loads((package/"promotion-delta.json").read_text())
    mutator(delta["assignment_additions"][0])
    dump(package/"promotion-delta.json", delta); rehash(package, root)
    return root


def reconstruct(root):
    return reconstruct_feature_production_state(
        registry_path=root/"audit/feature-overlays/index.json", root=root,
        now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_empty_registry_is_exact_current_production():
    state=validate_feature_production_state()
    assert state["overlay_count"]==0
    assert state["feature_facets"]==json.loads((ROOT/"data/feature-facets.json").read_text())


def test_immutable_baseline_boundaries_still_enforced():
    inputs=load_feature_v2_inputs(); feature=json.loads((ROOT/"data/feature-facets.json").read_text())
    validate_feature_facets(feature, inputs["mushroom_master"], sources=inputs["sources"],
        evidence_ledger=inputs["evidence_ledger"], source_snapshots=inputs["source_snapshots"],
        approval_manifest=inputs["approval_manifest"])
    bad=deepcopy(inputs["evidence_ledger"]); bad["approved_assignments"].pop()
    with pytest.raises(ValueError,match="boundary"): validate_feature_facets(feature,inputs["mushroom_master"],sources=inputs["sources"],evidence_ledger=bad,source_snapshots=inputs["source_snapshots"],approval_manifest=inputs["approval_manifest"])


def test_valid_synthetic_overlay_reconstructs_additively(tmp_path):
    copy_baseline(tmp_path); root,_,_=synthetic_package(tmp_path)
    state=reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,
                                               now=datetime(2026,10,6,tzinfo=timezone.utc))
    assert len(state["sources"]["sources"])==420
    row=next(r for r in state["feature_facets"]["entries"] if r["mushroom_id"]=="kiirosuppontake")
    assert [a["facet_id"] for a in row["assignments"]]==["gills"]
    assert state["feature_facets"]["coverage"]["assignment_count"]==374
    assert len(state["feature_facets"]["coverage"]["held_assignments"])==10


@pytest.mark.parametrize("decision",["held","pending"])
def test_nonapproved_candidate_is_never_promoted(tmp_path,decision):
    copy_baseline(tmp_path); root,_,_=synthetic_package(tmp_path,decision=decision)
    with pytest.raises(FeatureOverlayError,match="cannot be promoted"):
        reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


@pytest.mark.parametrize("facet,message",[("unknown-facet","unknown facet"),("ring","IA-029")])
def test_unknown_facet_and_ia029_ring_are_blocked(tmp_path,facet,message):
    copy_baseline(tmp_path); mushroom="tamagotakemodoki" if facet=="ring" else "kiirosuppontake"
    root,_,_=synthetic_package(tmp_path,facet=facet,mushroom=mushroom)
    with pytest.raises(FeatureOverlayError,match=message): reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_manifest_hash_mismatch(tmp_path):
    root,_,registry=synthetic_package(tmp_path); registry["overlays"][0]["manifest_sha256"]="0"*64; dump(root/"audit/feature-overlays/index.json",registry)
    with pytest.raises(FeatureOverlayError,match="manifest hash mismatch"): load_overlay_registry(root/"audit/feature-overlays/index.json",root)


@pytest.mark.parametrize("bad",["../x/promotion-manifest.json","/tmp/promotion-manifest.json","audit/knowledge-batches/other/promotion-manifest.json"])
def test_registry_traversal_absolute_and_identity_refused(tmp_path,bad):
    root,_,registry=synthetic_package(tmp_path); registry["overlays"][0]["manifest_path"]=bad; dump(root/"audit/feature-overlays/index.json",registry)
    with pytest.raises(FeatureOverlayError): load_overlay_registry(root/"audit/feature-overlays/index.json",root)


def test_symlink_manifest_escape_refused(tmp_path):
    root,package,registry=synthetic_package(tmp_path); outside=tmp_path/"outside"; outside.write_text("{}")
    (package/"promotion-manifest.json").unlink(); (package/"promotion-manifest.json").symlink_to(outside)
    with pytest.raises(FeatureOverlayError): load_overlay_registry(root/"audit/feature-overlays/index.json",root)


def test_package_directory_symlink_escape_refused(tmp_path):
    root = tmp_path/"repo"; outside = tmp_path/"outside"
    _, package, registry = synthetic_package(outside)
    (root/"audit/knowledge-batches").mkdir(parents=True)
    (root/"audit/feature-overlays").mkdir(parents=True)
    (root/"audit/knowledge-batches/overlay-001").symlink_to(package, target_is_directory=True)
    dump(root/"audit/feature-overlays/index.json", registry)
    with pytest.raises(FeatureOverlayError, match="escapes"):
        load_overlay_registry(root/"audit/feature-overlays/index.json", root)


def test_knowledge_batches_root_symlink_escape_refused(tmp_path):
    root, outside = tmp_path/"repo", tmp_path/"outside"
    _, _, registry = synthetic_package(outside)
    (root/"audit/feature-overlays").mkdir(parents=True)
    (root/"audit/knowledge-batches").symlink_to(outside/"audit/knowledge-batches",
                                                  target_is_directory=True)
    dump(root/"audit/feature-overlays/index.json", registry)
    with pytest.raises(FeatureOverlayError, match="escapes"):
        load_overlay_registry(root/"audit/feature-overlays/index.json", root)


def test_prior_overlay_source_and_snapshot_can_be_reused(tmp_path):
    copy_baseline(tmp_path); root, first, _ = synthetic_package(tmp_path)
    add_second_overlay(root, first)
    state = reconstruct(root)
    row = next(row for row in state["feature_facets"]["entries"]
               if row["mushroom_id"] == "kiirosuppontake")
    assert [item["facet_id"] for item in row["assignments"]] == ["gills", "cap_depressed"]


def test_prior_overlay_snapshot_cannot_be_redefined(tmp_path):
    copy_baseline(tmp_path); root, first, _ = synthetic_package(tmp_path)
    add_second_overlay(root, first, repeat_snapshot=True)
    with pytest.raises(FeatureOverlayError, match="snapshot replacement"):
        reconstruct(root)


def test_newly_used_source_requires_current_overlay_snapshot(tmp_path):
    copy_baseline(tmp_path); root, first, _ = synthetic_package(tmp_path)
    add_second_overlay(root, first, missing_new_snapshot=True)
    with pytest.raises(FeatureOverlayError, match="missing snapshot"):
        reconstruct(root)


@pytest.mark.parametrize("field,value,message",[("quote_sha256","0"*64,"quote hash"),("char_end",1,"quote offset"),("source_url","https://wrong.test","source URL")])
def test_evidence_provenance_failures(tmp_path,field,value,message):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path)
    delta=json.loads((package/"promotion-delta.json").read_text()); delta["assignment_additions"][0]["evidence_records"][0][field]=value; dump(package/"promotion-delta.json",delta); rehash(package,root)
    with pytest.raises(FeatureOverlayError,match=message): reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_existing_assignment_and_source_overwrite_refused(tmp_path):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path,mushroom="kaentake",facet="rod_cylindrical")
    delta=json.loads((package/"promotion-delta.json").read_text()); delta["source_additions"][0]["source_id"]="mhlw-kaentake"; dump(package/"promotion-delta.json",delta); rehash(package,root)
    with pytest.raises(FeatureOverlayError,match="source overwrite"): reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_actual_production_unexplained_change_fails(tmp_path):
    copy_baseline(tmp_path); (tmp_path/"audit/feature-overlays").mkdir(parents=True); dump(tmp_path/"audit/feature-overlays/index.json",{"schema_version":1,"overlays":[]})
    data=json.loads((tmp_path/"data/feature-facets.json").read_text()); data["entries"][0]["assignments"].pop(); dump(tmp_path/"data/feature-facets.json",data)
    with pytest.raises(FeatureOverlayError,match="differs"): validate_feature_production_state(registry_path=tmp_path/"audit/feature-overlays/index.json",root=tmp_path)


def test_valid_overlay_expected_runtime_can_become_exact_production(tmp_path):
    copy_baseline(tmp_path); root,_,_=synthetic_package(tmp_path)
    expected=reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))
    dump(root/"data/mushroom-master.json",expected["mushroom_master"])
    dump(root/"data/sources.json",expected["sources"])
    dump(root/"data/feature-facets.json",expected["feature_facets"])
    assert validate_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root)["overlay_count"]==1


def test_main_v2_path_renders_only_after_overlay_production_validation(monkeypatch):
    import main
    baseline = json.loads((ROOT/"data/feature-facets.json").read_text())
    expanded = deepcopy(baseline)
    expanded["coverage"]["assignment_count"] = 374
    production = {"mushroom_master":load_feature_v2_inputs()["mushroom_master"],
                  "feature_facets":expanded}
    calls = []
    monkeypatch.setattr(main, "load_fresh_portal_data", lambda _: {"version":1, "subjects":[]})
    monkeypatch.setattr(main, "load_feature_facets", lambda _: expanded)
    monkeypatch.setattr(main, "load_feature_v2_inputs", load_feature_v2_inputs)
    monkeypatch.setattr(main, "validate_feature_production_state",
                        lambda: calls.append("production") or production)
    monkeypatch.setattr(main, "validate_feature_facets",
                        lambda *args, **kwargs: pytest.fail("legacy validator must not see overlay runtime"))
    monkeypatch.setattr(main, "_write_feature_page",
                        lambda portal, feature, *args: calls.append(("write", feature)))
    assert main.generate_feature_page_if_fresh({"build_ok":True}) is True
    assert calls == ["production", ("write", expanded)]


def test_empty_overlay_writer_matches_validated_generator(tmp_path):
    feature = json.loads((ROOT/"data/feature-facets.json").read_text())
    inputs = load_feature_v2_inputs()
    portal = {"version":1, "subjects":[]}
    validated_dir, production_dir = tmp_path/"validated", tmp_path/"production"
    validated_model = generate_feature_page(
        portal, feature, validated_dir, ROOT/"assets", lambda value:value,
        mushroom_master=inputs["mushroom_master"], sources=inputs["sources"],
        evidence_ledger=inputs["evidence_ledger"], source_snapshots=inputs["source_snapshots"],
        approval_manifest=inputs["approval_manifest"])
    production = validate_feature_production_state()
    production_model = _write_feature_page(
        portal, production["feature_facets"], production_dir, ROOT/"assets", lambda value:value)
    assert production_model == validated_model
    assert (production_dir/"features.html").read_bytes() == (validated_dir/"features.html").read_bytes()


@pytest.mark.parametrize("field,value", [
    ("evidence_text", ""), ("source_ids", []),
    ("source_ids", ["test-source-overlay", "test-source-overlay"]),
    ("evidence_refs", ["overlay-evidence-1", "overlay-evidence-1"]),
    ("evidence_kind", "guess"), ("qualifiers", "bad"),
    ("qualifiers", [""]), ("qualifiers", ["same", "same"]),
])
def test_assignment_schema_failures(tmp_path, field, value):
    root = mutate_candidate(tmp_path, lambda row: row["assignment"].__setitem__(field, value))
    with pytest.raises(FeatureOverlayError): reconstruct(root)


def test_assignment_review_and_source_set_failures(tmp_path):
    mutations = [
        lambda row: row["assignment"].pop("review"),
        lambda row: row["assignment"]["review"].__setitem__("decision_id", ""),
        lambda row: row["assignment"]["review"].__setitem__("human_approval", True),
        lambda row: row["assignment"].__setitem__("source_ids", ["different-source"]),
    ]
    for index, mutation in enumerate(mutations):
        case = tmp_path/str(index); case.mkdir()
        root = mutate_candidate(case, mutation)
        with pytest.raises(FeatureOverlayError): reconstruct(root)


def test_paraphrase_with_false_exact_flag_is_valid(tmp_path):
    def mutation(row):
        row["assignment"]["evidence_kind"] = "source_supported_paraphrase"
        row["assignment"]["evidence_text"] = "supported paraphrase"
        record = row["evidence_records"][0]
        record["evidence_kind"] = "source_supported_paraphrase"
        record["evidence_text"] = "supported paraphrase"
        record["evidence_text_exact_substring_of_this_quote"] = False
    root = mutate_candidate(tmp_path, mutation)
    assert reconstruct(root)["overlay_count"] == 1


@pytest.mark.parametrize("field,value", [
    ("evidence_text_exact_substring_of_this_quote", False),
    ("char_start", -1), ("char_start", True), ("char_end", 999),
    ("snapshot_line_start", 2), ("snapshot_line_end", 2),
    ("original_response_sha256", "ABC"), ("snapshot_identity", ""),
])
def test_strict_provenance_failures(tmp_path, field, value):
    root = mutate_candidate(tmp_path, lambda row: row["evidence_records"][0].__setitem__(field, value))
    with pytest.raises(FeatureOverlayError): reconstruct(root)


def test_decision_manifest_schema_and_collision_failures(tmp_path):
    for index, mutation in enumerate((
        lambda d: d.__setitem__("unknown", True),
        lambda d: d["decisions"][0].__setitem__("review_result", "not_supported"),
        lambda d: d["decisions"][0].__setitem__("decision_id", load_feature_v2_inputs()["evidence_ledger"]["approved_assignments"][0]["decision_id"]),
    )):
        case=tmp_path/str(index); copy_baseline(case); root,package,_=synthetic_package(case)
        decisions=json.loads((package/"decision-manifest.json").read_text()); mutation(decisions)
        if index == 2:
            delta=json.loads((package/"promotion-delta.json").read_text())
            delta["assignment_additions"][0]["assignment"]["review"]["decision_id"]=decisions["decisions"][0]["decision_id"]
            delta["assignment_additions"][0]["evidence_records"][0]["decision_id"]=decisions["decisions"][0]["decision_id"]
            dump(package/"promotion-delta.json",delta)
        dump(package/"decision-manifest.json",decisions); rehash(package,root)
        with pytest.raises(FeatureOverlayError): reconstruct(root)


@pytest.mark.parametrize("value", [None, ""])
def test_decision_id_is_required_and_nonempty(tmp_path, value):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path)
    decisions=json.loads((package/"decision-manifest.json").read_text())
    if value is None:
        decisions["decisions"][0].pop("decision_id")
    else:
        decisions["decisions"][0]["decision_id"] = value
    dump(package/"decision-manifest.json", decisions); rehash(package,root)
    with pytest.raises(FeatureOverlayError, match="non-empty strings"):
        reconstruct(root)


def test_held_baseline_decision_id_collision_is_blocked(tmp_path):
    held_id = load_feature_v2_inputs()["evidence_ledger"]["held_decisions"][0]["decision_id"]
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path)
    delta=json.loads((package/"promotion-delta.json").read_text())
    candidate=delta["assignment_additions"][0]
    candidate["assignment"]["review"]["decision_id"] = held_id
    candidate["evidence_records"][0]["decision_id"] = held_id
    dump(package/"promotion-delta.json", delta)
    decisions=json.loads((package/"decision-manifest.json").read_text())
    decisions["decisions"][0]["decision_id"] = held_id
    dump(package/"decision-manifest.json", decisions); rehash(package,root)
    with pytest.raises(FeatureOverlayError, match="duplicate decision_id"):
        reconstruct(root)


def test_unused_overlay_snapshot_is_blocked(tmp_path):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path)
    snapshot=json.loads((package/"source-snapshots.jsonl").read_text())
    snapshot["source_id"]="unused-source"
    with (package/"source-snapshots.jsonl").open("a") as stream: stream.write(json.dumps(snapshot)+"\n")
    rehash(package,root)
    with pytest.raises(FeatureOverlayError,match="unused"): reconstruct(root)


@pytest.mark.parametrize("artifact",["promotion-delta.json","decision-manifest.json"])
def test_malformed_json_is_blocked(tmp_path,artifact):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path); (package/artifact).write_text("{"); rehash(package,root)
    with pytest.raises(FeatureOverlayError,match="malformed"):
        reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_malformed_jsonl_is_blocked(tmp_path):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path); (package/"source-snapshots.jsonl").write_text("{"); rehash(package,root)
    with pytest.raises(FeatureOverlayError,match="malformed"):
        reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_artifact_hash_mismatch_is_blocked(tmp_path):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path); (package/"promotion-delta.json").write_text("{}")
    with pytest.raises(FeatureOverlayError,match="artifact hash mismatch"):
        reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_duplicate_candidate_and_evidence_ids_are_blocked(tmp_path):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path)
    delta=json.loads((package/"promotion-delta.json").read_text()); delta["assignment_additions"].append(deepcopy(delta["assignment_additions"][0])); dump(package/"promotion-delta.json",delta); rehash(package,root)
    with pytest.raises(FeatureOverlayError,match="duplicate candidate_id"):
        reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_missing_evidence_and_orphan_source_are_blocked(tmp_path):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path)
    delta=json.loads((package/"promotion-delta.json").read_text()); delta["assignment_additions"]=[]; dump(package/"promotion-delta.json",delta); rehash(package,root)
    with pytest.raises(FeatureOverlayError,match="orphan source"):
        reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_registry_duplicate_overlay_id_and_order_are_blocked(tmp_path):
    root,_,registry=synthetic_package(tmp_path); registry["overlays"].append(deepcopy(registry["overlays"][0])); dump(root/"audit/feature-overlays/index.json",registry)
    with pytest.raises(FeatureOverlayError,match="duplicate overlay_id"): load_overlay_registry(root/"audit/feature-overlays/index.json",root)


def test_future_manifest_time_is_blocked(tmp_path):
    copy_baseline(tmp_path); root,package,_=synthetic_package(tmp_path); manifest=json.loads((package/"promotion-manifest.json").read_text()); manifest["created_at"]="2099-01-01T00:00:00+00:00"; dump(package/"promotion-manifest.json",manifest)
    registry=json.loads((root/"audit/feature-overlays/index.json").read_text()); registry["overlays"][0]["manifest_sha256"]=hashlib.sha256((package/"promotion-manifest.json").read_bytes()).hexdigest(); dump(root/"audit/feature-overlays/index.json",registry)
    with pytest.raises(FeatureOverlayError,match="cannot be future"):
        reconstruct_feature_production_state(registry_path=root/"audit/feature-overlays/index.json",root=root,now=datetime(2026,10,6,tzinfo=timezone.utc))


def test_registry_is_empty_and_public_output_has_no_overlay_artifacts():
    assert json.loads((ROOT/"audit/feature-overlays/index.json").read_text())["overlays"]==[]
    assert not (ROOT/"output/audit").exists()


def test_baseline_counts_remain_exact():
    inputs = load_feature_v2_inputs()
    ledger = inputs["evidence_ledger"]
    assert len(ledger["approved_assignments"]) == 373
    assert len(ledger["evidence_records"]) == 377
    assert len(ledger["held_decisions"]) == 10
    assert len(inputs["source_snapshots"].splitlines()) == 130
