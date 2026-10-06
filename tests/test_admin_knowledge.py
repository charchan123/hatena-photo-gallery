from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from admin import knowledge
from admin.git_workflow import (GitWorkflowError, collect_knowledge_changed_paths,
                                create_knowledge_pull_request, validate_knowledge_changed_paths)
from feature_overlay import reconstruct_feature_production_state, validate_feature_production_state

ROOT=Path(__file__).parents[1]
BASE="26f763efdf662a91766fd06edc2d0200ce78d31f"

def dump(value): return (json.dumps(value,ensure_ascii=False,indent=2)+"\n").encode()

def make_batch(tmp_path,batch_id="batch-001"):
    inbox=tmp_path/"inbox"; directory=inbox/batch_id; directory.mkdir(parents=True)
    text="synthetic evidence quote"; digest=hashlib.sha256(text.encode()).hexdigest()
    snapshot={"source_id":"knowledge-test-source","source_url":"https://example.test/source","full_extracted_text":text,"encoding":"UTF-8","snapshot_identity":"knowledge-test-1","extracted_text_sha256":digest,"text_snapshot_sha256":digest,"original_response_sha256":"a"*64,"unicode_codepoint_length":len(text),"utf8_byte_length":len(text.encode()),"lf_line_count":1}
    evidence={"evidence_id":"knowledge-evidence-1","decision_id":"knowledge-decision-1","mushroom_id":"kiirosuppontake","facet_id":"gills","source_id":"knowledge-test-source","source_url":"https://example.test/source","evidence_kind":"source_quote","evidence_text":"synthetic evidence","qualifiers":[],"quote":text,"quote_sha256":digest,"char_start":0,"char_end":len(text),"snapshot_identity":"knowledge-test-1","extracted_text_sha256":digest,"text_snapshot_sha256":digest,"original_response_sha256":"a"*64,"snapshot_line_start":1,"snapshot_line_end":1,"evidence_text_exact_substring_of_this_quote":True}
    assignment={"facet_id":"gills","evidence_text":"synthetic evidence","source_ids":["knowledge-test-source"],"evidence_refs":["knowledge-evidence-1"],"evidence_kind":"source_quote","qualifiers":[],"review":{"decision_id":"knowledge-decision-1","status":"source_checked_candidate","reviewer_kind":"human_incremental_review","human_approval":None}}
    source={"source_id":"knowledge-test-source","organization":"Synthetic Test","title":"Synthetic fixture","source_type":"test","url":"https://example.test/source","record_id":None,"accessed_at":"2026-10-05","notes":"test only"}
    delta={"schema_version":1,"mushroom_additions":[],"source_additions":[source],"assignment_additions":[{"candidate_id":"candidate-1","mushroom_id":"kiirosuppontake","assignment":assignment,"evidence_records":[evidence]}]}
    raws={"candidate-delta.json":dump(delta),"source-snapshots.jsonl":json.dumps(snapshot,ensure_ascii=False).encode()+b"\n"}
    for name,data in raws.items():(directory/name).write_bytes(data)
    manifest={"schema_version":1,"batch_id":batch_id,"created_at":"2026-10-05T00:00:00+00:00","generator":"synthetic-test","origin":"local-test","base_main_sha":BASE,"artifacts":[{"path":n,"sha256":hashlib.sha256(d).hexdigest(),"bytes":len(d)} for n,d in raws.items()],"counts":{"mushroom_additions":0,"source_additions":1,"assignment_candidates":1,"snapshots":1}}
    (directory/"batch-manifest.json").write_bytes(dump(manifest)); return inbox,directory

def refresh_batch(directory):
    delta=json.loads((directory/"candidate-delta.json").read_text())
    snapshots=[json.loads(line) for line in (directory/"source-snapshots.jsonl").read_text().splitlines() if line]
    manifest=json.loads((directory/"batch-manifest.json").read_text())
    for row in manifest["artifacts"]:
        raw=(directory/row["path"]).read_bytes();row.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    manifest["counts"]={"mushroom_additions":len(delta["mushroom_additions"]),"source_additions":len(delta["source_additions"]),"assignment_candidates":len(delta["assignment_additions"]),"snapshots":len(snapshots)}
    (directory/"batch-manifest.json").write_bytes(dump(manifest))

def test_valid_intake_pending_review_and_decisions(tmp_path):
    inbox,_=make_batch(tmp_path); states=tmp_path/"state"
    assert knowledge.validate_batch("batch-001",inbox=inbox)["status"]=="PASS"
    state,changed=knowledge.load_review_state("batch-001",inbox=inbox,state_root=states)
    assert not changed and state["decisions"][0]["human_decision"]=="pending"
    knowledge.set_candidate_decision("batch-001","candidate-1","approved","checked",inbox=inbox,state_root=states)
    saved,_=knowledge.load_review_state("batch-001",inbox=inbox,state_root=states)
    assert saved["decisions"][0]=={"candidate_id":"candidate-1","human_decision":"approved","note":"checked"}

def test_manifest_hash_and_bytes_mismatch_block(tmp_path):
    inbox,directory=make_batch(tmp_path); manifest=json.loads((directory/"batch-manifest.json").read_text())
    manifest["artifacts"][0]["sha256"]="0"*64;(directory/"batch-manifest.json").write_bytes(dump(manifest))
    assert "hash mismatch" in knowledge.validate_batch("batch-001",inbox=inbox)["blockers"][0]
    inbox,directory=make_batch(tmp_path/"two");manifest=json.loads((directory/"batch-manifest.json").read_text());manifest["artifacts"][0]["bytes"]+=1;(directory/"batch-manifest.json").write_bytes(dump(manifest))
    assert "bytes mismatch" in knowledge.validate_batch("batch-001",inbox=inbox)["blockers"][0]

def test_unsafe_and_symlinks_rejected(tmp_path):
    with pytest.raises(knowledge.KnowledgeError): knowledge.load_batch("../escape",inbox=tmp_path)
    inbox,directory=make_batch(tmp_path); outside=tmp_path/"outside";outside.mkdir(); (outside/"x").write_text("x")
    (directory/"candidate-delta.json").unlink();(directory/"candidate-delta.json").symlink_to(outside/"x")
    assert "symlink" in knowledge.validate_batch("batch-001",inbox=inbox)["blockers"][0]
    link=tmp_path/"linked";link.symlink_to(directory,target_is_directory=True)
    with pytest.raises(knowledge.KnowledgeError): knowledge.load_batch("linked",inbox=tmp_path)

def test_duplicate_invalid_facet_ia029_and_snapshot_fail(tmp_path):
    for mode in ("duplicate","facet","ia029","snapshot"):
        inbox,directory=make_batch(tmp_path/mode);delta=json.loads((directory/"candidate-delta.json").read_text())
        if mode=="duplicate": delta["assignment_additions"].append(delta["assignment_additions"][0]);
        elif mode=="facet": delta["assignment_additions"][0]["assignment"]["facet_id"]="invented"
        elif mode=="ia029":
            c=delta["assignment_additions"][0];c["mushroom_id"]="tamagotakemodoki";c["assignment"]["facet_id"]="ring";c["evidence_records"][0].update(mushroom_id="tamagotakemodoki",facet_id="ring")
        else:
            snaps=[json.loads(x) for x in (directory/"source-snapshots.jsonl").read_text().splitlines()];snaps[0]["utf8_byte_length"]+=1;(directory/"source-snapshots.jsonl").write_text(json.dumps(snaps[0])+"\n")
        if mode!="snapshot": (directory/"candidate-delta.json").write_bytes(dump(delta))
        manifest=json.loads((directory/"batch-manifest.json").read_text())
        for row in manifest["artifacts"]:
            raw=(directory/row["path"]).read_bytes();row.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        manifest["counts"]["assignment_candidates"]=len(delta["assignment_additions"]);(directory/"batch-manifest.json").write_bytes(dump(manifest))
        assert knowledge.validate_batch("batch-001",inbox=inbox)["status"]=="BLOCKER"

def test_manifest_change_requires_explicit_reset(tmp_path):
    inbox,directory=make_batch(tmp_path);states=tmp_path/"state";knowledge.reset_review_state("batch-001",inbox=inbox,state_root=states)
    manifest=json.loads((directory/"batch-manifest.json").read_text());manifest["origin"]="changed";(directory/"batch-manifest.json").write_bytes(dump(manifest))
    state,changed=knowledge.load_review_state("batch-001",inbox=inbox,state_root=states);assert changed and state["decisions"][0]["human_decision"]=="pending"
    with pytest.raises(knowledge.KnowledgeError,match="リセット"):knowledge.set_candidate_decision("batch-001","candidate-1","held",inbox=inbox,state_root=states)
    assert knowledge.reset_review_state("batch-001",inbox=inbox,state_root=states)["decisions"][0]["human_decision"]=="pending"

def test_readiness_and_real_promotion_contract(tmp_path):
    inbox,_=make_batch(tmp_path);states=tmp_path/"state"
    assert not knowledge.preview_promotion("batch-001",origin_main_sha=BASE,inbox=inbox,state_root=states)["ready"]
    knowledge.set_candidate_decision("batch-001","candidate-1","approved",inbox=inbox,state_root=states)
    assert not knowledge.preview_promotion("batch-001",origin_main_sha="0"*40,inbox=inbox,state_root=states)["ready"]
    assert knowledge.preview_promotion("batch-001",origin_main_sha=BASE,inbox=inbox,state_root=states)["ready"]
    root=tmp_path/"repo";knowledge._copy_contract_root(root);package=root/"audit/knowledge-batches/batch-001"
    report=knowledge.materialize_promotion_package("batch-001",package,inbox=inbox,state_root=states,base_sha=BASE)
    registry=json.loads((root/"audit/feature-overlays/index.json").read_text());manifest=package/"promotion-manifest.json";registry["overlays"].append({"overlay_id":"batch-001","manifest_path":"audit/knowledge-batches/batch-001/promotion-manifest.json","manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest()});registry["overlays"].sort(key=lambda r:r["overlay_id"]);(root/"audit/feature-overlays/index.json").write_bytes(dump(registry))
    expected=reconstruct_feature_production_state(root=root,registry_path=root/"audit/feature-overlays/index.json")
    for name,key in (("mushroom-master.json","mushroom_master"),("sources.json","sources"),("feature-facets.json","feature_facets")):(root/"data"/name).write_bytes(dump(expected[key]))
    assert validate_feature_production_state(root=root,registry_path=root/"audit/feature-overlays/index.json")["overlay_count"]==1
    for name in ("batch-manifest.json","candidate-delta.json","source-snapshots.jsonl"):
        assert (package/"intake"/name).read_bytes()==(inbox/"batch-001"/name).read_bytes()
    assert report["validation_status"]=="PASS"

def test_all_held_is_not_ready(tmp_path):
    inbox,_=make_batch(tmp_path);states=tmp_path/"state"
    knowledge.set_candidate_decision("batch-001","candidate-1","held",inbox=inbox,state_root=states)
    preview=knowledge.preview_promotion("batch-001",origin_main_sha=BASE,inbox=inbox,state_root=states)
    assert preview["pending_count"]==0 and preview["approved_count"]==0 and preview["held_count"]==1
    assert not preview["ready"]

def test_mixed_decisions_exclude_held_only_objects(tmp_path):
    inbox,directory=make_batch(tmp_path);batch=knowledge.load_batch("batch-001",inbox);first=batch["delta"]["assignment_additions"][0]
    second=json.loads(json.dumps(first));second["candidate_id"]="candidate-2";second["mushroom_id"]="held-only-mushroom";second["assignment"]["facet_id"]="cap_sticky";second["assignment"]["review"]["decision_id"]="held-decision";second["evidence_records"][0].update(evidence_id="held-evidence",decision_id="held-decision",mushroom_id="held-only-mushroom",facet_id="cap_sticky",source_id="held-only-source",source_url="https://example.test/held");second["assignment"]["source_ids"]=["held-only-source"];second["assignment"]["evidence_refs"]=["held-evidence"]
    mushroom={**json.loads((ROOT/"data/mushroom-master.json").read_text())["entries"][0],"mushroom_id":"held-only-mushroom","canonical_name_ja":"保留専用テスト種"}
    source={**batch["delta"]["source_additions"][0],"source_id":"held-only-source","url":"https://example.test/held"}
    snapshot={**batch["snapshots"][0],"source_id":"held-only-source","source_url":"https://example.test/held","snapshot_identity":"held-snapshot"}
    batch["delta"]["assignment_additions"].append(second);batch["delta"]["mushroom_additions"].append(mushroom);batch["delta"]["source_additions"].append(source);batch["snapshots"].append(snapshot)
    state={"reviewed_at":"2026-10-05T00:00:00+00:00","decisions":[{"candidate_id":"candidate-1","human_decision":"approved","note":""},{"candidate_id":"candidate-2","human_decision":"held","note":"hold"}]}
    delta,decision,snapshots,_,_=knowledge._make_package(batch,state)
    assert [c["candidate_id"] for c in delta["assignment_additions"]]==["candidate-1"]
    assert "held-only-mushroom" not in {m["mushroom_id"] for m in delta["mushroom_additions"]}
    assert "held-only-source" not in {s["source_id"] for s in delta["source_additions"]}
    assert "held-only-source" not in {s["source_id"] for s in snapshots}
    assert {d["human_decision"] for d in decision["decisions"]}=={"approved","held"}

def test_allowlist_and_gh_auth(monkeypatch):
    assert validate_knowledge_changed_paths(["data/sources.json","audit/knowledge-batches/x/a"],"x")
    with pytest.raises(GitWorkflowError):validate_knowledge_changed_paths(["admin/server.py"],"x")
    monkeypatch.setattr("admin.git_workflow.repository_status",lambda:{"gh_authenticated":False})
    with pytest.raises(GitWorkflowError,match="GitHub認証"):create_knowledge_pull_request("batch-001")

def test_static_security_and_local_ignore():
    js=(ROOT/"admin/static/admin.js").read_text();assert "innerHTML" not in js and "localStorage" not in js
    assert "noopener noreferrer" in js and "source-snapshots" not in js
    ignored=(ROOT/".gitignore").read_text();assert "/admin/inbox/" in ignored and "/admin/local-state/" in ignored

def test_changed_path_collection_includes_packages_and_rejects_unexpected(tmp_path):
    repo=tmp_path/"repo";repo.mkdir();
    for args in (["git","init"],["git","config","user.email","test@example.test"],["git","config","user.name","Test"]):
        __import__("subprocess").run(args,cwd=repo,check=True,capture_output=True)
    (repo/"tracked").write_text("old");__import__("subprocess").run(["git","add","tracked"],cwd=repo,check=True);__import__("subprocess").run(["git","commit","-m","base"],cwd=repo,check=True,capture_output=True)
    (repo/"tracked").write_text("new"); package=repo/"audit/knowledge-batches/batch-001";package.mkdir(parents=True)
    package_files=["promotion-manifest.json","promotion-delta.json","decision-manifest.json","source-snapshots.jsonl","validator-report.json","intake/batch-manifest.json","intake/candidate-delta.json","intake/source-snapshots.jsonl"]
    for name in package_files: (package/name).parent.mkdir(parents=True,exist_ok=True);(package/name).write_text("{}")
    paths=collect_knowledge_changed_paths(repo)
    assert {f"audit/knowledge-batches/batch-001/{name}" for name in package_files} <= set(paths)
    with pytest.raises(GitWorkflowError): validate_knowledge_changed_paths(paths,"batch-001")
    (repo/"tracked").write_text("old");paths=collect_knowledge_changed_paths(repo);assert validate_knowledge_changed_paths(paths,"batch-001")
    __import__("subprocess").run(["git","add","--",*paths],cwd=repo,check=True)
    staged=__import__("subprocess").run(["git","diff","--cached","--name-only"],cwd=repo,check=True,text=True,capture_output=True).stdout.splitlines()
    assert sorted(staged)==paths

@pytest.mark.parametrize(("target","key"),[("candidate","extra"),("assignment","extra"),("evidence","extra"),("snapshot","extra")])
def test_unknown_intake_keys_are_blockers(tmp_path,target,key):
    inbox,directory=make_batch(tmp_path);delta=json.loads((directory/"candidate-delta.json").read_text());snaps=[json.loads((directory/"source-snapshots.jsonl").read_text())]
    objects={"candidate":delta["assignment_additions"][0],"assignment":delta["assignment_additions"][0]["assignment"],"evidence":delta["assignment_additions"][0]["evidence_records"][0],"snapshot":snaps[0]}
    objects[target][key]="forbidden"
    (directory/"candidate-delta.json").write_bytes(dump(delta));(directory/"source-snapshots.jsonl").write_text("\n".join(json.dumps(x) for x in snaps)+"\n");refresh_batch(directory)
    assert knowledge.validate_batch("batch-001",inbox=inbox)["status"]=="BLOCKER"

@pytest.mark.parametrize("mode",["missing_snapshot","extra_snapshot","orphan_source","orphan_mushroom"])
def test_fail_closed_exact_intake_sets(tmp_path,mode):
    inbox,directory=make_batch(tmp_path);delta=json.loads((directory/"candidate-delta.json").read_text());snap=json.loads((directory/"source-snapshots.jsonl").read_text())
    if mode=="missing_snapshot": snapshots=[]
    elif mode=="extra_snapshot": snapshots=[snap,{**snap,"source_id":"unused-source","snapshot_identity":"unused-1"}]
    elif mode=="orphan_source":
        delta["source_additions"].append({**delta["source_additions"][0],"source_id":"unused-source","url":"https://example.test/unused"});snapshots=[snap]
    else:
        mushroom=json.loads((ROOT/"data/mushroom-master.json").read_text())["entries"][0]
        delta["mushroom_additions"].append({**mushroom,"mushroom_id":"unused-mushroom","canonical_name_ja":"未使用テスト種"});snapshots=[snap]
    (directory/"candidate-delta.json").write_bytes(dump(delta));(directory/"source-snapshots.jsonl").write_text("".join(json.dumps(x)+"\n" for x in snapshots));refresh_batch(directory)
    assert knowledge.validate_batch("batch-001",inbox=inbox)["status"]=="BLOCKER"

def test_inbox_and_state_root_symlinks_fail_closed(tmp_path):
    inbox,_=make_batch(tmp_path/"real"); linked=tmp_path/"inbox-link";linked.symlink_to(inbox,target_is_directory=True)
    with pytest.raises(knowledge.KnowledgeError,match="inbox root symlink"): knowledge.load_batch("batch-001",inbox=linked)
    state_real=tmp_path/"state-real";state_real.mkdir();state_link=tmp_path/"state-link";state_link.symlink_to(state_real,target_is_directory=True)
    with pytest.raises(knowledge.KnowledgeError,match="state directory symlink"): knowledge.load_review_state("batch-001",inbox=inbox,state_root=state_link)

def _use_snapshot(directory, snapshot, *, include_snapshot):
    delta=json.loads((directory/"candidate-delta.json").read_text());candidate=delta["assignment_additions"][0];e=candidate["evidence_records"][0]
    text=snapshot["full_extracted_text"];quote=text[:min(30,len(text))];digest=hashlib.sha256(text.encode()).hexdigest()
    delta["source_additions"]=[]; candidate["assignment"].update(evidence_text=quote,source_ids=[snapshot["source_id"]],evidence_refs=[e["evidence_id"]])
    e.update(source_id=snapshot["source_id"],source_url=snapshot["source_url"],evidence_text=quote,quote=quote,quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),char_start=0,char_end=len(quote),snapshot_identity=snapshot["snapshot_identity"],extracted_text_sha256=digest,text_snapshot_sha256=digest,original_response_sha256=snapshot["original_response_sha256"],snapshot_line_start=1,snapshot_line_end=1+quote.count("\n"),evidence_text_exact_substring_of_this_quote=True)
    compact={key:snapshot[key] for key in knowledge.SNAPSHOT_KEYS}
    (directory/"candidate-delta.json").write_bytes(dump(delta));(directory/"source-snapshots.jsonl").write_text(json.dumps(compact)+"\n" if include_snapshot else "");refresh_batch(directory)

def test_existing_source_without_snapshot_requires_and_promotes_snapshot(tmp_path):
    sources={r["source_id"]:r for r in json.loads((ROOT/"data/sources.json").read_text())["sources"]}
    available=knowledge._available_snapshot_ids();sid=next(s for s in sources if s not in available);source=sources[sid]
    inbox,directory=make_batch(tmp_path);snapshot=json.loads((directory/"source-snapshots.jsonl").read_text());snapshot.update(source_id=sid,source_url=source["url"]);_use_snapshot(directory,snapshot,include_snapshot=True)
    assert knowledge.validate_batch("batch-001",inbox=inbox)["status"]=="PASS"
    states=tmp_path/"state";knowledge.set_candidate_decision("batch-001","candidate-1","approved",inbox=inbox,state_root=states)
    batch=knowledge.load_batch("batch-001",inbox);state,_=knowledge.load_review_state("batch-001",inbox=inbox,state_root=states)
    assert [r["source_id"] for r in knowledge._make_package(batch,state)[2]]==[sid]

def test_baseline_snapshot_is_reused_without_input_snapshot(tmp_path):
    raw=json.loads((ROOT/"audit/phase4c9/v2/phase4c9-feature-source-snapshots-2026-10-03.jsonl").read_text().splitlines()[0])
    inbox,directory=make_batch(tmp_path);_use_snapshot(directory,raw,include_snapshot=False)
    assert knowledge.validate_batch("batch-001",inbox=inbox)["status"]=="PASS"

def test_prior_overlay_snapshot_is_reused(tmp_path):
    inbox,directory=make_batch(tmp_path/"one","batch-001");states=tmp_path/"states";knowledge.set_candidate_decision("batch-001","candidate-1","approved",inbox=inbox,state_root=states)
    root=tmp_path/"contract";knowledge._copy_contract_root(root);package=root/"audit/knowledge-batches/batch-001";knowledge.materialize_promotion_package("batch-001",package,inbox=inbox,state_root=states,base_sha=BASE,contract_root=root)
    registry=json.loads((root/"audit/feature-overlays/index.json").read_text());manifest=package/"promotion-manifest.json";registry["overlays"].append({"overlay_id":"batch-001","manifest_path":"audit/knowledge-batches/batch-001/promotion-manifest.json","manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest()});(root/"audit/feature-overlays/index.json").write_bytes(dump(registry))
    assert knowledge.validate_batch("batch-001",inbox=inbox,contract_root=root)["status"]=="BLOCKER"
    inbox2,directory2=make_batch(tmp_path/"two","batch-002");delta=json.loads((directory2/"candidate-delta.json").read_text());c=delta["assignment_additions"][0];c["candidate_id"]="candidate-2";c["assignment"]["facet_id"]="cap_sticky";c["assignment"]["review"]["decision_id"]="knowledge-decision-2";e=c["evidence_records"][0];e.update(evidence_id="knowledge-evidence-2",decision_id="knowledge-decision-2",facet_id="cap_sticky");c["assignment"]["evidence_refs"]=["knowledge-evidence-2"]
    delta["source_additions"]=[];(directory2/"candidate-delta.json").write_bytes(dump(delta));(directory2/"source-snapshots.jsonl").write_text("");refresh_batch(directory2)
    assert knowledge.validate_batch("batch-002",inbox=inbox2,contract_root=root)["status"]=="PASS"

def test_browser_state_has_all_evidence_but_no_snapshot_text(tmp_path):
    inbox,directory=make_batch(tmp_path);delta=json.loads((directory/"candidate-delta.json").read_text());c=delta["assignment_additions"][0];second={**c["evidence_records"][0],"evidence_id":"knowledge-evidence-2"};c["evidence_records"].append(second);c["assignment"]["evidence_refs"].append("knowledge-evidence-2");(directory/"candidate-delta.json").write_bytes(dump(delta));refresh_batch(directory)
    row=knowledge.scan_knowledge_batches(inbox=inbox,state_root=tmp_path/"state",origin_main_sha=BASE)[0];candidate=row["candidates"][0]
    assert len(candidate["evidence_records"])==2 and "full_extracted_text" not in json.dumps(candidate)
    assert candidate["mushroom_name"]!="kiirosuppontake" and candidate["facet_label"]!="gills"

def test_knowledge_pr_stops_when_current_head_is_not_fresh(monkeypatch):
    monkeypatch.setattr("admin.git_workflow.repository_status",lambda:{"gh_authenticated":True})
    def fake_run(args,**kwargs):
        if args[:3]==["git","status","--porcelain"]: return SimpleNamespace(stdout="",returncode=0)
        if args[:3]==["git","rev-parse","origin/main"]: return SimpleNamespace(stdout="fresh\n",returncode=0)
        if args[:3]==["git","rev-parse","HEAD"]: return SimpleNamespace(stdout="stale\n",returncode=0)
        return SimpleNamespace(stdout="",returncode=0)
    monkeypatch.setattr("admin.git_workflow.run",fake_run)
    with pytest.raises(GitWorkflowError,match="fresh origin/main"): create_knowledge_pull_request("batch-001")
