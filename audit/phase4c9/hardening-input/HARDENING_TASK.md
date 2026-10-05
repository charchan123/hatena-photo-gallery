# Phase 4C.9 Incremental Overlay Contract Hardening

Read this file after verifying the bundled gzip artifact in this directory.

Goal: recover the exact previous overlay contract, then harden only the known defects. Do not re-research biology. Do not implement Admin Console v2. Do not push, create a PR, merge, deploy, write gh-pages, or dispatch workflows.

Immutable baseline must remain unchanged:
- 373 approved assignments
- 10 held assignments
- 377 approved evidence
- 10 held evidence
- 1 retired evidence
- 130 snapshots
- 20 facets
- 4 groups
- TRUSTED_FEATURE_V2_MANIFEST_SHA256 and _V2_FILES unchanged
- audit/phase4c9/v2/* unchanged
- data/mushroom-master.json, data/sources.json, data/feature-facets.json unchanged
- IA-029 ring absent
- no v2 to v1 fallback

Bundled artifact:
audit/phase4c9/hardening-input/phase4c9-incremental-overlay-contract.patch.gz

Expected gzip:
- bytes 9655
- SHA-256 a2c91405593e8abba37875fdf1b311f88b856a9391e8998c8eba25e45caaa3dc

Decompressed patch expected:
- bytes 41907
- lines 678
- SHA-256 899ecf8229cb774346b31c2649e8ba75ba649b7d5195cf9af8a31235efc06eaa
- changed files exactly: HANDOFF.md, audit/feature-overlays/index.json, feature_overlay.py, feature_ui.py, main.py, tests/test_feature_overlay.py

Baseline target tree:
02b778ab6fad5dd6cbaed3c897c25c01328ee305
Expected baseline tests: 501 passed / 501 collected.

Recover the patch with git apply only after identity verification. Before hardening edits, regenerate the binary diff from the normalized baseline and verify it exactly matches the expected patch SHA/bytes/lines and six-file list. Commit that exact recovery as:
Recover Phase 4C.9 incremental overlay contract

Then harden the following defects only:

1. Production integration: actual overlay-expanded data/feature-facets.json must NOT be passed through the legacy 373-fixed baseline validator before overlay validation. Correct flow: confirm v2 -> validate_feature_production_state() -> immutable baseline validation inside it -> overlay registry/package validation -> expected runtime reconstruction -> exact compare to actual production -> render validated runtime. Do not weaken validate_feature_facets(... mode="production").

2. Remove any public boolean bypass such as production_state_validated=True. Prefer a private render/write helper shared by the existing baseline-validated path and the overlay-production-state-validated path.

3. Overlay assignment schema:
- assignment dict
- facet_id non-empty string and existing facet
- evidence_text non-empty string
- source_ids non-empty unique non-empty strings
- evidence_refs non-empty unique non-empty strings
- evidence_kind only source_quote or source_supported_paraphrase
- qualifiers list of unique non-empty strings
- review dict
- review.decision_id non-empty string
- review.human_approval must be null/None
- set(source_ids) must equal evidence source-id set

4. Evidence/provenance:
- exact-substring flag boolean
- exact == (evidence_text in quote)
- paraphrase may validly have exact=false
- char_start/end int but not bool
- 0 <= start <= end <= len(text)
- text[start:end] == quote
- quote SHA-256 exact
- computed snapshot line range must match stored line range
- snapshot_identity non-empty
- original_response_sha256 is 64 lowercase hex
- extracted_text_sha256 and text_snapshot_sha256 equal actual UTF-8 text hash
- record-side snapshot metadata equals snapshot-side metadata
- no web refetch

5. Decision manifest strict root keys only: schema_version, overlay_id, reviewed_at, decisions. Reject unknown root keys. Decision rows require non-empty candidate_id, mushroom_id, facet_id, decision_id, human_decision, review_result; note optional string. human_decision only approved/held/pending. Promoted candidate must be approved AND supports_facet. New decision_id must not collide with baseline approved, baseline held, prior overlay, or same-overlay decision IDs.

6. Path/symlink: package directory audit/knowledge-batches/<overlay-id>/ itself must resolve beneath fixed repo audit/knowledge-batches root. Reject absolute path, .., manifest symlink escape, package directory symlink outside repo, ancestor symlink escape, artifact ancestor symlink escape.

7. Overlay source-snapshots.jsonl may contain only snapshots actually referenced by approved evidence in that overlay. Reject unused/orphan overlay snapshots.

Extend tests/test_feature_overlay.py without deleting or weakening existing tests. At minimum cover:
- synthetic real overlay production integration without legacy 373-first failure
- empty overlay model/output equivalence
- empty evidence_text fail
- empty source_ids fail
- duplicate source_ids fail
- source/evidence set mismatch fail
- duplicate evidence_refs fail
- invalid evidence_kind fail
- qualifiers non-list/empty/duplicate fail
- review missing fail
- decision_id missing/empty fail
- non-null review.human_approval fail
- paraphrase + exact=false valid
- exact mismatch fail
- negative/bool char_start fail
- end beyond text fail
- wrong snapshot line start/end fail
- invalid original_response_sha256 fail
- empty snapshot_identity fail
- baseline decision_id collision fail
- unknown decision-manifest root field fail
- invalid promoted review_result fail
- manifest symlink escape fail
- package directory symlink escape fail
- artifact ancestor symlink escape fail
- unused overlay snapshot fail
- baseline still exactly 373/377/130
- IA-029 ring blocked
- empty registry pass
- valid approved overlay pass
- held/pending not promoted

Final validation:
- python -m pytest -q
- python -m pytest --collect-only -q
- python -m compileall -q .
- focused feature/admin tests
- JS syntax/regressions if available
- git diff --check NORMALIZED_BASE_SHA..HEAD

Allowed final changed files should remain limited to:
HANDOFF.md
audit/feature-overlays/index.json
feature_overlay.py
feature_ui.py
main.py
tests/test_feature_overlay.py

Do not include assets/aiuo.css, tests/test_aiuo_ui.py, production biology JSON, audit/phase4c9/v2/*, or .github/workflows/generate.yml in the final transfer diff.

After all tests pass, local commit:
Harden Phase 4C.9 incremental overlay contract

Generate final transfer patch from NORMALIZED_BASE_SHA..HEAD, deterministic gzip mtime=0, and complete Base64 output. End by stating immutable baseline unchanged, production biology data unchanged, original checkout unchanged, and no push/PR/merge/deploy.
