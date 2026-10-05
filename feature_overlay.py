"""Additive overlays layered on the immutable Phase 4C.9 feature package."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

from feature_ui import (TRUSTED_FEATURE_V2_MANIFEST_SHA256,
                        load_feature_v2_inputs, validate_feature_facets)
from mushroom_knowledge import load_mushroom_master, load_sources

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "audit" / "feature-overlays" / "index.json"
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_ARTIFACTS = {"promotion-delta.json", "decision-manifest.json", "source-snapshots.jsonl"}


class FeatureOverlayError(ValueError):
    """An incremental package cannot safely extend the immutable baseline."""


def _json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FeatureOverlayError(f"invalid JSON {path}: {error}") from error


def _inside(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
    except (OSError, ValueError) as error:
        raise FeatureOverlayError("path escapes its allowed directory") from error
    if path.is_symlink():
        raise FeatureOverlayError("symlink artifacts are forbidden")


def _inside_directory(path, parent):
    """Require a package directory and every resolved ancestor to stay in parent."""
    path, parent = Path(path), Path(parent).resolve()
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(parent)
    except (OSError, ValueError) as error:
        raise FeatureOverlayError("package directory escapes knowledge-batches root") from error
    if not resolved.is_dir():
        raise FeatureOverlayError("package path must be a directory")


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _unique(rows, key, label):
    if not isinstance(rows, list):
        raise FeatureOverlayError(f"{label} must be a list")
    result = {}
    for row in rows:
        value = row.get(key) if isinstance(row, dict) else None
        if not isinstance(value, str) or not value:
            raise FeatureOverlayError(f"{label} requires {key}")
        if value in result:
            raise FeatureOverlayError(f"duplicate {key}: {value}")
        result[value] = row
    return result


def load_overlay_registry(path=REGISTRY_PATH, root=ROOT):
    """Validate the ordered repository registry and its manifest hash chain."""
    root, path = Path(root).resolve(), Path(path)
    _inside(path, root)
    raw = _json(path)
    if set(raw) != {"schema_version", "overlays"} or raw["schema_version"] != 1:
        raise FeatureOverlayError("overlay registry must use schema version 1")
    rows = raw["overlays"]
    by_id = _unique(rows, "overlay_id", "overlays")
    ids = list(by_id)
    if ids != sorted(ids):
        raise FeatureOverlayError("overlays must be sorted by overlay_id")
    paths = set()
    knowledge_root = root / "audit" / "knowledge-batches"
    for overlay_id, row in by_id.items():
        if not ID.fullmatch(overlay_id):
            raise FeatureOverlayError("unsafe overlay_id")
        expected = f"audit/knowledge-batches/{overlay_id}/promotion-manifest.json"
        if row.get("manifest_path") != expected or expected in paths:
            raise FeatureOverlayError("manifest_path must be unique and bound to overlay_id")
        paths.add(expected)
        digest = row.get("manifest_sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise FeatureOverlayError("invalid manifest SHA-256")
        _inside_directory(knowledge_root, root)
        manifest = root / expected
        _inside_directory(manifest.parent, knowledge_root)
        _inside(manifest, root / "audit" / "knowledge-batches" / overlay_id)
        try:
            data = manifest.read_bytes()
        except OSError as error:
            raise FeatureOverlayError(f"missing manifest: {expected}") from error
        if _hash(data) != digest:
            raise FeatureOverlayError("manifest hash mismatch")
    return raw


def _manifest(registry_row, root, now):
    overlay_id = registry_row["overlay_id"]
    package = root / "audit" / "knowledge-batches" / overlay_id
    _inside_directory(package, root / "audit" / "knowledge-batches")
    path = root / registry_row["manifest_path"]
    manifest = _json(path)
    required = {"schema_version", "overlay_id", "created_at", "baseline_contract",
                "baseline_manifest_sha256", "additive_only", "artifacts"}
    if set(manifest) != required or manifest.get("schema_version") != 1:
        raise FeatureOverlayError("invalid promotion manifest schema")
    if (manifest["overlay_id"] != overlay_id or manifest["additive_only"] is not True
            or manifest["baseline_contract"] != "phase4c9-v2-immutable"):
        raise FeatureOverlayError("manifest identity/additive_only mismatch")
    if manifest["baseline_manifest_sha256"] != TRUSTED_FEATURE_V2_MANIFEST_SHA256:
        raise FeatureOverlayError("baseline manifest pin mismatch")
    try:
        created = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise FeatureOverlayError("created_at must be ISO-8601") from error
    if created.tzinfo is None or created > now:
        raise FeatureOverlayError("created_at requires timezone and cannot be future")
    artifacts = _unique(manifest["artifacts"], "path", "artifacts")
    if set(artifacts) != REQUIRED_ARTIFACTS:
        raise FeatureOverlayError("required artifact set mismatch")
    loaded = {}
    for name, row in artifacts.items():
        if name != Path(name).name or not SHA256.fullmatch(str(row.get("sha256", ""))):
            raise FeatureOverlayError("unsafe artifact path or SHA-256")
        path = package / name
        _inside(path, package)
        try:
            data = path.read_bytes()
        except OSError as error:
            raise FeatureOverlayError(f"missing artifact: {name}") from error
        if _hash(data) != row["sha256"]:
            raise FeatureOverlayError(f"artifact hash mismatch: {name}")
        loaded[name] = data
    return manifest, loaded


def _parse_json(data, name):
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise FeatureOverlayError(f"malformed {name}") from error


def _snapshots(data):
    try:
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as error:
        raise FeatureOverlayError("malformed source snapshot JSONL") from error
    return _unique(rows, "source_id", "snapshots")


def _validate_evidence(record, candidate, source, snapshot):
    context = f"candidate {candidate['candidate_id']}"
    if record.get("mushroom_id") != candidate["mushroom_id"] or record.get("facet_id") != candidate["assignment"].get("facet_id"):
        raise FeatureOverlayError(f"{context}: evidence target mismatch")
    if record.get("decision_id") != candidate["assignment"].get("review", {}).get("decision_id"):
        raise FeatureOverlayError(f"{context}: decision binding mismatch")
    if record.get("source_id") != source.get("source_id") or record.get("source_url") != source.get("url"):
        raise FeatureOverlayError(f"{context}: source URL binding mismatch")
    assignment = candidate["assignment"]
    if (record.get("evidence_kind") != assignment.get("evidence_kind")
            or record.get("evidence_text") != assignment.get("evidence_text")
            or record.get("qualifiers") != assignment.get("qualifiers")):
        raise FeatureOverlayError(f"{context}: evidence/assignment mismatch")
    text = snapshot.get("full_extracted_text")
    if not isinstance(text, str) or snapshot.get("encoding") != "UTF-8":
        raise FeatureOverlayError(f"{context}: snapshot text/encoding invalid")
    text_hash = _hash(text.encode())
    if not isinstance(snapshot.get("snapshot_identity"), str) or not snapshot["snapshot_identity"]:
        raise FeatureOverlayError(f"{context}: snapshot identity invalid")
    if not SHA256.fullmatch(str(snapshot.get("original_response_sha256", ""))):
        raise FeatureOverlayError(f"{context}: original response SHA-256 invalid")
    for field in ("extracted_text_sha256", "text_snapshot_sha256"):
        if snapshot.get(field) != text_hash or record.get(field) != text_hash:
            raise FeatureOverlayError(f"{context}: snapshot hash mismatch")
    if any(record.get(f) != snapshot.get(f) for f in ("snapshot_identity", "original_response_sha256")):
        raise FeatureOverlayError(f"{context}: snapshot identity mismatch")
    if (snapshot.get("unicode_codepoint_length") != len(text)
            or snapshot.get("utf8_byte_length") != len(text.encode())
            or snapshot.get("lf_line_count") != 1 + text.count("\n")):
        raise FeatureOverlayError(f"{context}: snapshot length mismatch")
    start, end, quote = record.get("char_start"), record.get("char_end"), record.get("quote")
    if (not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)
            or start < 0 or end < start or end > len(text)
            or not isinstance(quote, str) or text[start:end] != quote):
        raise FeatureOverlayError(f"{context}: quote offset mismatch")
    if _hash(quote.encode()) != record.get("quote_sha256"):
        raise FeatureOverlayError(f"{context}: quote hash mismatch")
    exact = record.get("evidence_text_exact_substring_of_this_quote")
    if not isinstance(exact, bool) or exact != (record["evidence_text"] in quote):
        raise FeatureOverlayError(f"{context}: exact-substring flag mismatch")
    line_start = 1 + text[:start].count("\n")
    line_end = line_start + quote.count("\n")
    if (record.get("snapshot_line_start"), record.get("snapshot_line_end")) != (line_start, line_end):
        raise FeatureOverlayError(f"{context}: line range mismatch")


def _validate_assignment(candidate, facet_ids):
    assignment = candidate.get("assignment")
    if not isinstance(assignment, dict):
        raise FeatureOverlayError("assignment must be an object")
    facet = assignment.get("facet_id")
    if not isinstance(facet, str) or not facet or facet not in facet_ids:
        raise FeatureOverlayError("unknown facet")
    if not isinstance(assignment.get("evidence_text"), str) or not assignment["evidence_text"]:
        raise FeatureOverlayError("assignment requires non-empty evidence_text")
    for field in ("source_ids", "evidence_refs", "qualifiers"):
        values = assignment.get(field)
        if (not isinstance(values, list) or (field != "qualifiers" and not values)
                or any(not isinstance(value, str) or not value for value in values)
                or len(values) != len(set(values))):
            raise FeatureOverlayError(f"invalid {field}")
    if assignment.get("evidence_kind") not in {"source_quote", "source_supported_paraphrase"}:
        raise FeatureOverlayError("invalid evidence_kind")
    review = assignment.get("review")
    if not isinstance(review, dict):
        raise FeatureOverlayError("assignment review is required")
    if not isinstance(review.get("decision_id"), str) or not review["decision_id"]:
        raise FeatureOverlayError("review decision_id is required")
    if review.get("human_approval", object()) is not None:
        raise FeatureOverlayError("review human_approval must be null")
    return assignment


def _validate_knowledge_objects(master, sources):
    """Reuse the production knowledge validators without touching repository files."""
    with tempfile.TemporaryDirectory(prefix="feature-overlay-") as directory:
        directory = Path(directory)
        source_path, master_path = directory / "sources.json", directory / "master.json"
        source_path.write_text(json.dumps(sources, ensure_ascii=False), encoding="utf-8")
        master_path.write_text(json.dumps(master, ensure_ascii=False), encoding="utf-8")
        load_sources(source_path)
        load_mushroom_master(master_path, source_path)


def reconstruct_feature_production_state(*, registry_path=REGISTRY_PATH, root=ROOT, now=None):
    """Validate baseline + overlays and return the deterministic expected production state."""
    root = Path(root).resolve()
    baseline = load_feature_v2_inputs()
    feature = json.loads((root / "audit/phase4c9/v2/feature-facets-runtime-candidate-2026-10-03.json").read_text())
    master, sources = baseline["mushroom_master"], baseline["sources"]
    validate_feature_facets(feature, master, sources=sources,
                            evidence_ledger=baseline["evidence_ledger"],
                            source_snapshots=baseline["source_snapshots"],
                            approval_manifest=baseline["approval_manifest"], mode="production")
    expected_master, expected_sources, expected_feature = deepcopy(master), deepcopy(sources), deepcopy(feature)
    registry = load_overlay_registry(registry_path, root)
    master_ids = {r["mushroom_id"] for r in expected_master["entries"]}
    names = {r["canonical_name_ja"] for r in expected_master["entries"]}
    aliases = {a for r in expected_master["entries"] for a in r.get("aliases_ja", [])}
    source_map = {r["source_id"]: r for r in expected_sources["sources"]}
    facet_ids = {r["facet_id"] for r in expected_feature["facets"]}
    entries = {r["mushroom_id"]: r for r in expected_feature["entries"]}
    assignment_keys = {(mid, a["facet_id"]) for mid, e in entries.items() for a in e["assignments"]}
    ledger = baseline["evidence_ledger"]
    evidence_ids = {r["evidence_id"] for r in ledger["evidence_records"]}
    evidence_ids |= {r["evidence_id"] for h in ledger["held_decisions"] for r in h["evidence_records"]}
    evidence_ids |= {r["evidence_id"] for r in ledger["retired_citations"]}
    baseline_decision_ids = {r["decision_id"] for r in ledger["approved_assignments"]}
    baseline_decision_ids |= {r["decision_id"] for r in ledger["held_decisions"]}
    snapshot_map = {row["source_id"]: row for row in
                    (json.loads(line) for line in baseline["source_snapshots"].splitlines() if line)}
    candidate_ids, overlay_decision_ids = set(), set()
    now = now or datetime.now(timezone.utc)
    for registry_row in registry["overlays"]:
        manifest, raw = _manifest(registry_row, root, now)
        delta = _parse_json(raw["promotion-delta.json"], "promotion delta")
        decisions = _parse_json(raw["decision-manifest.json"], "decision manifest")
        snapshots = _snapshots(raw["source-snapshots.jsonl"])
        available_snapshot_ids_before_overlay = set(snapshot_map)
        if set(delta) != {"schema_version", "mushroom_additions", "source_additions", "assignment_additions"} or delta["schema_version"] != 1:
            raise FeatureOverlayError("invalid promotion delta schema")
        if (set(decisions) != {"schema_version", "overlay_id", "reviewed_at", "decisions"}
                or decisions.get("schema_version") != 1
                or decisions.get("overlay_id") != manifest["overlay_id"]):
            raise FeatureOverlayError("invalid decision manifest")
        try:
            reviewed = datetime.fromisoformat(decisions["reviewed_at"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, ValueError) as error:
            raise FeatureOverlayError("reviewed_at must be timezone-aware ISO-8601") from error
        if reviewed.tzinfo is None or reviewed > now:
            raise FeatureOverlayError("reviewed_at requires timezone and cannot be future")
        decision_map = _unique(decisions.get("decisions"), "candidate_id", "decisions")
        if set(decision_map) & candidate_ids:
            raise FeatureOverlayError("duplicate candidate_id across overlays")
        candidate_ids |= set(decision_map)
        decision_ids = set()
        for decision in decision_map.values():
            required = ("candidate_id", "mushroom_id", "facet_id", "decision_id",
                        "human_decision", "review_result")
            if any(not isinstance(decision.get(field), str) or not decision[field] for field in required):
                raise FeatureOverlayError("decision fields must be non-empty strings")
            if "note" in decision and not isinstance(decision["note"], str):
                raise FeatureOverlayError("decision note must be a string")
            if decision.get("human_decision") not in {"approved", "held", "pending"}:
                raise FeatureOverlayError("invalid human decision")
            if decision.get("decision_id") in decision_ids:
                raise FeatureOverlayError("duplicate decision_id")
            decision_ids.add(decision.get("decision_id"))
        if decision_ids & (baseline_decision_ids | overlay_decision_ids):
            raise FeatureOverlayError("duplicate decision_id across overlays")
        overlay_decision_ids |= decision_ids
        additions = _unique(delta["assignment_additions"], "candidate_id", "assignment additions")
        if set(additions) - set(decision_map):
            raise FeatureOverlayError("assignment lacks human decision")
        for source in delta["source_additions"]:
            sid = source.get("source_id")
            if sid in source_map:
                raise FeatureOverlayError("existing source overwrite")
            source_map[sid] = source; expected_sources["sources"].append(source)
        for mushroom in delta["mushroom_additions"]:
            mid, name = mushroom.get("mushroom_id"), mushroom.get("canonical_name_ja")
            new_aliases = set(mushroom.get("aliases_ja", []))
            if mid in master_ids or name in names or name in aliases or new_aliases & (names | aliases):
                raise FeatureOverlayError("existing mushroom/name overwrite")
            master_ids.add(mid); names.add(name); aliases |= new_aliases; expected_master["entries"].append(mushroom)
        for sid, snapshot in snapshots.items():
            if sid in snapshot_map:
                raise FeatureOverlayError("baseline or prior overlay snapshot replacement")
            snapshot_map[sid] = snapshot
        used_new_sources = set()
        for candidate_id, candidate in additions.items():
            decision = decision_map[candidate_id]
            assignment = _validate_assignment(candidate, facet_ids)
            mid, facet = candidate.get("mushroom_id"), assignment["facet_id"]
            if decision.get("human_decision") != "approved" or decision.get("review_result") != "supports_facet":
                raise FeatureOverlayError("held/pending candidate cannot be promoted")
            review = assignment.get("review", {})
            if (decision.get("mushroom_id") != mid or decision.get("facet_id") != facet
                    or decision.get("decision_id") != review.get("decision_id")):
                raise FeatureOverlayError("decision binding mismatch")
            if (mid, facet) == ("tamagotakemodoki", "ring"):
                raise FeatureOverlayError("IA-029 ring is prohibited")
            if mid not in master_ids or (mid, facet) in assignment_keys:
                raise FeatureOverlayError("unknown mushroom or duplicate assignment key")
            records = candidate.get("evidence_records")
            refs = assignment.get("evidence_refs")
            if not isinstance(records, list) or not records or not isinstance(refs, list):
                raise FeatureOverlayError("assignment requires evidence")
            record_map = _unique(records, "evidence_id", "evidence records")
            if set(record_map) != set(refs) or set(record_map) & evidence_ids:
                raise FeatureOverlayError("evidence reference mismatch/collision")
            for record in records:
                sid = record.get("source_id"); source = source_map.get(sid)
                snapshot = snapshot_map.get(sid)
                if source is None:
                    raise FeatureOverlayError("unknown source")
                if snapshot is None or snapshot.get("source_url") != source.get("url"):
                    raise FeatureOverlayError("missing snapshot or source URL mismatch")
                _validate_evidence(record, candidate, source, snapshot)
                evidence_ids.add(record["evidence_id"]); used_new_sources.add(sid)
            if set(assignment["source_ids"]) != {record["source_id"] for record in records}:
                raise FeatureOverlayError("source/evidence set mismatch")
            entry = entries.get(mid)
            if entry is None:
                entry = {"mushroom_id": mid, "assignments": []}
                entries[mid] = entry; expected_feature["entries"].append(entry)
            entry["assignments"].append(assignment); assignment_keys.add((mid, facet))
        new_source_ids = {r["source_id"] for r in delta["source_additions"]}
        if new_source_ids - used_new_sources:
            raise FeatureOverlayError("orphan source addition")
        evidence_source_ids = {record["source_id"] for candidate in additions.values()
                               for record in candidate.get("evidence_records", [])}
        if set(snapshots) != evidence_source_ids - available_snapshot_ids_before_overlay:
            raise FeatureOverlayError("unused or missing overlay snapshot")
        eligible_new = {r["mushroom_id"] for r in delta["mushroom_additions"]
                        if str((r.get("features") or {}).get("summary") or "").strip()}
        if eligible_new - set(entries):
            raise FeatureOverlayError("new eligible mushroom requires approved assignment")
    coverage = expected_feature["coverage"]
    eligible = [r["mushroom_id"] for r in expected_master["entries"]
                if str((r.get("features") or {}).get("summary") or "").strip()]
    included = [r["mushroom_id"] for r in expected_feature["entries"]]
    coverage["eligible_mushroom_ids"] = eligible
    coverage["included_mushroom_ids"] = included
    coverage["excluded_mushrooms"] = [r for r in coverage["excluded_mushrooms"] if r["mushroom_id"] not in set(included)]
    coverage["entry_count"] = len(included)
    coverage["assignment_count"] = sum(len(r["assignments"]) for r in expected_feature["entries"])
    _validate_knowledge_objects(expected_master, expected_sources)
    return {"mushroom_master": expected_master, "sources": expected_sources,
            "feature_facets": expected_feature, "overlay_count": len(registry["overlays"])}


def validate_feature_production_state(*, registry_path=REGISTRY_PATH, root=ROOT):
    """Require actual production JSON to exactly equal reconstructed expected state."""
    expected = reconstruct_feature_production_state(registry_path=registry_path, root=root)
    actual_master = _json(Path(root) / "data/mushroom-master.json")
    actual_sources = _json(Path(root) / "data/sources.json")
    actual_feature = _json(Path(root) / "data/feature-facets.json")
    # Reuse the established source/master schema validators on the reconstructed files.
    load_sources(Path(root) / "data/sources.json")
    load_mushroom_master(Path(root) / "data/mushroom-master.json", Path(root) / "data/sources.json")
    for key, actual in (("mushroom_master", actual_master), ("sources", actual_sources),
                        ("feature_facets", actual_feature)):
        if actual != expected[key]:
            raise FeatureOverlayError(f"actual production {key} differs from reconstructed expected state")
    return expected
