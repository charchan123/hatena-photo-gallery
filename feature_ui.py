"""Evidence-backed feature search data validation and page generation."""

import html
import hashlib
import json
import os
import shutil
from pathlib import Path


TRUSTED_FEATURE_V2_MANIFEST_SHA256 = "2d6f21f31d7e0e33a513c02a5188f563baa4a8e8bbe1f40866501c3780521d05"
_V2_DIR = Path(__file__).parent / "audit" / "phase4c9" / "v2"
_V2_FILES = {
    "candidate": ("feature-facets-runtime-candidate-2026-10-03.json", "6d4d987a535dca9c1d0d3668b65de245fbdc281f56c546af436c6fb853bdd84d"),
    "master": ("mushroom-master-final-candidate-2026-10-03.json", "2ce8cfc61726ef04bb6f4bba26c42511e2c0bf1d4017b9e87e0a359d61decca4"),
    "sources": ("sources-final-candidate-2026-10-03.json", "d5213f1cf0881af1c60ea949c0321ae0eb854daa3f300135dae9e9f9ad2fdb66"),
    "snapshots": ("phase4c9-feature-source-snapshots-2026-10-03.jsonl", "5583716324d8ba2600352241c47ff5b61f5f2cef0bea9180f34f4315e2ec048e"),
    "ledger": ("phase4c9-feature-evidence-ledger-approved-2026-10-03.json", "0253787fb1bc0cea03cc5aba5759e08c2b0fcfa9fd37e194986011573c926ee7"),
    "manifest": ("phase4c9-feature-approval-manifest-2026-10-03.json", TRUSTED_FEATURE_V2_MANIFEST_SHA256),
}


class FeatureFacetError(ValueError):
    """Raised when curated feature data breaks its evidence contract."""


def load_feature_facets(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def load_feature_v2_inputs():
    """Load the repository-owned, byte-pinned Phase 4C.9 production inputs."""
    snapshot_bytes, _ = _bytes_and_object("snapshots")
    return {
        "mushroom_master": _bytes_and_object("master")[1],
        "sources": _bytes_and_object("sources")[1],
        "evidence_ledger": _bytes_and_object("ledger")[1],
        "source_snapshots": snapshot_bytes.decode("utf-8"),
        "approval_manifest": _bytes_and_object("manifest")[1],
    }


def _rows(root, key):
    rows = root.get(key) if isinstance(root, dict) else None
    if not isinstance(rows, list):
        raise FeatureFacetError(f"{key} must be a list")
    return rows


def validate_feature_facets(feature_data, mushroom_master, *, sources=None,
                            evidence_ledger=None, source_snapshots=None,
                            approval_manifest=None, mode="production"):
    """Dispatch to the immutable v1 contract or the audited Option B v2 path."""
    version = feature_data.get("version") if isinstance(feature_data, dict) else None
    if isinstance(version, bool) or not isinstance(version, int):
        raise FeatureFacetError("feature facets version must be an integer")
    if version == 1:
        return _validate_feature_facets_v1(feature_data, mushroom_master)
    if version != 2:
        raise FeatureFacetError(f"unsupported feature facets version: {version}")
    if mode not in ("production", "review"):
        raise FeatureFacetError(f"unsupported validation mode: {mode}")
    if sources is None or evidence_ledger is None or source_snapshots is None:
        raise FeatureFacetError("v2 requires sources, evidence ledger, and source snapshots")
    _validate_feature_facets_v2(feature_data, mushroom_master, sources,
                                evidence_ledger, source_snapshots)
    if mode == "production":
        _validate_v2_approval(feature_data, mushroom_master, sources,
                              evidence_ledger, source_snapshots, approval_manifest)
    return True


def _validate_feature_facets_v1(feature_data, mushroom_master):
    """Validate the complete v1 curated index without mutating either input."""
    groups = _rows(feature_data, "groups")
    facets = _rows(feature_data, "facets")
    entries = _rows(feature_data, "entries")
    masters = _rows(mushroom_master, "entries")

    def unique(rows, key, kind):
        result = {}
        for row in rows:
            value = row.get(key) if isinstance(row, dict) else None
            if not isinstance(value, str) or not value.strip():
                raise FeatureFacetError(f"{kind} requires non-empty {key}")
            if value in result:
                raise FeatureFacetError(f"duplicate {key}: {value}")
            result[value] = row
        return result

    group_map = unique(groups, "group_id", "group")
    facet_map = unique(facets, "facet_id", "facet")
    master_map = unique(masters, "mushroom_id", "mushroom master")
    entry_map = unique(entries, "mushroom_id", "feature entry")
    for facet_id, facet in facet_map.items():
        if facet.get("group_id") not in group_map:
            raise FeatureFacetError(f"facet_id {facet_id}: unknown group_id {facet.get('group_id')}")

    used = set()
    for mushroom_id, entry in entry_map.items():
        master = master_map.get(mushroom_id)
        if master is None:
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: unknown mushroom")
        features = master.get("features") if isinstance(master.get("features"), dict) else {}
        summary = features.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: features.summary is required")
        expected_sources = features.get("source_ids")
        assignments = entry.get("assignments")
        if not isinstance(assignments, list):
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: assignments must be a list")
        seen = set()
        for assignment in assignments:
            facet_id = assignment.get("facet_id") if isinstance(assignment, dict) else None
            context = f"mushroom_id {mushroom_id}, facet_id {facet_id}"
            if facet_id not in facet_map:
                raise FeatureFacetError(f"{context}: unknown facet")
            if facet_id in seen:
                raise FeatureFacetError(f"{context}: duplicate assignment")
            seen.add(facet_id); used.add(facet_id)
            evidence = assignment.get("evidence_text")
            if not isinstance(evidence, str) or not evidence.strip():
                raise FeatureFacetError(f"{context}: evidence_text must be non-empty")
            if evidence not in summary:
                raise FeatureFacetError(f"{context}: evidence_text is not an exact summary substring")
            sources = assignment.get("source_ids")
            if not isinstance(sources, list) or not sources:
                raise FeatureFacetError(f"{context}: source_ids must be non-empty")
            if set(sources) != set(expected_sources or []):
                raise FeatureFacetError(f"{context}: source_ids do not match features.source_ids")

    covered = {row["mushroom_id"] for row in masters
               if isinstance(row.get("features"), dict)
               and isinstance(row["features"].get("summary"), str)
               and row["features"]["summary"].strip()}
    if set(entry_map) != covered:
        raise FeatureFacetError(
            f"mushroom_id coverage mismatch: missing={sorted(covered-set(entry_map))}, "
            f"extra={sorted(set(entry_map)-covered)}")
    unused = set(facet_map) - used
    if unused:
        raise FeatureFacetError(f"unused facet_id values: {sorted(unused)}")
    return True


def _unique(rows, key, kind):
    result = {}
    for row in rows:
        value = row.get(key) if isinstance(row, dict) else None
        if not isinstance(value, str) or not value.strip():
            raise FeatureFacetError(f"{kind} requires non-empty {key}")
        if value in result:
            raise FeatureFacetError(f"duplicate {key}: {value}")
        result[value] = row
    return result


def _strings(value, context, *, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value):
        raise FeatureFacetError(f"{context} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise FeatureFacetError(f"{context} requires non-empty string IDs")
    if len(value) != len(set(value)):
        raise FeatureFacetError(f"{context} contains duplicate IDs")
    return value


def _snapshot_rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return [json.loads(line) for line in value.splitlines() if line.strip()]
        except json.JSONDecodeError as error:
            raise FeatureFacetError(f"invalid source snapshot JSONL: {error}") from error
    raise FeatureFacetError("source_snapshots must be a JSONL string or list")


def _validate_feature_facets_v2(feature_data, mushroom_master, sources,
                                evidence_ledger, source_snapshots):
    groups = _unique(_rows(feature_data, "groups"), "group_id", "group")
    facets = _unique(_rows(feature_data, "facets"), "facet_id", "facet")
    entries = _unique(_rows(feature_data, "entries"), "mushroom_id", "feature entry")
    masters = _unique(_rows(mushroom_master, "entries"), "mushroom_id", "mushroom master")
    source_map = _unique(_rows(sources, "sources"), "source_id", "source")
    for facet_id, facet in facets.items():
        if facet.get("group_id") not in groups:
            raise FeatureFacetError(f"facet_id {facet_id}: unknown group_id")

    evidence_map = _unique(_rows(evidence_ledger, "evidence_records"),
                           "evidence_id", "evidence")
    approved_rows = _rows(evidence_ledger, "approved_assignments")
    held = _rows(evidence_ledger, "held_decisions")
    retired_map = _unique(_rows(evidence_ledger, "retired_citations"),
                          "evidence_id", "retired citation")

    def decision_rows(rows, kind):
        by_decision = {}
        by_key = {}
        for row in rows:
            if not isinstance(row, dict):
                raise FeatureFacetError(f"{kind} rows must be objects")
            decision_id = row.get("decision_id")
            mushroom_id = row.get("mushroom_id")
            facet_id = row.get("facet_id")
            for value, label in (
                (decision_id, "decision_id"),
                (mushroom_id, "mushroom_id"),
                (facet_id, "facet_id"),
            ):
                if not isinstance(value, str) or not value.strip():
                    raise FeatureFacetError(f"{kind} requires non-empty {label}")
            if decision_id in by_decision:
                raise FeatureFacetError(f"duplicate decision_id: {decision_id}")
            key = (mushroom_id, facet_id)
            if key in by_key:
                raise FeatureFacetError(f"duplicate {kind} assignment key: {key}")
            by_decision[decision_id] = row
            by_key[key] = row
        return by_decision, by_key

    approved_decisions, approved_by_key = decision_rows(approved_rows, "approved assignment")
    held_decisions, held_by_key = decision_rows(held, "held decision")
    if (len(approved_by_key) != 373 or len(held_by_key) != 10
            or set(approved_decisions) & set(held_decisions)):
        raise FeatureFacetError("original assignment boundary mismatch")

    held_evidence_rows = []
    for row in held:
        records = row.get("evidence_records")
        if not isinstance(records, list) or not records:
            raise FeatureFacetError(
                f"held decision {row['decision_id']}: evidence_records must be non-empty")
        held_evidence_rows.extend(records)
    held_evidence_map = _unique(held_evidence_rows, "evidence_id", "held evidence")
    if len(evidence_map) != 377 or len(held_evidence_map) != 10 or len(retired_map) != 1:
        raise FeatureFacetError("historical evidence boundary mismatch")
    if (set(evidence_map) & set(held_evidence_map)
            or set(evidence_map) & set(retired_map)
            or set(held_evidence_map) & set(retired_map)):
        raise FeatureFacetError("active/held/retired evidence IDs must be disjoint")
    forbidden_refs = set(held_evidence_map) | set(retired_map)

    used = set()
    assignment_keys = set()
    for mushroom_id, entry in entries.items():
        if mushroom_id not in masters:
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: unknown mushroom")
        summary = (masters[mushroom_id].get("features") or {}).get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: features.summary is required")
        assignments = entry.get("assignments")
        if not isinstance(assignments, list) or not assignments:
            raise FeatureFacetError(f"mushroom_id {mushroom_id}: assignments must be non-empty")
        seen = set()
        for assignment in assignments:
            facet_id = assignment.get("facet_id") if isinstance(assignment, dict) else None
            context = f"mushroom_id {mushroom_id}, facet_id {facet_id}"
            if not isinstance(facet_id, str) or not facet_id.strip() or facet_id not in facets:
                raise FeatureFacetError(f"{context}: unknown facet")
            if facet_id in seen:
                raise FeatureFacetError(f"{context}: duplicate assignment")
            seen.add(facet_id)
            used.add(facet_id)
            assignment_keys.add((mushroom_id, facet_id))

            evidence_text = assignment.get("evidence_text")
            if not isinstance(evidence_text, str) or not evidence_text.strip():
                raise FeatureFacetError(f"{context}: evidence_text must be non-empty")
            source_ids = _strings(assignment.get("source_ids"), f"{context}: source_ids")
            unknown = set(source_ids) - set(source_map)
            if unknown:
                raise FeatureFacetError(f"{context}: unknown source {sorted(unknown)}")
            refs = _strings(assignment.get("evidence_refs"), f"{context}: evidence_refs")
            if set(refs) & forbidden_refs:
                raise FeatureFacetError(f"{context}: held or retired evidence is not active support")
            qualifiers = assignment.get("qualifiers")
            if not isinstance(qualifiers, list):
                raise FeatureFacetError(f"{context}: qualifiers must be a list")
            if any(not isinstance(value, str) or not value.strip() for value in qualifiers):
                raise FeatureFacetError(f"{context}: qualifiers require non-empty strings")
            if len(qualifiers) != len(set(qualifiers)):
                raise FeatureFacetError(f"{context}: duplicate qualifier")

            kind = assignment.get("evidence_kind")
            if kind not in ("source_quote", "source_supported_paraphrase"):
                raise FeatureFacetError(f"{context}: unsupported evidence_kind")
            review = assignment.get("review")
            if not isinstance(review, dict):
                raise FeatureFacetError(f"{context}: review metadata is required")
            decision_id = review.get("decision_id")
            if not isinstance(decision_id, str) or not decision_id.strip():
                raise FeatureFacetError(f"{context}: review decision_id is required")
            if review.get("human_approval") is not None:
                raise FeatureFacetError(
                    f"{context}: candidate human_approval must remain historical null")

            approved = approved_by_key.get((mushroom_id, facet_id))
            if approved is None:
                raise FeatureFacetError(f"{context}: assignment is not approved")
            if approved.get("decision_id") != decision_id:
                raise FeatureFacetError(f"{context}: approved decision binding mismatch")
            if approved.get("review_result") != "supports_facet":
                raise FeatureFacetError(f"{context}: approved decision is not supporting")

            records = []
            for ref in refs:
                record = evidence_map.get(ref)
                if record is None:
                    raise FeatureFacetError(f"{context}: unknown evidence_ref {ref}")
                if record.get("mushroom_id") != mushroom_id:
                    raise FeatureFacetError(f"{context}: evidence {ref} belongs to another mushroom")
                if record.get("facet_id") != facet_id:
                    raise FeatureFacetError(f"{context}: evidence {ref} belongs to another facet")
                if record.get("review_result") != "supports_facet":
                    raise FeatureFacetError(f"{context}: evidence {ref} is not supporting evidence")
                source_id = record.get("source_id")
                if not isinstance(source_id, str) or not source_id.strip() or source_id not in source_map:
                    raise FeatureFacetError(f"{context}: evidence {ref} has unknown source")
                source = source_map[source_id]
                if record.get("source_url") != source.get("url"):
                    raise FeatureFacetError(f"{context}: evidence {ref} source URL mismatch")
                records.append(record)

            if set(source_ids) != {row.get("source_id") for row in records}:
                raise FeatureFacetError(f"{context}: source set differs from active evidence")

            raw = json.dumps(assignment, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()
            expected = (approved.get("runtime_assignment_digest") or {}).get("sha256")
            if hashlib.sha256(raw).hexdigest() != expected:
                raise FeatureFacetError(f"{context}: approved assignment digest mismatch")

            for record in records:
                ref = record["evidence_id"]
                if record.get("decision_id") != decision_id:
                    raise FeatureFacetError(f"{context}: evidence {ref} decision binding mismatch")
                if record.get("evidence_kind") != kind:
                    raise FeatureFacetError(f"{context}: evidence {ref} evidence_kind mismatch")
                if record.get("evidence_text") != evidence_text:
                    raise FeatureFacetError(f"{context}: evidence {ref} evidence_text mismatch")
                if list(record.get("qualifiers") or []) != qualifiers:
                    raise FeatureFacetError(f"{context}: evidence {ref} qualifier mismatch")

    if set(facets) - used:
        raise FeatureFacetError(f"unused facet_id values: {sorted(set(facets)-used)}")
    if len(groups) != 4 or len(facets) != 20:
        raise FeatureFacetError("v2 group/facet boundary mismatch")
    if assignment_keys != set(approved_by_key):
        raise FeatureFacetError("runtime assignment set differs from approved assignments")
    if set(held_by_key) & assignment_keys:
        raise FeatureFacetError("held assignment present in runtime")
    if ("tamagotakemodoki", "ring") in assignment_keys:
        raise FeatureFacetError("IA-029 ring is not approved")

    snapshots = _unique(_snapshot_rows(source_snapshots), "source_id", "snapshot")
    evidence_source_ids = {row.get("source_id") for row in evidence_map.values()}
    for evidence_id, record in evidence_map.items():
        source_id = record.get("source_id")
        snapshot = snapshots.get(source_id)
        if snapshot is None:
            raise FeatureFacetError(f"evidence {evidence_id}: missing snapshot")
        text = snapshot.get("full_extracted_text")
        if not isinstance(text, str):
            raise FeatureFacetError(f"evidence {evidence_id}: snapshot text missing")
        if snapshot.get("encoding") != "UTF-8":
            raise FeatureFacetError(f"evidence {evidence_id}: snapshot encoding mismatch")
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if (text_hash != snapshot.get("extracted_text_sha256")
                or text_hash != snapshot.get("text_snapshot_sha256")):
            raise FeatureFacetError(f"evidence {evidence_id}: snapshot text hash mismatch")
        if (snapshot.get("unicode_codepoint_length") != len(text)
                or snapshot.get("utf8_byte_length") != len(text.encode("utf-8"))):
            raise FeatureFacetError(f"evidence {evidence_id}: snapshot length mismatch")
        if snapshot.get("lf_line_count") != 1 + text.count("\n"):
            raise FeatureFacetError(f"evidence {evidence_id}: snapshot LF line count mismatch")
        source = source_map.get(source_id)
        if source is None or snapshot.get("source_url") != source.get("url"):
            raise FeatureFacetError(f"evidence {evidence_id}: snapshot source binding mismatch")
        for field in (
            "snapshot_identity",
            "extracted_text_sha256",
            "text_snapshot_sha256",
            "original_response_sha256",
        ):
            if record.get(field) != snapshot.get(field):
                label = "snapshot identity" if field == "snapshot_identity" else field
                raise FeatureFacetError(f"evidence {evidence_id}: {label} mismatch")

        start = record.get("char_start")
        end = record.get("char_end")
        quote = record.get("quote")
        if (not isinstance(start, int) or isinstance(start, bool)
                or not isinstance(end, int) or isinstance(end, bool)):
            raise FeatureFacetError(f"evidence {evidence_id}: invalid character offsets")
        if not isinstance(quote, str):
            raise FeatureFacetError(f"evidence {evidence_id}: quote must be a string")
        if start < 0 or end < start or end > len(text) or text[start:end] != quote:
            raise FeatureFacetError(f"evidence {evidence_id}: quote/offset mismatch")
        if hashlib.sha256(quote.encode("utf-8")).hexdigest() != record.get("quote_sha256"):
            raise FeatureFacetError(f"evidence {evidence_id}: quote hash mismatch")
        line_start = 1 + text[:start].count("\n")
        line_end = line_start + quote.count("\n")
        if (line_start, line_end) != (
                record.get("snapshot_line_start"), record.get("snapshot_line_end")):
            raise FeatureFacetError(f"evidence {evidence_id}: line range mismatch")
        exact = record.get("evidence_text_exact_substring_of_this_quote")
        if not isinstance(exact, bool):
            raise FeatureFacetError(f"evidence {evidence_id}: exact-substring flag must be boolean")
        if exact != (record.get("evidence_text") in quote):
            raise FeatureFacetError(f"evidence {evidence_id}: exact-substring flag mismatch")

    if set(snapshots) != evidence_source_ids or len(snapshots) != 130:
        raise FeatureFacetError("snapshot source set/count mismatch")

    eligible = {key for key, row in masters.items()
                if isinstance((row.get("features") or {}).get("summary"), str)
                and (row.get("features") or {}).get("summary").strip()}
    included = set(entries)
    expected_held_keys = {
        (row["decision_id"], row["mushroom_id"], row["facet_id"]) for row in held
    }

    def validate_coverage_block(coverage, label):
        if not isinstance(coverage, dict):
            raise FeatureFacetError(f"{label} coverage must be an object")
        recorded_eligible = set(_strings(
            coverage.get("eligible_mushroom_ids"),
            f"{label} coverage eligible_mushroom_ids"))
        recorded_included = set(_strings(
            coverage.get("included_mushroom_ids"),
            f"{label} coverage included_mushroom_ids"))
        excluded_rows = coverage.get("excluded_mushrooms")
        if not isinstance(excluded_rows, list):
            raise FeatureFacetError(f"{label} coverage excluded_mushrooms must be a list")
        excluded = set()
        for row in excluded_rows:
            mushroom_id = row.get("mushroom_id") if isinstance(row, dict) else None
            if (not isinstance(mushroom_id, str) or not mushroom_id.strip()
                    or mushroom_id in excluded):
                raise FeatureFacetError(
                    f"{label} excluded mushroom IDs must be unique non-empty strings")
            if (not isinstance(row.get("reason"), str) or not row["reason"].strip()
                    or not isinstance(row.get("status"), str) or not row["status"].strip()):
                raise FeatureFacetError(
                    f"{label} excluded mushroom {mushroom_id}: reason/status required")
            excluded.add(mushroom_id)

        if recorded_eligible != eligible:
            raise FeatureFacetError(f"{label} eligible coverage mismatch")
        if recorded_included != included:
            raise FeatureFacetError(f"{label} included coverage mismatch")
        if included & excluded or excluded - eligible or eligible != included | excluded:
            raise FeatureFacetError(f"{label} eligible/included/excluded coverage mismatch")
        if len(eligible) != 139 or len(included) != 127 or len(excluded) != 12:
            raise FeatureFacetError(f"{label} coverage boundary mismatch")
        if (coverage.get("assignment_count") != len(assignment_keys)
                or coverage.get("entry_count") != len(included)
                or coverage.get("active_facet_count") != len(facets)):
            raise FeatureFacetError(f"{label} coverage count mismatch")

        coverage_held = coverage.get("held_assignments")
        if not isinstance(coverage_held, list):
            raise FeatureFacetError(f"{label} coverage held_assignments must be a list")
        coverage_held_keys = set()
        for row in coverage_held:
            if not isinstance(row, dict):
                raise FeatureFacetError(f"{label} held assignment rows must be objects")
            decision_id = row.get("decision_id")
            mushroom_id = row.get("mushroom_id")
            facet_id = row.get("facet_id")
            reason = row.get("reason")
            if any(not isinstance(value, str) or not value.strip()
                   for value in (decision_id, mushroom_id, facet_id, reason)):
                raise FeatureFacetError(
                    f"{label} held assignment requires decision/mushroom/facet/reason")
            key = (decision_id, mushroom_id, facet_id)
            if key in coverage_held_keys:
                raise FeatureFacetError(f"{label} duplicate held assignment")
            coverage_held_keys.add(key)
        if coverage_held_keys != expected_held_keys:
            raise FeatureFacetError(f"{label} held assignment coverage mismatch")

    validate_coverage_block(feature_data.get("coverage"), "candidate")
    validate_coverage_block(evidence_ledger.get("coverage"), "ledger")

def _bytes_and_object(role):
    filename, expected = _V2_FILES[role]
    raw = (_V2_DIR / filename).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise FeatureFacetError(f"trusted {role} artifact hash mismatch")
    if role == "snapshots":
        return raw, [json.loads(line) for line in raw.decode().splitlines() if line]
    return raw, json.loads(raw)


def _validate_v2_approval(feature_data, mushroom_master, sources,
                          evidence_ledger, source_snapshots, approval_manifest):
    if approval_manifest is None:
        raise FeatureFacetError("production v2 validation requires approval manifest")
    supplied = {"candidate": feature_data, "master": mushroom_master, "sources": sources,
                "ledger": evidence_ledger, "snapshots": _snapshot_rows(source_snapshots),
                "manifest": approval_manifest}
    for role, value in supplied.items():
        _, trusted = _bytes_and_object(role)
        if value != trusted:
            raise FeatureFacetError(f"{role} does not match the hash-pinned approved package")
    if approval_manifest.get("approved_option") != "B" or approval_manifest.get("ia029_ring") != "not_approved":
        raise FeatureFacetError("approval manifest scope mismatch")


def build_feature_search_model(portal_data, feature_data, safe_filename=lambda value: value):
    """Join subjects only through their explicit mushroom_master_id."""
    if not isinstance(portal_data, dict) or portal_data.get("version") != 1:
        raise ValueError("feature UI requires portal-data schema version 1")
    facets = {row["facet_id"]: row for row in feature_data["facets"]}
    assignment_rows = {row["mushroom_id"]: row["assignments"] for row in feature_data["entries"]}
    results = []
    for subject in portal_data.get("subjects", []):
        subject_assignments = assignment_rows.get(subject.get("mushroom_master_id"))
        if not subject_assignments:
            continue
        facet_ids = [item["facet_id"] for item in subject_assignments]
        name = subject.get("gallery_name")
        if not isinstance(name, str) or not name:
            continue
        result = {"gallery_name": name, "cover_src": subject.get("cover_src", ""),
                  "href": f"{safe_filename(name)}.html", "facet_ids": list(facet_ids),
                  "facet_labels": [facets[value]["label"] for value in facet_ids]}
        if feature_data.get("version") == 2:
            result["assignments"] = [{"facet_id": item["facet_id"],
                                      "evidence_text": item["evidence_text"],
                                      "qualifiers": list(item.get("qualifiers") or [])}
                                     for item in subject_assignments]
        results.append(result)
    counts = {facet_id: sum(facet_id in row["facet_ids"] for row in results) for facet_id in facets}
    groups = [{**group, "facets": [{**facet, "count": counts[facet["facet_id"]]}
               for facet in feature_data["facets"] if facet["group_id"] == group["group_id"]]}
              for group in feature_data["groups"]]
    return {"groups": groups, "results": results, "coverage_count": len(results)}


def render_feature_page(model, safe_filename=None):
    groups = []
    for group in model["groups"]:
        buttons = "".join(
            f'<button type="button" class="feature-filter" data-facet="{html.escape(f["facet_id"], quote=True)}" '
            f'aria-pressed="false">{html.escape(f["label"])} <span>{f["count"]}</span></button>'
            for f in group["facets"])
        groups.append(
            f'<fieldset><legend>{html.escape(group["label"])}</legend>'
            f'<div class="feature-buttons">{buttons}</div></fieldset>'
        )
    cards = []
    for row in model["results"]:
        name = html.escape(row["gallery_name"])
        cover = html.escape(str(row["cover_src"]), quote=True)
        details = {item["facet_id"]: item for item in row.get("assignments", [])}
        chips = "".join(
            f'<span class="feature-chip" data-facet-chip="{html.escape(facet_id, quote=True)}">'
            f'{html.escape(label)}'
            + (f'<small class="feature-qualifier">{html.escape(details[facet_id]["evidence_text"])}'
               + (f'（{html.escape("、".join(details[facet_id]["qualifiers"]))}）'
                  if details[facet_id]["qualifiers"] else '') + '</small>'
               if facet_id in details else '') + '</span>'
            for facet_id, label in zip(row["facet_ids"], row["facet_labels"])
        )
        cards.append(
            f'<a class="mushroom-card feature-card" href="{html.escape(row["href"], quote=True)}" '
            f'data-name="{name}" data-facets="{html.escape(" ".join(row["facet_ids"]), quote=True)}">'
            f'<div class="mushroom-card-thumb"><span class="card-fav">☆</span>'
            f'<img src="{cover}?width=400" alt="{name}" loading="lazy"></div>'
            f'<div class="mushroom-card-name">{name}</div>'
            f'<div class="feature-chips">{chips}</div></a>'
        )
    count = model["coverage_count"]
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>特徴から探す｜キノコ図鑑</title>
<link rel="stylesheet" href="assets/gallery.css">
<link rel="stylesheet" href="assets/features.css">
<script src="assets/gallery.js" defer></script>
<script src="assets/features.js" defer></script>
</head>
<body class="feature-index">
<main id="gallery-content-root" class="feature-page">
  <section class="feature-hub" aria-labelledby="feature-title">
    <header class="feature-hero">
      <a class="feature-back-link" href="index.html">← 図鑑へ戻る</a>
      <div class="feature-hero-copy">
        <span class="feature-eyebrow">FEATURE FINDER</span>
        <h1 id="feature-title">特徴から探す</h1>
        <p>写真や資料に記載された見た目の特徴を組み合わせて探せます。</p>
      </div>
    </header>
    <div class="feature-hub-body">
      <div class="feature-heading">
        <span class="feature-eyebrow">FILTER BY APPEARANCE</span>
        <h2>特徴を選ぶ</h2>
        <p>選んだ特徴をすべて含む図鑑登録種を表示します。条件は複数選択できます。</p>
      </div>
      <p class="feature-warning">選んだ特徴が出典資料に明記されている図鑑登録種だけを表示します。特徴だけでキノコの種類を判定する機能ではありません。</p>
      <p class="feature-warning">表示する状態や条件は、同じ個体で同時に現れることを保証するものではありません。</p>
      <div class="feature-coverage"><span>特徴検索対応</span><strong>{count}</strong><span>種類</span></div>
      <section class="feature-controls" aria-label="特徴で絞り込む">
        {''.join(groups)}
        <button type="button" class="feature-clear">選択をクリア</button>
      </section>
    </div>
  </section>
  <section class="feature-results-panel" aria-labelledby="feature-results-title">
    <header class="feature-results-heading">
      <div><span class="feature-eyebrow">MATCHING MUSHROOMS</span><h2 id="feature-results-title">該当するキノコ</h2></div>
      <div class="feature-result-count" aria-live="polite">{count}種類</div>
    </header>
    <div class="mushroom-list feature-results">{''.join(cards)}</div>
    <p class="feature-empty" hidden>該当する図鑑登録種はありません。条件を減らしてみてください。</p>
  </section>
  <footer class="feature-footer"><a href="index.html">← キノコ図鑑へ戻る</a></footer>
</main>
</body>
</html>'''


def generate_feature_page(portal_data, feature_data, output_dir, assets_dir, safe_filename,
                          *, mushroom_master=None, sources=None, evidence_ledger=None,
                          source_snapshots=None, approval_manifest=None):
    if feature_data.get("version") == 2:
        validate_feature_facets(
            feature_data, mushroom_master, sources=sources,
            evidence_ledger=evidence_ledger, source_snapshots=source_snapshots,
            approval_manifest=approval_manifest, mode="production")
    model = build_feature_search_model(portal_data, feature_data, safe_filename)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)
    with open(os.path.join(output_dir, "features.html"), "w", encoding="utf-8") as stream:
        stream.write(render_feature_page(model))
    for filename in ("features.css", "features.js"):
        shutil.copy2(os.path.join(assets_dir, filename), os.path.join(output_dir, "assets", filename))
    return model
