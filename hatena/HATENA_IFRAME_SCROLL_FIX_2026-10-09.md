# Hatena iframe navigation and scroll preservation — manual replacement

PARENT_HATENA_PATCH_REQUIRED: YES

Starting main: `08c3f2c056bd7ffa53461022a288cb25902760f0`
Starting tree: `cb9c673a7c4f06019e2dd98a653453ddd75c1911`
Branch: `fix/hatena-body-scroll-container-2026-10-10`

## 2026-10-10 BODY scroll host — current finding

**Actual root cause: Hatena Design Staging uses BODY as its scroll container.**
The user measured this directly in the top-level Hatena Staging console after manually
applying PR #98. Height shrink worked and the giant blank area disappeared, but
scroll-to-iframe-top still failed. The actual measurements were:

| Element | Scroll top | Client height | Scroll height | Overflow Y | Rect top |
| --- | ---: | ---: | ---: | --- | ---: |
| Window | 0 | — | — | — | — |
| HTML / document.scrollingElement | 0 | 897 | 897 | hidden | — |
| BODY | 4000 | 841 | 4841 | auto | 56 |
| photoGallery iframe | — | — | — | — | -3652 |

The iframe rect height was 4199px. The old window-coordinate target was -3672;
window.scrollTo left window.scrollY=0 and did not move the actual view. The correct
BODY content top is `-3652 - 56 + 4000 = 292`; the 20px offset gives **272px**.
These are user-supplied real Staging diagnostics, not a claim that this run accessed
or edited the user's private Staging session. They supersede timing-only explanations
as the current root cause. The PR #96–98 investigations below remain historical;
their browser harness exercised only normal window scrolling.

### Unified scroll context

The communication candidate now chooses Window/HTML for normal scrolling or the
independently sized, auto/scroll-overflow BODY when HTML is locked/non-scrolling.
It detects that layout even at BODY.scrollTop=0 and after content becomes shorter
than the viewport. All positioning, reservation, upward reclaim and viewport-size
calculations use the same context. BODY coordinates subtract its viewport rect top
and clientTop (border), then add BODY.scrollTop; its viewport height is clientHeight.
Window mode retains rect top + window.scrollY and window.innerHeight.

A passive scroll listener is attached to the actual host. Host changes detach the
old listener and reset the previous-position baseline; resize rechecks the host.
Neither listener selection nor resize scrolls the page.

Validated intent still completes **instant scroll on the actual host before ACK**.
Load only clears pending intent, releases old reservation, resets the height cache
and requests the destination height. Cancel clears pending state without rollback.
No setHeight/in-place/resize/initial or ordinary load calls scrollTo. No 0px collapse
or forced reflow is reintroduced. The source, origin, destination and ID guards,
legacy navigation and lgClosed behavior are retained.

### Initial postMessage warning

A delayed initial GitHub iframe load reproduced one target-origin warning with
PR #98's eager requestHeight, while the initial iframe document still belonged to
Hatena. The candidate sends no eager request. It waits for a gallery load or a
strictly authenticated gallery message, ignores an observable parent-origin initial
load, and retains exact galleryOrigin for height requests and ACKs. No permanent
wildcard targetOrigin is introduced. Bounded post-load retries remain unchanged.
The same delayed-load browser fixture produced zero origin warnings with the candidate.

### Validation evidence

Current evidence: `body-scroll-review-2026-10-10/`. Browser acceptance uses the saved
actual Hatena DOM and real generator output at separate parent/child origins. A
**test-only** root/BODY layout overlay reproduces HTML overflow:hidden, BODY
overflow:auto and BODY viewport top=56; no production CSS is changed. The browser
fixture's current content geometry is recorded separately from the exact measured
4000→272 unit fixture. Prior window-only evidence is not relabeled as BODY evidence.

| Width | Window navigation / in-place | BODY navigation / in-place | Overflow |
| --- | --- | --- | --- |
| 360 | 6/6; 9/9 | 6/6; 9/9 | NONE |
| 390 | 6/6; 9/9 | 6/6; 9/9 | NONE |
| 430 | 6/6; 9/9 | 6/6; 9/9 | NONE |
| 768 | 6/6; 9/9 | 6/6; 9/9 | NONE |
| 1440 | 6/6; 9/9 | 6/6; 9/9 | NONE |

**60 navigation / 90 in-place PASS**. Navigation scrolls exactly once on the selected
host before ACK; iframe load scrolls zero times. All in-place changes have **delta
0px / scroll call 0**, including bottom-edge details close. Both parent and child
have no horizontal overflow. Initial load makes no scroll calls in either model.
Actual destination height matches the child content measurement; navigation leaves
no wrapper min-height reservation. BODY mode keeps window.scrollY=0 throughout.

The exact user-coordinate unit fixture asserts **BODY 4000→272px**, with HTML as
`document.scrollingElement`, HTML overflow hidden, BODY viewport height 841px and
rect top 56px; no window.scrollTo call is made. Listener transfer, BODY-at-top/short
content, border offsets, BODY viewport resize, upward reclaim, authentication,
legacy navigation and lgClosed are also covered.

Browser BODY example, 390px features-bottom→index: **5906→301px**,
iframe **6327→1797px**, BODY viewport top
**56px**, viewport height **844px**.
The instant scroll completes at **1791638253286ms**, ACK is sent at
**1791638253286ms**, and load follows at **1791638254257ms**.
Target=301.296875px; the browser rounds to 301px. This geometry comes
from the current saved DOM/mobile CSS and is not misrepresented as the user's exact
private Staging geometry.

Focused old/new BODY reproduction: PR #98 goes **5906→1376px**, missing its
301.296875px target; the candidate goes **5906→301px**. The separate delayed-initial
load experiment gives **1 old / 0 candidate** target-origin warnings.

Validation: **600 pytest passed / 600 collected**; parent JS **17**, gallery JS
**7**, poison JS **11**, other JS **5**, all JS **40** passed. compileall, parent JS
syntax, diff check and unchanged CSS parsing PASS. Real generator build: **321 HTML
pages**, 923 observations, 302 subjects. All assets, CSS, renderer, knowledge,
provenance/facet/toxicity data, admin and workflows are unchanged from starting main.

Evidence files contain the complete event/coordinate matrix, old/new reproduction,
user diagnostic, build, test summary and SHA-256 manifest. These are browser-equivalent
acceptance results. The revised parent still requires manual verification in the
same private Staging environment; no Hatena save/publish was performed.


### Manual replacement and scope

Apply only `hatena-footer-iframe-handler-candidate-2026-10-09.html` in authorized
Staging after backing up the current communication block. Do not append another
handler or replace PAGE TOP. Verify features-bottom→index in the same real BODY
scroll environment; this run does not save/publish Hatena or claim that private
Staging acceptance is completed. The GitHub Pages child and all CSS need no change.
PAGE TOP is explicitly outside this patch and remains byte-identical.

## 2026-10-10 PR #98 timing follow-up — historical window-only specification

The user applied PR #97's parent candidate to actual Hatena Design Staging and confirmed **height shrink PASS / giant blank space resolved / scroll-to-iframe-top FAIL** for features-bottom → index. This supersedes the prior browser-equivalent success as evidence of real Staging navigation behavior. The Staging result was supplied by the user; this run does not claim access to that private session.

PR #97 postponed scroll until destination iframe load, after ACK allowed destruction of the long departing document. That ordering could not guarantee the user's pre-navigation scroll UX in Staging. The specific browser-internal reason for the missed load-time repositioning has not been independently established; it is not presented as a proven storage denial or smooth-scroll cancellation.

The fix changes **only parent timing**: validate source/origin/path/ID → complete instant scroll → record pending/scrolled → ACK → native navigation. Load no longer calls scrollToTitle. This restores the old footer's click-time positioning without its destructive zero-height hack. Child sender, gallery.js, poison colors/motion/eligibility, CSS and renderer are unchanged from starting main.

### Cancel/error/fallback policy

If a link is changed or removed while ACK is in flight, the existing child may send navigationIntentCancel. The parent clears its matching pending state but **does not roll back an already completed scroll**. The user remains at the iframe top on the old page; this rare cancellation is not a completed navigation and does not trigger a second scroll. Automatically restoring a stale lower position would fight any intervening user scroll. No new timeout or rollback machinery is added. The existing 120ms child fallback and legacy scrollToTitle compatibility path remain unchanged.

### PR #98 browser and test evidence — historical

Current evidence is stored separately in `navigation-timing-review-2026-10-10/`; the PR #97 evidence below remains historical and is not relabeled.

| Width | Navigation | In-place | Parent/child overflow |
| --- | --- | --- | --- |
| 360 | 6/6 PASS | 9/9 PASS; delta 0px | NONE |
| 390 | 6/6 PASS | 9/9 PASS; delta 0px | NONE |
| 430 | 6/6 PASS | 9/9 PASS; delta 0px | NONE |
| 768 | 6/6 PASS | 9/9 PASS; delta 0px | NONE |
| 1440 | 6/6 PASS | 9/9 PASS; delta 0px | NONE |

All **30 navigation** cases have exactly **one** scroll, completed before ACK is sent and before native document navigation. The recorded ordering is intent received → scroll complete → ACK sent → document navigation → load. Load itself scrolls **zero** times. Destination actual height matches its measured content root and body padding; wrapper reservation is empty. A post-load forced height response is present in every case. The unchanged child can also send an early height measurement before load; that is safe and never triggers another scroll.

Representative features-bottom → index, 360px: parent **5895 → 301px**, iframe **6372 → 1797px**, wrapper min-height empty. At time **1791619973549ms** intent is received, instant scroll completes at y=301 and ACK is sent. Native document navigation follows at **1791619973563ms**; load follows at **1791619973822ms**. Final height is 1797px. The ordering was asserted at each width, not inferred from final position alone. A same-document query/history URL change may produce an additional framenavigated notification; it is not a second document load or link activation.

All **45 in-place** cases have scroll call **0**, parent delta **0px**, no intent/scrollToTitle message and no overflow, including bottom-edge details close. Initial load makes zero scroll calls at all five widths.

Current validation: **600 pytest passed / 600 collected**; parent JS **6**, gallery navigation JS **7**, poison JS **11**, all JS scripts **29** passed. compileall, JS syntax and diff check PASS. Real generator build: **321 HTML**, 923 observations, 302 subjects. All assets (including gallery.js and poison-spores.js), Design CSS, renderer, protected data and workflows have no diff from starting main.

See `browser-matrix.json` for event timestamps, scroll/height before/after, wrapper min-height, source/origin, document navigation, load count and scroll count; `test-summary.json`, `build.json` and `manifest.json` hold compact final validation and hashes. The evidence uses an ACK-send logging hook in the browser harness only; no logging hook was added to the shipped candidate. Hatena production/Staging were not edited in this run; the user must verify the revised parent candidate in the same Staging environment that exposed PR #97's timing failure.

## PR #96 follow-up: observed failure and diagnosis

After PR #96 was merged, the user confirmed a real Hatena Design Staging failure: **features → bottom footer → index** navigated to the shorter index but left the parent in a pale-green blank area. Feature filters already preserved scroll correctly. This report distinguishes that user observation from this run's local measurements.

The historical PR #97 investigation reused the saved real Hatena DOM, cached resources, generated pages and Chromium 153. Both origins remained distinct (`exsudoporus-ruber.hatenablog.jp` parent / `charchan123.github.io` child). No private Staging session was accessed. Its original assets/parent were taken from main `33dd7817e1b5af355cf41ab48d9fb6db0ad35e3c`.

The features footer does reach the shared navigation listener. With normal sessionStorage, the marker is saved, remains available at destination pageshow, is consumed, and the live destination's message passes the exact origin/source guard. Ordinary navigation succeeds. The prior 15 cases exercised this successful path, not unavailable storage or a delayed pageshow.

Two focused failures were reproduced independently:

| Starting-main condition, 390px | Before scrollY | After scrollY | Iframe height | Wrapper min-height | Result |
| --- | ---: | ---: | --- | --- | --- |
| Normal storage | 5850 | 301 | 6327 → 1797px | empty | PASS |
| Third-party sessionStorage throws SecurityError | 5850 | 1320 | 6327 → 1797px | 1899px | Blank-space failure |
| Destination stylesheet delays pageshow by 11s | 5850 | 1320 | 6327 → 1797px | 1899px | Blank-space failure |

The departing message arrives with **event.source === null** after document replacement and is correctly rejected. Storage denial prevents replay; an 11-second load exceeds the old 10-second replay lifetime. Early destination setHeight can reserve the old bottom viewport; load releases that space, browser clamping changes the viewport, and subsequent height synchronization reserves space at the remaining lower position. Without an authenticated navigation request there is no authorized scroll to the iframe top. The actual iframe height can therefore be correct while the parent still shows blank space.

Smooth-scroll cancellation is not the demonstrated cause here: the PR #96 handler already uses instant positioning. The fragile dependency is the departing-message/destination-storage replay chain and its ordering with height/load/reservation.

## PR #97 paired replacement behavior — historical child protocol

Deploy the paired `assets/gallery.js` change and replace the complete **photoGallery communication script** with `hatena-footer-iframe-handler-candidate-2026-10-09.html`. Do not append a second handler or replace the adjacent PAGE TOP script.

1. An unmodified, same-frame, same-origin HTML link sends `navigationIntent` with an ID and destination path. The child prevents only that activation, keeping its document alive.
2. The parent requires the existing exact iframe WindowProxy and origin checks and validates the ID and destination within the gallery directory. It then **completes instant scrollToTitle while the departing page still exists**, records `{id, scrolled:true}`, and only then sends `navigationIntentAck` to the gallery origin. A repeated pending ID receives another ACK without another scroll.
3. The child accepts only a matching ACK from its actual parent (also exact origin when known from a cross-origin referrer), clears the optional storage replay marker, and activates the original native link once. No navigation URL is taken from the ACK.
4. Iframe load **does not scroll**, whether initial, ordinary or navigation load. It clears pending intent, releases reserved space, resets the height cache and requests actual destination height. The authenticated intent has already settled the parent at iframe top minus 20px before native navigation.
5. Actual setHeight messages directly set finite, nonnegative height. The existing bounded height retries remain. No temporary `height=0px` / forced reflow returns.

Acknowledging intent before document replacement guarantees that the parent has recorded the explicit navigation even if storage is unavailable or destination load is slow. A changed/disconnected link cancels its matching intent rather than navigating. Repeated clicks on the pending link cannot multiply activations; pagehide cleans up the child timer.

### Referrer and compatibility

After a native iframe navigation, `document.referrer` can be the **previous child page**, not the Hatena parent. It must not be used as the parent's origin in that case. A cross-origin HTTP(S) referrer is used as an exact target/ACK origin; otherwise the intent is sent with `*` and the ACK is authenticated by the actual parent WindowProxy and matching pending ID. The parent's strict origin/source checks are unchanged; null or unrelated sources remain rejected.

An older/missing parent receives one bounded **120ms** fallback to native activation, the legacy departing scroll message and optional sessionStorage replay. No indefinite wait or retry loop is introduced. Reliable scroll restoration with blocked storage requires the paired new parent; old parents retain the documented best-effort limitation. Top-level pages bypass the handshake entirely.

External links, `_top`/`_blank` links, downloads, modified/middle clicks, fragment-only navigation, buttons, filters and details do not send navigation intent. Search/filter semantics and hrefs are unchanged.

### In-place preservation

Keep actual iframe height accurate, reserve minimum height on the outer wrapper when needed to prevent bottom-edge clamp, and reclaim that space during upward scrolling or growth. Reservation is legitimate for an in-place collapse, not a reason to keep old navigation space indefinitely. Initial load, untagged load, resize and setHeight **never call scrollTo**. `lgClosed`, fullscreen cleanup and requestHeight remain authenticated and functional.

The old footer's intended UX—navigate, return to iframe top, fit the new page—is restored conceptually. Its destructive zero-height intermediate step is not restored.

## PR #97 browser evidence — historical

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

## PR #97 color-only poison spore follow-up — historical

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

## PR #97 automated validation — historical

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

Rollback for this follow-up: restore only the backed-up communication block. No child JS or CSS version changes are included in this patch. The historical PR #97 paired rollback required restoring its prior child JS as well. The Slim baseline and full mobile CSS are preserved. No merge, manual deployment, workflow_dispatch, auto-merge, Hatena production save or publish was performed.
