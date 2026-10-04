# Codex Cloud Task — Phase 4C.9 Feature Facet v2 validator

## Goal

Implement the Phase 4C.9 Option B feature-facet v2 validation path, evidence/provenance validation, coverage validation, trusted approval-manifest pin, negative tests, and qualifier propagation to the feature-search model/UI.

This is an implementation task, **not a new mushroom/source research task**.

Do not merge to `main`, do not deploy, and do not perform the final production-data cutover.

## Starting point

Repository:

`charchan123/hatena-photo-gallery`

Start from the current branch:

`phase4c9-v2-input-package`

This branch is based directly on:

`phase4c9-141-knowledge-expansion`

parent SHA:

`cf1bb3f39ffb6b2fd2adf9bab1cae60436ff9195`

The input-package commit was created only to make the audited artifacts available to Codex Cloud. Do not bring unrelated Phase 4C.10 / Phase 4C.11 design work into this task.

Create a dedicated implementation branch from the current input-package HEAD, for example:

`phase4c9-v2-validator-implementation`

Do not work directly on `main`.

## Step 1 — mandatory reconstruction/hash gate

Before changing any implementation file, run:

```bash
audit/phase4c9/v2-input/reconstruct.sh
```

This must reconstruct all 11 logical artifacts under:

`/tmp/phase4c9-v2-input`

and `sha256sum -c` must print **OK for all 11 files**.

If any artifact is missing or any SHA-256 mismatches:

- STOP.
- Do not reformat, reserialize, normalize, repair, redownload, or substitute the file.
- Report the missing/mismatching filename, expected hash, and actual hash.

The exact hashes are in:

`audit/phase4c9/v2-input/SHA256SUMS.txt`

Do not use Web search or network re-fetches to replace these artifacts.

## Step 2 — read the implementation sources

After the 11-hash gate passes, read all reconstructed artifacts, especially:

- `feature-facets-runtime-candidate-2026-10-03.json`
- `phase4c9-feature-facet-reconciliation-decisions-2026-10-03.json`
- `phase4c9-feature-facet-reconciliation-report-2026-10-03.md`
- `phase4c9-feature-facet-validator-plan-2026-10-03.md`
- `phase4c9-feature-source-snapshots-2026-10-03.jsonl`
- `phase4c9-feature-evidence-ledger-approved-2026-10-03.json`
- `phase4c9-feature-approval-manifest-2026-10-03.json`
- `phase4c9-feature-v2-implementation-package-summary-2026-10-03.md`

Also read:

- `HANDOFF.md`
- `feature_ui.py`
- all feature-facet tests
- every repository call site of `validate_feature_facets`, `build_feature_search_model`, `render_feature_page`, and `generate_feature_page`.

Do not assume the validator-plan pseudocode is copy/paste-ready. Implement it according to the existing repository architecture.

## Fixed audited boundary — do not change

The following boundary is already audited and approved:

- original assignments: 383
- approved runtime assignments: 373
- held assignments: 10
- approved supporting evidence records: 377
- held evidence records: 10
- retired non-supporting citation: 1
- total historical evidence records: 388
- eligible species: 139
- included species: 127
- explicitly uncovered/excluded species: 12
- groups: 4
- active facets: 20
- cited source snapshots: 130 / 130
- approved provenance model: Option B

Required identities:

`373 + 10 = 383`

`377 + 10 + 1 = 388`

`127 + 12 = 139`

IA-029 / タマゴタケモドキ:

- `ring` is **NOT APPROVED**
- do not add it
- preserve only the already approved four facet assignments

Do not infer or add facets for the 12 uncovered species.

Do not reactivate any of the 10 held assignments.

## Approval model

Historical candidate fields such as:

`human_approval: null`

must remain historical facts. Do not rewrite them to `true`.

Approval is external and hash-scoped through:

`phase4c9-feature-approval-manifest-2026-10-03.json`

Trusted manifest SHA-256:

`2d6f21f31d7e0e33a513c02a5188f563baa4a8e8bbe1f40866501c3780521d05`

Production validation must pin this hash from a repository-owned trust boundary/config/constant that candidate-controlled data cannot rewrite.

Do not accept arbitrary `approved: true` or an unpinned manifest as authorization.

## v1 compatibility is mandatory

Preserve the existing version-1 validator contract.

Existing two-argument calls:

`validate_feature_facets(feature_data, mushroom_master)`

must continue to work for version 1.

Do not weaken v1 checks to make v2 data pass.

Preserve v1 behavior including its exact-substring/source-set/coverage contract and existing negative tests.

Reject:

- bool masquerading as integer version
- unknown versions
- implicit downgrade
- v2 failure followed by permissive v1 retry

## v2 dispatcher

Implement a dedicated v2 path broadly consistent with the reviewed validator plan.

Expected API shape:

```python
validate_feature_facets(
    feature_data,
    mushroom_master,
    *,
    sources=None,
    evidence_ledger=None,
    source_snapshots=None,
    approval_manifest=None,
    mode="production",
)
```

For version 2:

- sources required
- evidence ledger required
- source snapshots required
- production mode requires approval manifest and trusted manifest pin
- only `production` and `review` modes are valid

Review-mode success must never be treated as production-mode success.

## v2 structural validation

At minimum validate:

- root/groups/facets/entries/assignments types
- non-empty string IDs
- whitespace-only IDs rejected
- duplicate IDs rejected
- group/facet/master/source references exist
- duplicate facet assignment within one mushroom rejected
- all 20 active facets remain used
- reader-facing master feature summary remains non-empty for eligible coverage
- `evidence_text` non-empty
- `source_ids` non-empty and unique
- `evidence_refs` non-empty and unique
- each evidence ref binds to the same mushroom/facet
- each evidence source is one of the assignment source IDs
- assignment source set equals the active approved evidence source set

Do **not** require v2 assignment source IDs to equal `master.features.source_ids`.

## Snapshot / quote / offset validation

No runtime Web requests.

Use only the fixed 130 UTF-8 extracted-text snapshots.

Validate the full chain:

source ID
→ snapshot identity
→ extracted/full-text hash
→ quote
→ Unicode char offsets
→ LF-based line range
→ quote hash
→ evidence ID
→ decision ID
→ mushroom ID
→ facet ID
→ runtime assignment

Rules:

- file hashes = exact file bytes, including final LF
- text hashes = raw UTF-8 text bytes, no normalization
- quote hashes = raw UTF-8 quote bytes, no strip/normalization/newline rewriting
- `char_start` is 0-based
- `char_end` is exclusive
- offsets are Unicode code points, not UTF-8 byte offsets or JS UTF-16 code units
- line numbers are 1-based
- count LF as newline; do not silently treat form-feed as newline

## Original-response hash limitation

Only 4/130 original HTTP/PDF response hashes can be recomputed from retained raw bytes.

The remaining 126 are inherited historical values.

Do not claim those 126 were recomputed from original response bytes.

Do not make raw-response reproducibility a new gate that blocks the already approved fixed-extracted-text model.

The production evidence gate for this phase is the fixed extracted text + quote/hash/offset + reviewed/approved provenance.

## evidence_kind semantics

Allowed:

- `source_quote`
- `source_supported_paraphrase`

For `source_supported_paraphrase`, `evidence_text` does not need to be an exact substring of the quote.

Do not attempt to infer semantic support merely from keywords.

Trust only the fixed reviewed assignment/evidence/digest relationship after all hashes and bindings validate.

For `source_quote`, enforce the approved exact-quote relationship as specified by the ledger.

Respect `evidence_text_exact_substring_of_this_quote` per evidence record.

## Active / held / retired separation

`held_decisions` and `retired_citations` are history-only.

They cannot resolve active runtime `evidence_refs`.

Runtime evidence must be approved `supports_facet` evidence.

Reject non-supporting, insufficient, held, retired, unresolved-conflict, or unknown evidence as active runtime support.

## Coverage validation

Recompute what can be recomputed.

- eligible = master IDs with non-empty reader-facing feature summary (expected 139)
- included = entry IDs with at least one active approved assignment (expected 127)
- excluded = the explicitly recorded 12 eligible IDs with reason/status

Require:

`eligible == included | excluded`

`included & excluded == empty`

`excluded <= eligible`

Do not count empty entries as included.

Also validate the original assignment boundary:

383 original = 373 approved + 10 held

with ID-set integrity, not only counts.

## Runtime assignment digest

Recompute all 373 approved runtime-assignment digests using the serialization contract recorded in the approved artifacts:

- UTF-8 JSON
- `ensure_ascii=false`
- `sort_keys=true`
- separators `(",", ":")`
- no trailing newline

A candidate mutation such as evidence-text change, source swap, qualifier removal, evidence-ref change, or review mutation must invalidate the approved digest.

## Qualifiers must survive into model/UI

Do not stop after validator implementation.

Inspect and update, as needed:

- `build_feature_search_model`
- `render_feature_page`
- `generate_feature_page`

Preserve existing explicit `subject.mushroom_master_id` joins and AND filtering.

Do not add fuzzy/name-based join fallback.

Pass sufficient evidence detail so reader-facing condition/qualifier information is not lost, including representative cases for:

- wet-condition stickiness
- growth-stage / maturity changes
- deciduous/transient structures
- ring mobility/traces where approved
- volva morphology limitations (not always a complete bag-like volva)
- annular/collar/incomplete/fragmentary forms
- staining body part
- injury/staining trigger
- staining strength / subsequent color change
- solid→hollow developmental differences
- cases where multiple listed states are not guaranteed simultaneously in one specimen

Preserve the existing warning that features alone should not be used to identify a mushroom.

Do not expose internal hashes in normal UI unless required for an explicit evidence-detail view.

## Production generation gate

For v2 data, page generation must require successful production validation before rendering.

If required v2 inputs are absent or the trusted manifest pin does not match, stop generation.

Do not catch validator failure and continue with unvalidated v2 data.

Search all call sites and update them consistently.

### Important cutover boundary

Do **not** perform the final production-data cutover in this task.

Do not silently replace the current live production facet file with the 373-assignment v2 candidate merely to make tests pass.

If the current Phase 4C.9 branch contains an expanded version-1 facet file that cannot satisfy the preserved v1 contract, do not weaken v1 and do not mutate the audited v2 candidate.

Choose the smallest reversible implementation-only treatment that keeps production behavior explicit (for example isolating the v2 candidate and/or restoring the last valid v1 production facet for this implementation branch), document the exact choice in HANDOFF, and stop if a safe non-cutover treatment is not possible.

## Required negative/regression tests

Keep all existing tests.

Add focused tests for at least:

### v1 regression
- valid v1 PASS
- v1 summary mismatch FAIL
- v1 source-set mismatch FAIL
- v1 not weakened

### v2 success
- approved independent evidence absent from master summary PASS
- directly supported source set different from master feature source set PASS
- exact approved package production validation PASS
- correct review-mode validation PASS

### v2 structure failures
- unknown source
- empty source IDs
- duplicate source
- extra unsupported source
- duplicate facet assignment
- unknown facet
- unknown mushroom
- empty entry
- unused active facet
- bool version
- unknown version

### evidence failures
- evidence ref from another mushroom
- evidence ref from another facet
- quote mutation
- quote-hash mutation
- char-start mutation
- char-end mutation
- line-number mutation
- snapshot-text-hash mutation
- missing snapshot
- snapshot-identity swap
- source-ID swap
- evidence-text-only semantic mutation / approved digest mismatch
- source_quote/paraphrase type mutation
- non-supporting evidence promoted to active
- held evidence promoted to active
- retired citation promoted to active

### approval failures
- production without manifest
- manifest bytes/hash mismatch
- trusted manifest pin mismatch
- candidate self-sets approved=true
- approved assignment digest mismatch
- candidate hash mismatch
- ledger hash mismatch
- snapshot-bundle hash mismatch
- master hash mismatch
- sources hash mismatch

### coverage failures
- excluded reason removed
- one excluded ID removed
- included/excluded overlap
- eligible omission
- 383 != 373 + 10
- held assignment in runtime
- inferred assignment added to an uncovered species

### IA-029
- adding ring to タマゴタケモドキ must FAIL
- approved existing four facets remain intact

### UI contract
Representative tests must prove that wet-condition, growth-stage, transient/deciduous, volva-shape limitation, and staining-condition qualifiers survive model → render.

## Baseline and final validation

Before implementation, run and record:

```bash
python -m pytest -q
python -m pytest --collect-only -q
python -m compileall -q .
```

Run existing JS syntax/tests too where applicable.

The Phase 4C.9 starting branch may have a known feature-facet repository validation failure from the old v1-expanded candidate. Do not hide it; identify it precisely before changing code.

After implementation run:

- full pytest
- collect-only
- compileall
- all feature tests
- all v1 regression tests
- all v2 positive/negative tests
- approved-package production validation
- qualifier render tests
- existing JS regression/syntax checks
- `git diff --check`

If useful, a temporary CI workflow may be used, but remove temporary workflow files before opening the PR.

## Expected production-mode validation result

Using the exact approved package, the new v2 validator in `mode="production"` must pass with:

- approved assignments: 373
- held: 10
- included: 127
- excluded: 12
- eligible: 139
- active facets: 20
- groups: 4
- source snapshots: 130

This means only:

`READY_FOR_PRODUCTION_CUTOVER`

It does **not** authorize or perform the cutover.

## Repository/audit package handling before PR

The `audit/phase4c9/v2-input/` package exists only to feed Codex Cloud.

Do not merge this temporary package to `main`.

Before opening the implementation PR, decide which audited artifacts are actually required as durable runtime/review inputs by the implemented design.

- Keep only artifacts that the validator/runtime genuinely needs, in intentional repository paths.
- Remove the temporary transfer-only split parts and transfer README/script from the implementation branch before PR.
- Never regenerate or reserialize a kept audited artifact; preserve exact bytes/hash.
- Do not silently discard provenance artifacts that production validation requires.

Document the final artifact layout in HANDOFF.

## HANDOFF.md

Update HANDOFF.md with:

- starting SHA and branch
- exact 11-input hash-gate result
- v1 compatibility
- v2 validator architecture
- trusted manifest pin
- durable artifact locations
- 373 / 10 / 12
- 377 / 10 / 1
- 130 snapshots
- raw-response limitation: 4 recomputed / 126 inherited only
- IA-029 ring remains unapproved
- qualifier UI behavior
- production-mode validation result
- all tests
- production cutover not performed
- main merge not performed

## PR

When all implementation tests pass, push the implementation branch and open a PR.

Do not auto-merge.

Prefer a PR whose final tree does **not** contain the transfer-only `parts/` package.

PR body must state:

- Phase 4C.9 Feature Facet v2 validator
- Option B
- v1 unchanged
- trusted manifest pin
- exact artifact hash verification
- 373 approved / 10 held
- 127 included / 12 excluded
- 130/130 snapshots
- qualifier preservation
- negative tests
- IA-029 ring not added
- no inferred assignments for uncovered 12
- production cutover NOT performed
- merge NOT performed

If PR base choice is ambiguous because the Phase 4C.9 data branch is not yet merged to main, prefer the base that produces the smallest truthful Phase 4C.9 implementation diff and clearly report the chosen base. Do not merge anything merely to simplify PR history.

## Prohibited

Do not:

- search the Web for new mushroom facts
- refetch sources
- OCR/reprocess PDFs
- make new taxonomy/mycology judgments
- change the 373 approved assignments
- accept the 10 held assignments
- add IA-029 ring
- infer facets for the uncovered 12
- rewrite master/sources to satisfy validation
- re-point source IDs
- redefine expected hashes
- reserialize audited JSON merely to update hashes
- fake historical approval
- permit candidate self-approval
- weaken v1
- fallback after failed validation
- mix unrelated design work
- merge to main
- deploy
- auto-merge a PR

If an ambiguity requires changing the audited biological/provenance boundary, STOP and report a BLOCKER instead of guessing.

## Final report format

Report:

### Status

### Starting SHA

### Implementation Branch

### Input Hash Gate
- 11/11 result

### Baseline
- pytest
- collected
- compile
- JS

### v1 Compatibility
- unchanged YES/NO

### v2 Validator
- dispatcher
- structure
- evidence
- coverage
- manifest
- trusted pin

### Approved Package
- 373 approved
- 10 held
- 377 evidence
- 130 snapshots
- 127 included
- 12 excluded
- 139 eligible

### Qualifier UI
- representative preserved conditions

### IA-029
- ring absent PASS/FAIL

### Negative Tests
- count and result

### Production-mode Validation
- PASS/FAIL
- trusted manifest SHA
- READY_FOR_PRODUCTION_CUTOVER YES/NO
- cutover performed MUST BE NO

### Regression Tests
- full results

### Files Changed

### Durable Audit Artifact Layout

### HANDOFF
- updated YES/NO

### PR
- number / URL
- base
- mergeable state
- merged MUST BE NO

### Remaining
- production cutover
- main merge
- live deployment
