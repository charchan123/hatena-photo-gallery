# Hatena Design CSS slimming audit

Status: PASS. Review artifact only; not connected to deployment.

## Source and rollback identity

- Read-only source branch: `audit/hatena-design-css-input-2026-10-07`
- Pinned source commit: `a9f10eeb4826c1ebfb7e972562cc141a8cd3c46c`
- Source path: `hatena-design-css-source-2026-10-07.css`
- Source size: **62,059 bytes**
- Source SHA-256: `8ecbf814d5786dd36017246edf02e5f1214fa841d0d9bc806a2fe01949b73217`
- Identity verified before editing: YES (both GitHub retrieval and `git show` agree).
- Starting main: `0c64a654b3d4ee9ae8d86869fdc7f8bd03a2443c`
- Starting tree: `3534fa6c4a713e519b2fc97e98ece32779c2c774`
- Implementation branch: `audit-hatena-css-slimming`, created from latest main, not the input branch.
- Source branch/file modified: NO.

The slim file is a **complete Design CSS replacement**, not an append-only patch. It includes the unpublished Phase 4C.11 article design. The existing `hatena/hatena-article-newtop-preview.css` is unchanged; it is the earlier article-only append patch and does not replace this full source. Do not append that patch after the slim file. No Hatena editor save/publish was performed.

Rollback: retrieve the exact source from the pinned input commit and verify the size/hash above. This audit does not change current Hatena production, so no production rollback is presently required.

## Measured reduction

| Measure | Original | Slim | Reduction |
|---|---:|---:|---:|
| Lines (`splitlines`, including final unterminated source line) | 2,310 | 1,212 | 1,098 (47.53%) |
| UTF-8 bytes | 62,059 | 35,041 | 27,018 (43.54%) |
| Style rules | 164 | 140 | 24 |
| Declarations | 760 | 625 | 135 |
| Duplicate properties within one rule | 1 | 0 | 1 |
| Repeated exact selector/context keys (textual) | 13 | 9 | 4 |

Slim SHA-256: `0158ad4f6b192abc8315903a7149be7ac5ed950253938f80b88329c1ae1f15c2`.

Both Hatena system sections, including their comments, theme import and background declaration, are byte-for-byte preserved. Formatting outside those sections uses readable indentation and LF line endings. The source remains untouched. Savings include formatting and historical-comment cleanup; they are not all executable CSS removal.

## Conservative cascade method

The entire source was parsed with tinycss2. Only an earlier declaration of the **same property and exactly the same selector list** was removed when a later valid declaration covered the same media context (or was unconditional) and had equal or stronger importance. Selector specificity therefore remains identical for every such comparison. Declaration-level decisions preserve properties not overwritten by later partial blocks.

- Media conditions are retained verbatim except surrounding formatting. No assumptions that desktop and mobile exhaust every possible fractional viewport width.
- No selector renaming, specificity reduction, `!important` removal, custom-property deletion, value tuning or new breakpoint.
- Shorthand/longhand resets and vendor aliases are retained conservatively: e.g. border/border-bottom, mask/mask-image and both clip-path forms. No inference that a shorthand is redundant merely because a nearby longhand exists.
- Inheritance and pseudo-elements remain attached to the same selectors. Variable-based fallback substitutions were not inferred.
- Only adjacent identical media containers were joined, preserving all inner source order. Only adjacent identical selector rules were joined. Nonadjacent declarations were not moved across potentially competing selectors.
- Retained duplicate selectors are intentional where safe removal or movement has not been proven. There is no unused-selector purge.

## Deletion classification

Counts have different units and must not be added together.

| Class | Count | Meaning |
|---|---:|---|
| A: fully overridden historical declarations | 88 declarations | Later same-property winner covers the earlier scope and priority. |
| B: exact duplicate declarations | 47 declarations | Same final value; earlier copy cannot win. |
| C: adjacent identical media-query consolidation | 7 joins | Inner rule order preserved. |
| D: superseded/empty historical rules | 23 rules | All declarations removed under A/B; emptied containers also omitted. |
| E: confirmed-unused selector removal | **0** | No selector was removed on a guess about conditional DOM. |
| F: comment/history cleanup | 145 non-system source comments replaced | Historical/numerical tuning commentary replaced with 20 current-purpose section comments; four system comments retained. |

One additional pair of adjacent identical selector rules was merged without moving declarations across another rule.

## Major deletion/consolidation ledger

Line numbers refer to the pinned original CSS, not the slim file.

| Original section | What changed | Why safe / final source of values |
|---|---|---|
| Shared PAGE TOP, around 112–115 | Remove earlier `top:30%` within the same pseudo-element rule. | Later `top:22px` wins in the same block; size, translation and click target remain. The harmless empty declaration after `border-radius` is omitted by serialization. |
| New-top tuning 01–02, around 858–1040 | Remove superseded Hero height/background, image position/clip, title/subtitle and content margin values. | Same desktop media scope; final Hero at 1389/1606–1638, cutout at 1649–1657, text at 1444–1507/1570–1587, margin at 1520. Still-live `left:auto`, opacity and brightness settings remain. |
| New-top tuning 03–04, around 1062–1366 | Remove only fully superseded declarations and now-empty blocks. | Final desktop title family/weight/size/spacing, pseudo-element text shadow and cutout values remain at their later winning locations. Wrapper overflow rules with additional selectors are retained. |
| New-top tuning 05–06 and final adjustment, around 1380–1695 | Preserve final surviving declarations and join adjacent desktop media containers. | Height 228px, 18px white strip, image `top:0`/clip 78px, title top 62px plus translateY(18px), subtitle top 142px plus translateY(18px), content margin -14px. No final values were redesigned. |
| Article base and 960px/680px Hero rules, around 1726–2140 | Remove earlier height/background/position/clip values covered by later rules. | Later unconditional final height 232px intentionally wins over the old 960px height 210px. The later 680px rule restores height 188px. This existing behavior is preserved, not “fixed.” |
| Article top-strip override, around 2207–2240 | Remove the obsolete 12px strip, height 236px and prior image positions. | Final 7px strip and height 232px at 2249–2264; final image positions/clip at 2270–2308, including desktop top -6px. |
| All responsive rules | Join only adjacent equal conditions; keep overlapping overrides in their existing order. | Tablet/mobile cascade, shared-menu breakpoints and pseudo-element inheritance remain unchanged. |
| Historical comments | Remove obsolete “previously”, tuning iteration and screenshot-relative instructions. | Replace with current section descriptions; preserve executable values and system sections. |

### Important effective values retained

| Target | Desktop (1440) | Tablet (768) | Mobile (390) |
|---|---|---|---|
| New-top Hero height | 228px | 220px | 188px |
| New-top image top / bottom clip | 0 / 78px | -16px / 34px | 0 / 28px |
| New-top content margin-top | -14px | 0 | 0 |
| Article Hero height | 232px | **232px** | 188px |
| Article image top / bottom clip | -6px / 48px | -1px / 42px | 0 / 10px |

## Visual and computed-style method

Actual public DOM snapshots were downloaded once and reused:

- `https://exsudoporus-ruber.hatenablog.jp/new-top`
- `https://exsudoporus-ruber.hatenablog.jp/entry/2026/09/25/225327` (first observation-record link)

The Design CSS link was replaced at the same cascade position, first with Original and then Slim on the same DOM. Theme import, embedded header rules, photos, sidebar, iframe and native controls remained. Public article CSS was never the expected result: both compared states use the unpublished source's Phase 4C.11 design.

Chromium used a shared font configuration (Noto Sans JP fallback on Linux). This compares CSS equivalence in one rendering environment; it does not claim Windows/macOS font rasterization is identical. External resources were cached and reused. Lazy images were fully decoded before screenshots. Native loading animations were sampled at a fixed time; functional tests used a separate page with no fake clock. Earlier differences caused by lazy loading/animation timing were investigated rather than accepted as CSS regressions.

Computed snapshots include every main-document non-script/style element and both `::before`/`::after`, all enumerated CSS properties and bounding rectangles. This includes the requested hero, title, menu, content, article, sidebar, comments and PAGE TOP selectors. Whole-page pixel comparison includes the embedded new-top portal.

| Page | Viewport width | Computed differences | Pixel differences | Horizontal overflow |
|---|---:|---:|---:|---|
| article | 1440 | 0 | 0 | NONE |
| article | 390 | 0 | 0 | NONE |
| article | 768 | 0 | 0 | NONE |
| top | 1440 | 0 | 0 | NONE |
| top | 768 | 0 | 0 | NONE |
| top | 390 | 0 | 0 | NONE |
| top | 680 | 0 | 0 | NONE |
| top | 681 | 0 | 0 | NONE |
| top | 960 | 0 | 0 | NONE |
| top | 961 | 0 | 0 | NONE |
| article | 680 | 0 | 0 | NONE |
| article | 681 | 0 | 0 | NONE |
| article | 960 | 0 | 0 | NONE |
| article | 961 | 0 | 0 | NONE |

All 14 complete screenshots match pixel-for-pixel. Required new-top 1440/768/390 and article 1440/390 comparisons PASS, plus both sides of the 680px/960px breakpoints and article tablet. Original and Slim use the same captured DOM/resources.

Separate real-time functional checks: article MENU opens and closes at 390px and 768px for both CSS versions, including visibility of the actual menu links. The floated-link container itself has zero height even when open; testing its bounding box alone was an invalid visibility assertion, corrected without changing CSS. PAGE TOP returns to scrollY < 5 on article 390/768 and new-top 390. Link hrefs, display, visibility and pointer-events, plus Star/social/comment container styles, match exactly. New-top menu remains hidden as designed, and its actual iframe is included in the screenshots. No links were followed to perform an external account action.

Artifact bundle: `hatena-design-css-audit-evidence-2026-10-07.zip`. Inside `visual/`, required before/after screenshots are `top-1440-original.png`, `top-1440-slim.png`, `top-390-original.png`, `top-390-slim.png`, `article-1440-original.png`, `article-1440-slim.png`, `article-390-original.png`, `article-390-slim.png`. Tablet and boundary-width screenshots, all computed snapshots, `pixel-diff.json`, `comparison.json`, `functional-results.json`, `css-validation.json`, and `deletions.json` are also included.


## Native-control / network limitations

Hatena initialization, monthly archive count and circle-module API requests returned 403 in the unsigned test environment. Existing static native DOM and its CSS were retained and compared. Star/social/comment containers are present; sidebar links remain. No star was submitted, comment posted, social share sent or account action performed. This is a CSS preservation check, not a claim of authenticated Hatena service end-to-end testing. Advertising/analytics requests were excluded from the visual fixture.

## Syntax and regression validation

- tinycss2: complete stylesheet, declaration lists and nested media rules parse without errors in both files.
- Chromium `CSS.supports` and selector parsing: all 760 original and 625 slim declarations valid; no rejected selector/declaration.
- Balanced rule structure; no stray executable HTML. System-section HTML-like comments are intentionally retained.
- No within-block duplicate property remains. Remaining duplicate selectors and shorthand/longhand combinations are deliberately retained as explained above.
- No new Python/JS dependency or runtime logic added to the repository. Browser audit harness and raw evidence remain outside the production tree.
- `python -m pytest -q`: 596 passed.
- `python -m pytest --collect-only -q`: 596 collected.
- Focused existing preview regression: `python -m pytest -q tests/test_phase4c11_hatena_preview.py`: 1 passed. No new pytest file added; the direct browser/CSS-parser audit covers this artifact.
- `python -m compileall -q .`: PASS.
- `git diff --check`: default flags identify only the eight original CRLF system-section line endings as trailing whitespace. With Git's `cr-at-eol` handling (`git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --cached --check`): PASS. All ordinary whitespace checks remain enabled; the system-section bytes are preserved rather than normalized.
- Protected paths: PASS; staged diff includes only this report and the slim CSS. `data/**`, `audit/**`, `feature_overlay.py`, `admin/**`, `.github/**`, `assets/**`, `main.py`, and the existing preview CSS are unchanged.

## Review and release boundary

No Hatena production save/publish. No source-branch change. No biology, provenance, audit, data, feature-overlay, Admin, workflow, main.py, portal/gallery CSS or poison-spore runtime change. No merge/deploy/auto-merge/workflow_dispatch. This artifact is for review; a merge by itself does not install Hatena CSS.

The evidence bundle contains original/slim screenshots, computed snapshots, comparison results, parser validation, functional checks and the declaration-level deletion ledger. Keep the pinned original available when reviewing or manually installing the complete CSS in a separate future task.
