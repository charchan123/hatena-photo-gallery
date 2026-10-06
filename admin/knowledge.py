"""Fail-closed local intake and human promotion for knowledge batches."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from feature_overlay import (FeatureOverlayError, ID, SHA256,
    TRUSTED_FEATURE_V2_MANIFEST_SHA256, load_overlay_registry,
    reconstruct_feature_production_state)
from .core import ROOT

INBOX = ROOT / "admin/inbox"
LOCAL_STATE = ROOT / "admin/local-state/knowledge"
ARTIFACTS = {"candidate-delta.json", "source-snapshots.jsonl"}
CANDIDATE_KEYS = {"candidate_id", "mushroom_id", "assignment", "evidence_records"}
ASSIGNMENT_KEYS = {"facet_id", "evidence_text", "source_ids", "evidence_refs",
                   "evidence_kind", "qualifiers", "review"}
REVIEW_KEYS = {"decision_id", "status", "reviewer_kind", "human_approval"}
EVIDENCE_KEYS = {"evidence_id", "decision_id", "mushroom_id", "facet_id",
                 "source_id", "source_url", "evidence_kind", "evidence_text",
                 "qualifiers", "quote", "quote_sha256", "char_start", "char_end",
                 "snapshot_identity", "extracted_text_sha256", "text_snapshot_sha256",
                 "original_response_sha256", "snapshot_line_start", "snapshot_line_end",
                 "evidence_text_exact_substring_of_this_quote"}
SNAPSHOT_KEYS = {"source_id", "source_url", "full_extracted_text", "encoding",
                 "snapshot_identity", "extracted_text_sha256", "text_snapshot_sha256",
                 "original_response_sha256", "unicode_codepoint_length",
                 "utf8_byte_length", "lf_line_count"}
SOURCE_KEYS = {"source_id", "organization", "title", "source_type", "url",
               "record_id", "accessed_at", "notes"}
MUSHROOM_KEYS = {"mushroom_id", "canonical_name_ja", "name_ja_sources", "aliases_ja",
                 "scientific_name", "taxonomy", "food_safety", "toxins", "features",
                 "season", "habitat", "verification"}


class KnowledgeError(ValueError):
    pass


def _hash(data): return hashlib.sha256(data).hexdigest()
def _dump(value): return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def _safe_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise KnowledgeError("unsafe batch ID")
    return value


def _batch_dir(batch_id, inbox=INBOX):
    batch_id = _safe_id(batch_id); raw_inbox = Path(inbox)
    if raw_inbox.is_symlink(): raise KnowledgeError("inbox root symlink is forbidden")
    inbox = raw_inbox.resolve()
    path = raw_inbox / batch_id
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(inbox)
    except (OSError, ValueError) as error:
        raise KnowledgeError("batch directory escapes inbox") from error
    if path.is_symlink() or not resolved.is_dir():
        raise KnowledgeError("batch directory symlink/non-directory is forbidden")
    return path


def _read_artifact(path, parent):
    if path.is_symlink(): raise KnowledgeError("artifact symlink is forbidden")
    try: path.resolve(strict=True).relative_to(parent.resolve())
    except (OSError, ValueError) as error: raise KnowledgeError("artifact escapes batch") from error
    try: return path.read_bytes()
    except OSError as error: raise KnowledgeError(f"missing artifact: {path.name}") from error


def _json(data, label):
    try: return json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error: raise KnowledgeError(f"invalid {label}") from error


def _jsonl(data):
    try: return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as error: raise KnowledgeError("invalid source snapshot JSONL") from error


def load_batch(batch_id, inbox=INBOX):
    directory = _batch_dir(batch_id, inbox)
    manifest_raw = _read_artifact(directory / "batch-manifest.json", directory)
    manifest = _json(manifest_raw, "batch manifest")
    required = {"schema_version","batch_id","created_at","generator","origin","base_main_sha","artifacts","counts"}
    if set(manifest) != required or manifest.get("schema_version") != 1: raise KnowledgeError("invalid manifest exact schema")
    if manifest.get("batch_id") != batch_id: raise KnowledgeError("batch ID mismatch")
    try: created = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError) as error: raise KnowledgeError("created_at must be ISO-8601") from error
    if created.tzinfo is None or created > datetime.now(timezone.utc): raise KnowledgeError("created_at requires timezone and cannot be future")
    if not all(isinstance(manifest.get(k), str) and manifest[k] for k in ("generator","origin")): raise KnowledgeError("generator/origin required")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("base_main_sha", ""))): raise KnowledgeError("invalid base_main_sha")
    rows = manifest.get("artifacts")
    if not isinstance(rows, list) or len(rows) != 2: raise KnowledgeError("artifact exact set mismatch")
    artifacts = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path","sha256","bytes"}: raise KnowledgeError("invalid artifact row")
        name = row.get("path")
        if name in artifacts or name not in ARTIFACTS: raise KnowledgeError("artifact exact set mismatch")
        if not SHA256.fullmatch(str(row.get("sha256", ""))): raise KnowledgeError("invalid artifact hash")
        if isinstance(row.get("bytes"), bool) or not isinstance(row.get("bytes"), int) or row["bytes"] < 0: raise KnowledgeError("invalid artifact bytes")
        raw = _read_artifact(directory / name, directory)
        if len(raw) != row["bytes"]: raise KnowledgeError(f"artifact bytes mismatch: {name}")
        if _hash(raw) != row["sha256"]: raise KnowledgeError(f"artifact hash mismatch: {name}")
        artifacts[name] = raw
    delta = _json(artifacts["candidate-delta.json"], "candidate delta")
    snapshots = _jsonl(artifacts["source-snapshots.jsonl"])
    if set(delta) != {"schema_version","mushroom_additions","source_additions","assignment_additions"} or delta.get("schema_version") != 1: raise KnowledgeError("invalid candidate delta schema")
    for key in ("mushroom_additions","source_additions","assignment_additions"):
        if not isinstance(delta[key], list): raise KnowledgeError(f"{key} must be a list")
    expected_counts = {"mushroom_additions":len(delta["mushroom_additions"]), "source_additions":len(delta["source_additions"]), "assignment_candidates":len(delta["assignment_additions"]), "snapshots":len(snapshots)}
    counts = manifest.get("counts")
    if not isinstance(counts, dict) or set(counts) != set(expected_counts) or any(isinstance(v,bool) or not isinstance(v,int) or v < 0 for v in counts.values()) or counts != expected_counts: raise KnowledgeError("manifest counts mismatch")
    return {"directory":directory,"manifest":manifest,"manifest_raw":manifest_raw,"manifest_sha256":_hash(manifest_raw),"delta":delta,"snapshots":snapshots,"raw":artifacts}


def _copy_contract_root(destination, source_root=ROOT):
    source_root = Path(source_root)
    for relative in ("audit/phase4c9/v2", "audit/feature-overlays", "data"):
        source, target = source_root / relative, destination / relative
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copytree(source, target)
    source = source_root / "audit/knowledge-batches"
    if source.exists(): shutil.copytree(source, destination / "audit/knowledge-batches")


def _available_snapshot_ids(contract_root=ROOT):
    """Return validated baseline/prior-overlay snapshot IDs, not source IDs."""
    root = Path(contract_root)
    registry_path = root / "audit/feature-overlays/index.json"
    reconstruct_feature_production_state(root=root, registry_path=registry_path)
    registry = load_overlay_registry(registry_path, root)
    baseline_path = root / "audit/phase4c9/v2/phase4c9-feature-source-snapshots-2026-10-03.jsonl"
    ids = {json.loads(line)["source_id"] for line in baseline_path.read_text(encoding="utf-8").splitlines() if line}
    for row in registry["overlays"]:
        manifest_path = root / row["manifest_path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        snapshot_path = manifest_path.parent / next(a["path"] for a in manifest["artifacts"] if a["path"] == "source-snapshots.jsonl")
        ids.update(json.loads(line)["source_id"] for line in snapshot_path.read_text(encoding="utf-8").splitlines() if line)
    return ids


def _state_path(batch_id, state_root=LOCAL_STATE):
    batch_id=_safe_id(batch_id); root=Path(state_root)
    if root.exists() and root.is_symlink(): raise KnowledgeError("local state directory symlink is forbidden")
    if root.parent.exists() and root.parent.is_symlink(): raise KnowledgeError("local state parent symlink is forbidden")
    root.mkdir(parents=True, exist_ok=True)
    path=root/f"{batch_id}.json"
    if path.exists() and path.is_symlink(): raise KnowledgeError("local state symlink is forbidden")
    return path


def _initial_state(batch):
    return {"schema_version":1,"batch_id":batch["manifest"]["batch_id"],"batch_manifest_sha256":batch["manifest_sha256"],"reviewed_at":datetime.now(timezone.utc).isoformat(),"decisions":[{"candidate_id":c["candidate_id"],"human_decision":"pending","note":""} for c in batch["delta"]["assignment_additions"]]}


def load_review_state(batch_id, *, inbox=INBOX, state_root=LOCAL_STATE):
    batch=load_batch(batch_id,inbox); path=_state_path(batch_id,state_root)
    if not path.exists(): return _initial_state(batch), False
    state=_json(path.read_bytes(),"review state")
    if state.get("batch_manifest_sha256") != batch["manifest_sha256"]: return _initial_state(batch), True
    ids=[c["candidate_id"] for c in batch["delta"]["assignment_additions"]]
    decisions=state.get("decisions")
    if set(state) != {"schema_version","batch_id","batch_manifest_sha256","reviewed_at","decisions"} or state.get("schema_version") != 1 or state.get("batch_id") != batch_id or not isinstance(decisions,list) or [d.get("candidate_id") for d in decisions] != ids: raise KnowledgeError("invalid review state")
    if any(set(d)!={"candidate_id","human_decision","note"} or d["human_decision"] not in {"pending","approved","held"} or not isinstance(d["note"],str) for d in decisions): raise KnowledgeError("invalid review decision")
    return state, False


def save_review_state(state, *, state_root=LOCAL_STATE):
    path=_state_path(state["batch_id"],state_root); data=_dump(state)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return state


def reset_review_state(batch_id, *, inbox=INBOX, state_root=LOCAL_STATE):
    return save_review_state(_initial_state(load_batch(batch_id,inbox)),state_root=state_root)


def set_candidate_decision(batch_id,candidate_id,decision,note="",*,inbox=INBOX,state_root=LOCAL_STATE):
    if decision not in {"pending","approved","held"}: raise KnowledgeError("invalid human decision")
    state,changed=load_review_state(batch_id,inbox=inbox,state_root=state_root)
    if changed: raise KnowledgeError("batch内容が変更されたためレビューをリセットしてください")
    row=next((r for r in state["decisions"] if r["candidate_id"]==candidate_id),None)
    if row is None: raise KnowledgeError("unknown candidate ID")
    row.update(human_decision=decision,note=str(note)); state["reviewed_at"]=datetime.now(timezone.utc).isoformat()
    return save_review_state(state,state_root=state_root)


def _make_package(batch,state,contract_root=ROOT):
    decisions={r["candidate_id"]:r for r in state["decisions"]}; candidates=batch["delta"]["assignment_additions"]
    approved=[c for c in candidates if decisions[c["candidate_id"]]["human_decision"]=="approved"]
    approved_mids={c["mushroom_id"] for c in approved}; approved_sids={e["source_id"] for c in approved for e in c["evidence_records"]}
    delta={"schema_version":1,"mushroom_additions":[r for r in batch["delta"]["mushroom_additions"] if r.get("mushroom_id") in approved_mids],"source_additions":[r for r in batch["delta"]["source_additions"] if r.get("source_id") in approved_sids],"assignment_additions":approved}
    dm=[]
    by_candidate={c["candidate_id"]:c for c in candidates}
    for review in state["decisions"]:
        c=by_candidate[review["candidate_id"]]; a=c["assignment"]
        dm.append({"candidate_id":c["candidate_id"],"mushroom_id":c["mushroom_id"],"facet_id":a["facet_id"],"decision_id":a["review"]["decision_id"],"human_decision":review["human_decision"],"review_result":"supports_facet" if review["human_decision"]=="approved" else "held","note":review["note"]})
    decision={"schema_version":1,"overlay_id":batch["manifest"]["batch_id"],"reviewed_at":state["reviewed_at"],"decisions":dm}
    available_snapshot_ids = _available_snapshot_ids(contract_root)
    snapshots=[s for s in batch["snapshots"] if s.get("source_id") in approved_sids-available_snapshot_ids]
    raw={"promotion-delta.json":_dump(delta),"decision-manifest.json":_dump(decision),"source-snapshots.jsonl":b"".join((json.dumps(s,ensure_ascii=False,separators=(",",":"))+"\n").encode() for s in snapshots)}
    manifest={"schema_version":1,"overlay_id":batch["manifest"]["batch_id"],"created_at":state["reviewed_at"],"baseline_contract":"phase4c9-v2-immutable","baseline_manifest_sha256":TRUSTED_FEATURE_V2_MANIFEST_SHA256,"additive_only":True,"artifacts":[{"path":name,"sha256":_hash(data)} for name,data in raw.items()]}
    return delta,decision,snapshots,raw,manifest


def _exercise_contract(batch,state,contract_root=ROOT):
    with tempfile.TemporaryDirectory(prefix="knowledge-preview-") as name:
        root=Path(name); _copy_contract_root(root, contract_root)
        package=root/"audit/knowledge-batches"/batch["manifest"]["batch_id"]
        package.mkdir(parents=True,exist_ok=False)
        _,_,_,raw,manifest=_make_package(batch,state,contract_root)
        for filename,data in raw.items(): (package/filename).write_bytes(data)
        (package/"promotion-manifest.json").write_bytes(_dump(manifest))
        registry=json.loads((root/"audit/feature-overlays/index.json").read_text())
        registry["overlays"].append({"overlay_id":batch["manifest"]["batch_id"],"manifest_path":f"audit/knowledge-batches/{batch['manifest']['batch_id']}/promotion-manifest.json","manifest_sha256":_hash((package/"promotion-manifest.json").read_bytes())})
        registry["overlays"].sort(key=lambda r:r["overlay_id"])
        (root/"audit/feature-overlays/index.json").write_bytes(_dump(registry))
        return reconstruct_feature_production_state(root=root,registry_path=root/"audit/feature-overlays/index.json"), registry


def _require_exact(row, keys, label):
    if not isinstance(row, dict) or set(row) != keys: raise KnowledgeError(f"invalid {label} exact schema")


def _validate_intake(batch, contract_root):
    delta, snapshots = batch["delta"], batch["snapshots"]
    candidates = delta["assignment_additions"]
    for row in delta["source_additions"]: _require_exact(row, SOURCE_KEYS, "source addition")
    for row in delta["mushroom_additions"]: _require_exact(row, MUSHROOM_KEYS, "mushroom addition")
    for candidate in candidates:
        _require_exact(candidate, CANDIDATE_KEYS, "candidate")
        _require_exact(candidate["assignment"], ASSIGNMENT_KEYS, "assignment")
        _require_exact(candidate["assignment"].get("review"), REVIEW_KEYS, "assignment review")
        if candidate["assignment"]["review"].get("human_approval", object()) is not None:
            raise KnowledgeError("review human_approval must be null")
        if not isinstance(candidate.get("evidence_records"), list) or not candidate["evidence_records"]:
            raise KnowledgeError("candidate evidence_records required")
        for evidence in candidate["evidence_records"]: _require_exact(evidence, EVIDENCE_KEYS, "evidence record")
    for snapshot in snapshots: _require_exact(snapshot, SNAPSHOT_KEYS, "snapshot")
    groups = ((candidates, "candidate_id", "candidate"),
              (delta["source_additions"], "source_id", "source"),
              (delta["mushroom_additions"], "mushroom_id", "mushroom"),
              (snapshots, "source_id", "snapshot"))
    for rows, key, label in groups:
        values = [row.get(key) for row in rows]
        if any(not isinstance(v, str) or not ID.fullmatch(v) for v in values) or len(values) != len(set(values)):
            raise KnowledgeError(f"duplicate/unsafe {label} ID")
    evidence_source_ids = {e["source_id"] for c in candidates for e in c["evidence_records"]}
    candidate_mushroom_ids = {c["mushroom_id"] for c in candidates}
    source_addition_ids = {r["source_id"] for r in delta["source_additions"]}
    mushroom_addition_ids = {r["mushroom_id"] for r in delta["mushroom_additions"]}
    if source_addition_ids - evidence_source_ids: raise KnowledgeError("orphan source addition")
    if mushroom_addition_ids - candidate_mushroom_ids: raise KnowledgeError("orphan mushroom addition")
    expected_snapshots = evidence_source_ids - _available_snapshot_ids(contract_root)
    actual_snapshots = {row["source_id"] for row in snapshots}
    if actual_snapshots != expected_snapshots: raise KnowledgeError("unused or missing input snapshot")


def validate_batch(batch_id, *, inbox=INBOX, contract_root=ROOT):
    blockers=[]
    try:
        batch=load_batch(batch_id,inbox)
        _validate_intake(batch, contract_root)
        synthetic=_initial_state(batch)
        for row in synthetic["decisions"]: row["human_decision"]="approved"
        _exercise_contract(batch,synthetic,contract_root)
    except (KnowledgeError,FeatureOverlayError,KeyError,TypeError,ValueError,OSError) as error: blockers.append(str(error))
    return {"status":"PASS" if not blockers else "BLOCKER","blockers":blockers,"warnings":[]}


def preview_promotion(batch_id, *, origin_main_sha=None, inbox=INBOX, state_root=LOCAL_STATE, contract_root=ROOT):
    validation=validate_batch(batch_id,inbox=inbox,contract_root=contract_root); batch=load_batch(batch_id,inbox); state,changed=load_review_state(batch_id,inbox=inbox,state_root=state_root)
    counts={v:sum(d["human_decision"]==v for d in state["decisions"]) for v in ("approved","held","pending")}
    blockers=list(validation["blockers"])
    if changed: blockers.append("batch内容が変更されたためレビューをリセットしてください")
    if origin_main_sha != batch["manifest"]["base_main_sha"]: blockers.append("base_main_sha does not match origin/main")
    before=reconstruct_feature_production_state(root=contract_root,registry_path=Path(contract_root)/"audit/feature-overlays/index.json"); after=None
    if counts["approved"]:
        try: after,_=_exercise_contract(batch,state,contract_root)
        except (FeatureOverlayError,KnowledgeError,ValueError,OSError) as error: blockers.append(str(error))
    def metrics(value): return {"master_count":len(value["mushroom_master"]["entries"]),"source_count":len(value["sources"]["sources"]),"feature_entry_count":len(value["feature_facets"]["entries"]),"assignment_count":sum(len(r["assignments"]) for r in value["feature_facets"]["entries"]),"overlay_count":value["overlay_count"]}
    approved_ids={d["candidate_id"] for d in state["decisions"] if d["human_decision"]=="approved"}; approved=[c for c in batch["delta"]["assignment_additions"] if c["candidate_id"] in approved_ids]
    return {"status":"PASS" if not blockers else "BLOCKER","blockers":blockers,"warnings":validation["warnings"],"batch_id":batch_id,"base_main_sha":batch["manifest"]["base_main_sha"],"candidate_count":len(state["decisions"]),**{f"{k}_count":v for k,v in counts.items()},"production_before":metrics(before),"production_after":metrics(after) if after else None,"promoted_mushroom_ids":sorted({c["mushroom_id"] for c in approved}),"promoted_source_ids":sorted({e["source_id"] for c in approved for e in c["evidence_records"]}),"promoted_candidate_ids":sorted(approved_ids),"ready":not blockers and not counts["pending"] and counts["approved"]>0}


def materialize_promotion_package(batch_id,destination,*,inbox=INBOX,state_root=LOCAL_STATE,base_sha=None,contract_root=ROOT):
    batch=load_batch(batch_id,inbox); state,changed=load_review_state(batch_id,inbox=inbox,state_root=state_root)
    preview=preview_promotion(batch_id,origin_main_sha=base_sha,inbox=inbox,state_root=state_root,contract_root=contract_root)
    if changed or not preview["ready"]: raise KnowledgeError("promotion is not ready: "+"; ".join(preview["blockers"]))
    delta,decision,snapshots,raw,manifest=_make_package(batch,state,contract_root); destination=Path(destination); destination.mkdir(parents=True,exist_ok=False)
    for name,data in raw.items(): (destination/name).write_bytes(data)
    (destination/"promotion-manifest.json").write_bytes(_dump(manifest))
    intake=destination/"intake"; intake.mkdir()
    (intake/"batch-manifest.json").write_bytes(batch["manifest_raw"])
    for name,data in batch["raw"].items(): (intake/name).write_bytes(data)
    report={"schema_version":1,"batch_id":batch_id,"base_main_sha":batch["manifest"]["base_main_sha"],"batch_manifest_sha256":batch["manifest_sha256"],"validation_status":"PASS","validated_at":datetime.now(timezone.utc).isoformat(),"candidate_count":preview["candidate_count"],"approved_count":preview["approved_count"],"held_count":preview["held_count"],"pending_count":preview["pending_count"],"promoted_assignment_count":len(delta["assignment_additions"]),"promoted_mushroom_count":len(delta["mushroom_additions"]),"promoted_source_count":len(delta["source_additions"]),"promoted_snapshot_count":len(snapshots),"blockers":[],"warnings":preview["warnings"]}
    (destination/"validator-report.json").write_bytes(_dump(report)); return report


def scan_knowledge_batches(*, inbox=INBOX, state_root=LOCAL_STATE, origin_main_sha=None):
    root=Path(inbox)
    if not root.exists(): return []
    if root.is_symlink(): return [{"batch_id":"(inbox)","status":"BLOCKER","blockers":["inbox symlink is forbidden"]}]
    try:
        production = reconstruct_feature_production_state()
        mushroom_names = {row["mushroom_id"]:row["canonical_name_ja"] for row in production["mushroom_master"]["entries"]}
        facet_labels = {row["facet_id"]:row["label"] for row in production["feature_facets"]["facets"]}
    except (FeatureOverlayError, OSError, ValueError):
        mushroom_names, facet_labels = {}, {}
    rows=[]
    for path in sorted(root.iterdir()):
        try:
            batch=load_batch(path.name,inbox); validation=validate_batch(path.name,inbox=inbox); state,changed=load_review_state(path.name,inbox=inbox,state_root=state_root)
            counts={v:sum(d["human_decision"]==v for d in state["decisions"]) for v in ("approved","held","pending")}
            candidates=[]
            review={d["candidate_id"]:d for d in state["decisions"]}
            additions={m["mushroom_id"]:m["canonical_name_ja"] for m in batch["delta"]["mushroom_additions"]}
            for c in batch["delta"]["assignment_additions"]:
                a=c["assignment"]
                evidence=[{key:e[key] for key in ("evidence_id","source_id","source_url","evidence_kind","evidence_text","qualifiers","quote")} for e in c["evidence_records"]]
                candidates.append({"candidate_id":c["candidate_id"],"mushroom_id":c["mushroom_id"],"mushroom_name":additions.get(c["mushroom_id"],mushroom_names.get(c["mushroom_id"],c["mushroom_id"])),"facet_id":a["facet_id"],"facet_label":facet_labels.get(a["facet_id"],a["facet_id"]),"evidence_records":evidence,"decision_id":a["review"]["decision_id"],**review[c["candidate_id"]]})
            blockers=list(validation["blockers"])+( ["batch内容が変更されたためレビューをリセットしてください"] if changed else [])
            rows.append({"batch_id":path.name,"status":"BLOCKER" if blockers else validation["status"],"blockers":blockers,"warnings":validation["warnings"],"created_at":batch["manifest"]["created_at"],"generator":batch["manifest"]["generator"],"origin":batch["manifest"]["origin"],"base_main_sha":batch["manifest"]["base_main_sha"],"base_matches":origin_main_sha==batch["manifest"]["base_main_sha"],"candidate_count":len(candidates),**{f"{k}_count":v for k,v in counts.items()},"review_changed":changed,"candidates":candidates})
        except Exception as error: rows.append({"batch_id":path.name,"status":"BLOCKER","blockers":[str(error)],"warnings":[],"candidate_count":0,"approved_count":0,"held_count":0,"pending_count":0,"candidates":[]})
    return rows
