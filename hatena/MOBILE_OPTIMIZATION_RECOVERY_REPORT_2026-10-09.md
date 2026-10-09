# Mobile UX and Hatena iframe interaction recovery — 2026-10-09

Status: PASS for review; not deployed. **PARENT_HATENA_PATCH_REQUIRED: YES.**

## Recovery and boundaries

- Main: `255b3f693a1af966286cbda2597b8842614fa1bf`, tree `3908dbc27c6027324395560f1e095f094f1bbc15` (PR #95).
- This continuation started exactly at checkpoint `ed1aca8ab3f642941452bc7be846f81c3486e1d4`, tree `6104552d18f8d86e43e8b0f2ffa74c281cc15252`.
- Branch: `mobile-optimization-recovery-2026-10-09`; no new implementation branch, no reset to main.
- Earlier checkpoint `e280b7009ca9a2c5aa57000969ab67aa075545a6` contains the recovered UI implementation. `ed1aca8a` adds the parent candidate and tests. Navigation fix checkpoint: `8622db82dd8c2111bb46245658ec7dd06569a5d4`.
- Local browser evidence and downloaded input documents survived this continuation and were reused. The 34 layout cases and 10 desktop/tablet computed-style comparisons were not needlessly rerun; their UI/CSS is unchanged by the final navigation-only correction.
- The initial lost-run claims remain distinct from retained measured evidence. The previous 44-case scroll result was known; its intermediate rerun file was incomplete. Final validation below supersedes it with 45 in-place cases and 15 actual navigations.
- A detached main reference was used only for comparison builds. All implementation remained on the checkpoint branch.

## UI implementation retained

| Item | Result |
|---|---|
| Mobile new-top Hero | 12px white strip; existing Amanita overlaps it; brightness 1.06; no replacement image |
| Three guide cards | All 98px high on mobile (was 82px) |
| Research / Best Shots spacing | 18px mobile gap |
| Guide Best Shots artwork | `new-top-best-shots-camera-mushrooms.webp` |
| Season explanation | User-supplied EXIF / actual observation / regional variability wording; grouping unchanged |
| Kana filters | All button on its own row, five kana on the second row at 360/390/430px |
| Detail | Breadcrumb hidden only on mobile; back link kept; GOJUON fixed 5×2 |
| Best Shots year Hero | 360/390/430px PASS: no isolated last character, description inside Hero |
| About self | `https://exsudoporus-ruber.hatenablog.jp/entry/2025/03/22/032440` |
| About daily | Existing 日常の記録 archive URL unchanged |
| About links | `https://exsudoporus-ruber.hatenablog.jp/entry/links` |
| About target | `_top` retained |

Full Hatena CSS: `hatena/hatena-design-css-mobile-optimized-2026-10-09.css`.
1215 lines; 35442 bytes; SHA-256 `4298621f4f6f85c11ac0f7496b452e5774e2664501f416af23069d0e1b907842`.
The Slim baseline and its system-section bytes remain intact; Phase 4C.11 article rule section is byte-identical.

## Root cause: in-place height synchronization

Captured public Hatena footer explicitly assigns height 0px, reads offsetHeight, then assigns real height. A real feature click at parent scrollY 350 reproduced 350 → 0, with setHeight messages and no scrollToTitle (`root-cause.json`).

The candidate assigns actual height directly. When content shrinks near the document bottom, the wrapper reserves just enough minimum height to prevent browser scroll clamping; iframe height is never inflated. This intentionally can leave blank space below the frame until upward scrolling/growth/navigation reclaims it. No scrollTo is called by height updates, filters or details.

## Root cause: navigation messages from destroyed documents

Four focused mobile repetitions delivered scrollToTitle from the expected origin **with event.source === null**. The strict handler rejected these; there were zero scrollTo calls. See `navigation-diagnosis-before.json` (honestly labeled summary of the instrumented console observations, not reconstructed raw scroll samples).

Thus smooth-scroll cancellation was a hypothesis, not the demonstrated primary cause of those failures. Retrying on load could not recover a message never accepted. Origin/source validation was not weakened.

Final strategy:

1. An actual same-frame, same-origin HTML link records destination pathname and time in sessionStorage, without preventing or delaying native navigation. Downloads, other targets, external links, top-level pages and prevented/modified clicks are excluded.
2. Destination pageshow consumes the marker once, only if pathname matches and age is 0–10 seconds, then sends scrollToTitle from its live window. Filters/search/details create no marker.
3. The parent still requires exact iframe contentWindow and exact origin; null sources remain rejected. Explicit navigation uses `behavior: instant`, avoiding an animated-scroll/load race. setHeight and load do not request scrolling. No new retry timer or retry loop is used.
4. The existing history traversal path, requestHeight and lgClosed behavior remain. Native navigation still works if storage is unavailable, but reliable destination replay cannot be guaranteed in that privacy configuration.

`navigation-timeline.json` records child send times, parent receipt, source identity, iframe load, navigation request, height messages and scrollY. Fixed repeated navigation: 4/4 PASS (`navigation-diagnosis.json`).

## Final navigation results

Chromium 153; widths 360/390/430 touch emulation and 768/1440 desktop input; viewport height 900. Real generated pages within the captured Hatena DOM, with only candidate CSS/parent script injected. Production not edited. Subpixel CSS target is rounded by browser scrollY; tolerance 1px.

| Width | Navigation | Final scrollY | Target | Delta |
|---|---|---:|---:|---:|
| 360 | card → detail | 301 | 301.2969 | -0.2969 |
| 360 | detail → GOJUON | 301 | 301.2969 | -0.2969 |
| 360 | back link | 301 | 301.2969 | -0.2969 |
| 390 | card → detail | 301 | 301.2969 | -0.2969 |
| 390 | detail → GOJUON | 301 | 301.2969 | -0.2969 |
| 390 | back link | 301 | 301.2969 | -0.2969 |
| 430 | card → detail | 301 | 301.2969 | -0.2969 |
| 430 | detail → GOJUON | 301 | 301.2969 | -0.2969 |
| 430 | back link | 301 | 301.2969 | -0.2969 |
| 768 | card → detail | 272 | 272.0000 | 0.0000 |
| 768 | detail → GOJUON | 272 | 272.0000 | 0.0000 |
| 768 | back link | 272 | 272.0000 | 0.0000 |
| 1440 | card → detail | 266 | 266.0000 | 0.0000 |
| 1440 | detail → GOJUON | 266 | 266.0000 | 0.0000 |
| 1440 | back link | 266 | 266.0000 | 0.0000 |

15/15 PASS. Card → detail used a poisonous card, so the real 600ms activation path is also exercised within the parent frame. No forced scrolling was introduced for in-place updates.

## Final in-place results

Each case records before/after, messages, actual parent scrollTo-call count (zero), and parent/child overflow. 45/45 PASS, every delta exactly 0px, no scrollToTitle messages. Bottom-edge close PASS at all five widths. Programmatic summary activation is used only for the explicit bottom-edge case to avoid browser automation scrolling the clicked element into view.

| Width | Action | Before → after scrollY |
|---|---|---:|
| 360 | feature ON | 301 → 301 |
| 360 | feature OFF | 301 → 301 |
| 360 | feature clear | 1158 → 1158 |
| 360 | details open | 1158 → 1158 |
| 360 | details close | 1158 → 1158 |
| 360 | bottom-edge close | 1848 → 1848 |
| 360 | season tab | 235 → 235 |
| 360 | kana filter | 235 → 235 |
| 360 | kana search | 235 → 235 |
| 390 | feature ON | 301 → 301 |
| 390 | feature OFF | 301 → 301 |
| 390 | feature clear | 1113 → 1113 |
| 390 | details open | 1113 → 1113 |
| 390 | details close | 1113 → 1113 |
| 390 | bottom-edge close | 1814 → 1814 |
| 390 | season tab | 235 → 235 |
| 390 | kana filter | 235 → 235 |
| 390 | kana search | 235 → 235 |
| 430 | feature ON | 301 → 301 |
| 430 | feature OFF | 301 → 301 |
| 430 | feature clear | 1113 → 1113 |
| 430 | details open | 1113 → 1113 |
| 430 | details close | 1113 → 1113 |
| 430 | bottom-edge close | 1803 → 1803 |
| 430 | season tab | 213 → 213 |
| 430 | kana filter | 213 → 213 |
| 430 | kana search | 213 → 213 |
| 768 | feature ON | 272 → 272 |
| 768 | feature OFF | 272 → 272 |
| 768 | feature clear | 835 → 835 |
| 768 | details open | 835 → 835 |
| 768 | details close | 835 → 835 |
| 768 | bottom-edge close | 1541 → 1541 |
| 768 | season tab | 230 → 230 |
| 768 | kana filter | 230 → 230 |
| 768 | kana search | 230 → 230 |
| 1440 | feature ON | 266 → 266 |
| 1440 | feature OFF | 266 → 266 |
| 1440 | feature clear | 740 → 740 |
| 1440 | details open | 740 → 740 |
| 1440 | details close | 740 → 740 |
| 1440 | bottom-edge close | 1430 → 1430 |
| 1440 | season tab | 245 → 245 |
| 1440 | kana filter | 245 → 245 |
| 1440 | kana search | 245 → 245 |

## Poison interaction

| Mode | Delay to navigation request | Navigation requests | Result |
|---|---:|---:|---|
| Poison touch | 603ms | 1 | PASS |
| Double tap | 603ms | 1 | PASS |
| Non-poison | 8ms | 1 | PASS |
| Reduced motion | 5ms | 1 | PASS |
| Keyboard | 5ms | 1 | PASS |
| PC hover | No navigation | 0 | 10 particles, one burst |

The timing harness observes then aborts outgoing navigation requests to count them; the separate parent-frame tests above complete the real navigations. PR #94 presets, curved motion, active burst cap, cleanup, toxicity attribute eligibility and renderer logic are unchanged. A photo-loaded touch screenshot separately confirms the visible effect.

## Visual and functional evidence

- Retained 34-case matrix: eight real page types × 360/390/430/1440, plus new-top/article at 768; no horizontal overflow.
- New final interaction checks: parent and child overflow NONE at 360/390/430/768/1440.
- Retained 10 computed-style comparisons: eight desktop page types + new-top/article tablet. Measured layout, typography, filter, clip-path, spacing and geometry agree with baseline; intentionally changed guide artwork and requested text are not claimed identical.
- Article comparisons use the full candidate CSS, not the old publicly deployed article style. The article section is unchanged from PR #95.
- MENU open/close and PAGE TOP: 360/390/430/768 PASS. The harness waits for jQuery's actual slide duration; the earlier 300ms wait was insufficient.
- Native Star/social/comment/sidebar DOM remains present (82 combined matched nodes on the sampled article); no authenticated Star click, comment submission or third-party account operation was performed. Physical Android/iOS verification remains a manual review step; tests use Chromium touch emulation.
- Representative screenshots and the browser harness are supplied as a separate review bundle; bulky media is not committed.

## Final automated checks

| Check | Result |
|---|---|
| python -m pytest -q | 600 passed |
| python -m pytest --collect-only -q | 600 collected |
| Focused Python | 70 passed (included in full suite) |
| Parent iframe JS | 3 passed |
| Poison JS | 10 passed |
| Navigation replay JS | 5 passed |
| Other JS | 5 passed; total 23 |
| JS syntax | gallery.js / poison-spores.js PASS |
| compileall | PASS |
| CSS parser | Seven files, nested media/declaration parsing, no errors |
| Real generator build | 321 HTML; 923 observations / 302 subjects |
| git diff --check | PASS; whole-PR check permits original system-section CRLF via cr-at-eol |
| Protected paths | No differences from starting main |

## Required manual Hatena step

**PARENT_HATENA_PATCH_REQUIRED: YES.** This PR does not update Hatena production. Use `HATENA_IFRAME_SCROLL_FIX_2026-10-09.md` and replace only the complete communication script with `hatena-footer-iframe-handler-candidate-2026-10-09.html` after separate owner review/authorization. Install the paired gallery.js change for reliable destination replay. The new full Design CSS is also a review artifact; keep a backup and Preview before any later authorized save.

No biology, provenance, facet assignments, source data, toxicity classification, audit baseline, feature overlay, Admin Console or workflows changed. No main push, merge, deploy, auto-merge or workflow_dispatch was performed.

## Changed files relative to starting main

- `assets/aiuo.css`
- `assets/best-shots.css`
- `assets/detail.css`
- `assets/gallery.js`
- `assets/guide.css`
- `assets/poison-spores.js`
- `assets/portal.css`
- `best_shot_ui.py`
- `hatena/HATENA_IFRAME_SCROLL_FIX_2026-10-09.md`
- `hatena/MOBILE_OPTIMIZATION_RECOVERY_REPORT_2026-10-09.md`
- `hatena/hatena-design-css-mobile-optimized-2026-10-09.css`
- `hatena/hatena-footer-iframe-handler-candidate-2026-10-09.html`
- `hatena/mobile-review-2026-10-09/build-baseline.json`
- `hatena/mobile-review-2026-10-09/build.json`
- `hatena/mobile-review-2026-10-09/css-validation.json`
- `hatena/mobile-review-2026-10-09/desktop-tablet.json`
- `hatena/mobile-review-2026-10-09/final-interactions.json`
- `hatena/mobile-review-2026-10-09/inputs.json`
- `hatena/mobile-review-2026-10-09/interactions.json`
- `hatena/mobile-review-2026-10-09/manifest.json`
- `hatena/mobile-review-2026-10-09/navigation-diagnosis-before.json`
- `hatena/mobile-review-2026-10-09/navigation-diagnosis.json`
- `hatena/mobile-review-2026-10-09/navigation-timeline.json`
- `hatena/mobile-review-2026-10-09/navigation.json`
- `hatena/mobile-review-2026-10-09/poison.json`
- `hatena/mobile-review-2026-10-09/root-cause.json`
- `hatena/mobile-review-2026-10-09/scroll.json`
- `hatena/mobile-review-2026-10-09/test-summary.json`
- `hatena/mobile-review-2026-10-09/visual.json`
- `main.py`
- `season_ui.py`
- `tests/test_gallery_navigation.js`
- `tests/test_hatena_iframe_handler.js`
- `tests/test_mobile_optimization.py`
- `tests/test_phase4c10_records_alignment.py`
- `tests/test_poison_spores.js`
- `tests/test_season_ui.py`
- `tests/test_top_portal.py`

Supplementary visual bundle: `mobile-optimization-visual-evidence-2026-10-09.zip` (4,402,051 bytes), SHA-256 `8689411c6270f8346a23ac93a254a331c814232f86a1849d073da74a29d11c5f`. No screenshot or large video is committed to this repository.

Intermediate `scroll.json` and `navigation.json` are explicitly marked SUPERSEDED and are not final acceptance evidence. The final 60 cases in `final-interactions.json` are authoritative. Their deletion command was rejected by automatic approval review, so they are retained with clear provenance.
