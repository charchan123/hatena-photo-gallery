# Mobile optimization recovery — 2026-10-09

Status: CHECKPOINT; not ready for production or merge.

Starting main: `255b3f693a1af966286cbda2597b8842614fa1bf`
Starting tree: `3908dbc27c6027324395560f1e095f094f1bbc15`
Branch: `mobile-optimization-recovery-2026-10-09`

Recovery: git status, branches, reflog, all-ref log, stash, /workspace and /tmp searches found no prior mobile implementation or evidence. Earlier conversation findings guide reconstruction; earlier PASS results are not current-run evidence.

Reconstructed: mobile new-top 12px white strip / brightness 1.06; 98px guide cards; 18px independent-card gap; guide camera artwork; EXIF explanatory wording; kana 5-column layout; detail breadcrumb hidden and GOJUON 5x2; Best Shots year title wrapping; About links; coarse touch poisonous-card 600ms deferred native activation. Toxicity eligibility and PC spore presets unchanged.

Current checkpoint checks: 56 focused Python tests PASS; 10 poison JS tests PASS. Actual generator build: 321 HTML pages from 923 production observations / 302 subjects. No current-run visual PASS is claimed yet.

Public Hatena parent source still has height=0px, forced offsetHeight, then real height. Focused browser reproduction and replacement candidate validation remain pending.

PARENT_HATENA_PATCH_REQUIRED: YES. No Hatena production save is permitted.

Remaining: browser root reproduction; parent candidate; visual 34-case matrix; scroll/touch interactions; full regression suite; final review evidence; Draft PR.

Slim baseline and protected knowledge paths remain unchanged. No merge, deploy, auto-merge, or workflow_dispatch.

## Continuation checkpoint

Resumed exactly at `ed1aca8ab3f642941452bc7be846f81c3486e1d4`, tree `6104552d18f8d86e43e8b0f2ffa74c281cc15252`; main unchanged. Existing UI code and 34-case layout / 10-case computed-style / poison / MENU evidence were recovered locally, not reconstructed.

Focused navigation diagnosis: 4/4 mobile trials delivered `scrollToTitle` with correct origin but null source after child navigation. The parent rejected it and made zero scrollTo calls. The draft load retry could not fix a request that was never accepted.

Fix: same-frame internal HTML links record a destination pathname and timestamp in sessionStorage; destination pageshow consumes this once and sends from the live iframe. Parent preserves exact source/origin validation and uses instant positioning only for explicit navigation; no setHeight/load scrolling. Storage denial is fail-open for native navigation, but replay becomes best effort. No toxin/biology eligibility change.

Checkpoint tests: parent 3, navigation 5, poison 10, all JS total 23 PASS. Final five-width navigation/in-place checks and final report are pending. No PR yet.
