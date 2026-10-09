# Hatena iframe navigation and scroll preservation — manual replacement

PARENT_HATENA_PATCH_REQUIRED: YES

Status: PASS for the browser-equivalent acceptance matrix. Hatena production and Design Staging were not edited during this run. The actual Staging device/storage restriction remains unconfirmed; the two independently reproduced failure mechanisms below do not require guessing that restriction.

Starting main: `33dd7817e1b5af355cf41ab48d9fb6db0ad35e3c`
Starting tree: `aaa7b5168361afb06e3e6b25e8b6a71eda05a4ef`
Branch: `fix/hatena-navigation-and-spore-colors-2026-10-09`

## PR #96 follow-up: observed failure and diagnosis

After PR #96 was merged, the user confirmed a real Hatena Design Staging failure: **features → bottom footer → index** navigated to the shorter index but left the parent in a pale-green blank area. Feature filters already preserved scroll correctly. This report distinguishes that user observation from this run's local measurements.

This run reused the saved real Hatena DOM, cached resources, generated pages and Chromium 153. Both origins remained distinct (`exsudoporus-ruber.hatenablog.jp` parent / `charchan123.github.io` child). No private Staging session was accessed. Original assets/parent were taken from the starting main.

The features footer does reach the shared navigation listener. With normal sessionStorage, the marker is saved, remains available at destination pageshow, is consumed, and the live destination's message passes the exact origin/source guard. Ordinary navigation succeeds. The prior 15 cases exercised this successful path, not unavailable storage or a delayed pageshow.

Two focused failures were reproduced independently:

| Starting-main condition, 390px | Before scrollY | After scrollY | Iframe height | Wrapper min-height | Result |
| --- | ---: | ---: | --- | --- | --- |
| Normal storage | 5850 | 301 | 6327 → 1797px | empty | PASS |
| Third-party sessionStorage throws SecurityError | 5850 | 1320 | 6327 → 1797px | 1899px | Blank-space failure |
| Destination stylesheet delays pageshow by 11s | 5850 | 1320 | 6327 → 1797px | 1899px | Blank-space failure |

The departing message arrives with **event.source === null** after document replacement and is correctly rejected. Storage denial prevents replay; an 11-second load exceeds the old 10-second replay lifetime. Early destination setHeight can reserve the old bottom viewport; load releases that space, browser clamping changes the viewport, and subsequent height synchronization reserves space at the remaining lower position. Without an authenticated navigation request there is no authorized scroll to the iframe top. The actual iframe height can therefore be correct while the parent still shows blank space.

Smooth-scroll cancellation is not the demonstrated cause here: the PR #96 handler already uses instant positioning. The fragile dependency is the departing-message/destination-storage replay chain and its ordering with height/load/reservation.

## Paired replacement behavior

Deploy the paired `assets/gallery.js` change and replace the complete **photoGallery communication script** with `hatena-footer-iframe-handler-candidate-2026-10-09.html`. Do not append a second handler or replace the adjacent PAGE TOP script.

1. An unmodified, same-frame, same-origin HTML link sends `navigationIntent` with an ID and destination path. The child prevents only that activation, keeping its document alive.
2. The parent requires the existing exact iframe WindowProxy and origin checks, validates the ID and destination within the gallery directory, records pending navigation, and sends `navigationIntentAck` to the gallery origin. Intent alone does not scroll.
3. The child accepts only a matching ACK from its actual parent (also exact origin when known from a cross-origin referrer), clears the optional storage replay marker, and activates the original native link once. No navigation URL is taken from the ACK.
4. The **next iframe load with authenticated pending intent**, and only that load, scrolls instantly to iframe top minus 20px **before** releasing wrapper reservation. It consumes the intent, releases reserved space, resets the height cache and requests actual destination height.
5. Actual setHeight messages directly set finite, nonnegative height. The existing bounded height retries remain. No temporary `height=0px` / forced reflow returns.

Acknowledging intent before document replacement guarantees that the parent has recorded the explicit navigation even if storage is unavailable or destination load is slow. A changed/disconnected link cancels its matching intent rather than navigating. Repeated clicks on the pending link cannot multiply activations; pagehide cleans up the child timer.

### Referrer and compatibility

After a native iframe navigation, `document.referrer` can be the **previous child page**, not the Hatena parent. It must not be used as the parent's origin in that case. A cross-origin HTTP(S) referrer is used as an exact target/ACK origin; otherwise the intent is sent with `*` and the ACK is authenticated by the actual parent WindowProxy and matching pending ID. The parent's strict origin/source checks are unchanged; null or unrelated sources remain rejected.

An older/missing parent receives one bounded **120ms** fallback to native activation, the legacy departing scroll message and optional sessionStorage replay. No indefinite wait or retry loop is introduced. Reliable scroll restoration with blocked storage requires the paired new parent; old parents retain the documented best-effort limitation. Top-level pages bypass the handshake entirely.

External links, `_top`/`_blank` links, downloads, modified/middle clicks, fragment-only navigation, buttons, filters and details do not send navigation intent. Search/filter semantics and hrefs are unchanged.

### In-place preservation

Keep actual iframe height accurate, reserve minimum height on the outer wrapper when needed to prevent bottom-edge clamp, and reclaim that space during upward scrolling or growth. Reservation is legitimate for an in-place collapse, not a reason to keep old navigation space indefinitely. Initial load, untagged load, resize and setHeight **never call scrollTo**. `lgClosed`, fullscreen cleanup and requestHeight remain authenticated and functional.

The old footer's intended UX—navigate, return to iframe top, fit the new page—is restored conceptually. Its destructive zero-height intermediate step is not restored.

## Current-run browser evidence

Evidence: [`navigation-followup-review-2026-10-09/`](navigation-followup-review-2026-10-09/).

| Width | Six real navigation cases | Nine in-place cases | Parent/child horizontal overflow |
| --- | --- | --- | --- |
| 360 | 6/6 PASS | 9/9, all delta 0px | NONE |
| 390 | 6/6 PASS | 9/9, all delta 0px | NONE |
| 430 | 6/6 PASS | 9/9, all delta 0px | NONE |
| 768 | 6/6 PASS | 9/9, all delta 0px | NONE |
| 1440 | 6/6 PASS | 9/9, all delta 0px | NONE |

Navigation cases: features bottom → index; season footer → index; aiuo footer → index; detail → aiuo; detail → index; toxic mushroom card → detail. **30/30 PASS**. Each records before/after scrollY, iframe height, wrapper min-height, source/origin, message ordering, load count and scrollTo count. Each has exactly one authorized scroll, zero destination reservation, correct destination URL and actual destination height (index 1797px on mobile / 1029px on desktop).

In-place cases: feature ON, OFF, clear; details open, close, bottom-edge close; season tab; kana filter; kana search. **45/45 PASS**, each delta **0px**, no navigation intent, no scrollTo and no overflow. Initial load made no unwanted scroll request at all five widths.

Also **10/10 chained navigation PASS**, with both normal and denied storage, without resetting the child between links. These test the real previous-child referrer, including index → aiuo → detail → aiuo → index. Both denied-storage and 11-second pageshow failures pass with the paired fix (parent y=301, empty reservation, actual height 1797px).

Detailed machine-readable evidence:

- `reproduction-before.json` / `reproduction-after.json`
- `slow-pageshow-before.json` / `slow-pageshow-after.json`
- `browser-matrix.json` (75 cases)
- `chained-navigation.json`
- `poison.json` / `poison-paired-iframe.json`
- `test-summary.json`, `build.json`, `css-unchanged.json`, `manifest.json`

## Color-only poison spore follow-up

Only the four preset core/edge colors changed:

| Spore | Old core / edge | New core / edge |
| --- | --- | --- |
| Yellow-green | #EEFF88 / #D7F957 | **#D2FF5A / #69D600** |
| Violet | #F0D2FF / #E2A5FF | **#CFA0FF / #7838D1** |

Actual カエンタケ photo decoded at naturalWidth=1200. The same 1440px Chromium card was captured before/after with both motion/appearance animations fixed to 500ms for comparable positions. Visual classification: **yellow-green / violet**; soft radial edges retained, no added glow. The darker edges distinguish the colors without changing opacity or motion.

![Before: pale yellow/pink cores](navigation-followup-review-2026-10-09/spore-colors-before.png)

![After: yellow-green/violet](navigation-followup-review-2026-10-09/spore-colors-after.png)

Count remains 10 (six green/four violet). Preset size/path/bend/duration/delay/opacity are byte-equivalent as a JSON projection to starting main; SHA-256 `1037f439d0687a8c8fdaf3b6cf92ae500a21475f74ef1b4e0a7662d3304bb766`. Radial-gradient CSS, easing, cleanup, eligibility and 600ms touch delay are unchanged.

Measured browser timings: poison 605ms, double tap 603ms, paired parent/child double tap 604ms; navigation exactly once in each. Non-poison 4ms, reduced motion 7ms, keyboard 4ms. PC hover: one burst, 10 particles, no navigation. Toxicity remains explicit server-supplied `poisonous_confirmed`, with no inference.

## Final automated validation

- Full pytest: **600 passed**; collection: **600**.
- Gallery navigation JS: **7 passed**; parent iframe JS: **5 passed**; poison JS: **11 passed**.
- All JS scripts: **28 passed**, zero failures (includes five other script-level checks).
- Python compileall, JS syntax (gallery, poison and extracted parent candidate), git diff check: **PASS**.
- Real generator build from saved production portal data: **321 HTML pages**, 923 observations, 302 subjects.
- CSS parser validation: no stylesheet syntax errors; Slim baseline, full mobile Design CSS and gallery.css **unchanged**.
- Protected paths `data/**`, `audit/**`, `feature_overlay.py`, `admin/**`, `.github/**`: **no diff** from starting main. Biology, provenance, facet assignments and toxicity classifications unchanged.

The previous 34-case layout/computed-style evidence remains under `mobile-review-2026-10-09/`; it was not relabeled as a new run. This follow-up has no CSS/renderer/layout change and independently verifies overflow in the 75 current interaction cases.

## Manual Hatena review and rollback

PARENT_HATENA_PATCH_REQUIRED: YES. This Draft PR cannot automatically update Hatena's parent footer. Back up the current footer, apply **only** the replacement communication block to an authorized Preview/Staging, and verify features-bottom → index under the same privacy settings/device as the reported failure. Do not save/publish Hatena production as part of this task.

Review other actual navigation links, initial load, all in-place operations, bottom-edge shrink, native controls, PAGE TOP and lightGallery close. The full mobile Design CSS does not need replacing again for this follow-up. If only the child is updated, old-parent fallback remains best effort; the paired parent replacement is necessary for the reliability guarantee.

Rollback: restore the previously backed-up communication block and the prior child JS versions together. The Slim baseline and full mobile CSS are preserved. No merge, manual deployment, workflow_dispatch, auto-merge, Hatena production save or publish was performed.
