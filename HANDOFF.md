# Phase 3A.5 handoff: iframe height shrinking

## Baseline, purpose, and boundary

Phase 3A.5 started from required baseline
`2f9968f69f328c9e1b19c7a242fb8179bef047c2`. It is a focused fix performed before
Phase 3B so that the embedded gallery iframe can shrink as well as grow when normal
page content changes.

The bug was caused by measuring the maximum body/document-element scroll and offset
heights. Those values can retain the current iframe viewport height after the Hatena
parent enlarges it, instead of representing the smaller intrinsic content height.

## Measurement and observation design

At the beginning of `DOMContentLoaded`, `assets/gallery.js` creates
`#gallery-content-root` if it does not already exist and moves the existing body nodes
into it. Moving nodes does not clone or reload scripts. UI appended to body later—such
as LightGallery overlays and favorite/undo toasts—remains outside the measurement root
and therefore cannot inflate the normal iframe height. Minimal `display: flow-root` and
`width: 100%` styling makes the root contain the normal layout without a visual redesign.

Height is calculated from `gallery-content-root.getBoundingClientRect().height`, plus
the computed body's top and bottom padding, and rounded upward to an integer pixel.
It no longer uses body or document-element viewport-dependent scroll/offset heights.
Only an exactly repeated integer height is suppressed; a smaller value is posted just
like a larger value.

`ResizeObserver` watches the measurement root as the primary path for image loading,
search/filter changes, pagination, favorite removal/undo, responsive reflow, and other
size changes. Browsers without it use a `MutationObserver` scoped to the root rather
than body. The existing initial, load (including delayed retries), window resize, and
`requestHeight` message paths remain available.

The message contract remains `{ type: "setHeight", height: number, reason: string }`
and the existing `"*"` target origin is unchanged. No Hatena parent/footer code,
LightGallery behavior, favorite/localStorage/undo behavior, search or Japanese
normalization behavior, or Phase 3A metadata code was changed.

## Validation

- `python -m py_compile main.py tests/test_article_extraction.py`: passed.
- `python -m pytest -q`: passed (`43 passed`).
- `node --check assets/gallery.js`: passed.
- `node tests/test_gallery_highlight.js`: passed (`4` cases).
- `node tests/test_gallery_height.js`: passed.
- `git diff --check`: passed.

The lightweight height regression test exercises integer rounding and both a larger
and smaller result, and statically guards the root target, body-padding inclusion,
root `ResizeObserver`, unchanged message type, and removal of viewport-based sources.

## Required production smoke test

Browser E2E was not available in the Codex environment. After deployment:

1. Show many results in top-page search and confirm the iframe grows.
2. Change the search to zero results and confirm the iframe shrinks.
3. Restore the search and confirm the iframe grows again.
4. Reduce results with search/filter on a 五十音 page and confirm it shrinks.
5. Remove a photo from 観察ノート; after the three-second final removal, confirm it shrinks.
6. Undo a removal and confirm the photo and required height return.
7. Open LightGallery and confirm its overlay does not make normal iframe height huge.
8. Close LightGallery and confirm height remains normal.
9. Repeat on PC and Android/iPhone-sized narrow viewports.

Production validation is the remaining risk because parent-frame behavior and browser
layout cannot be fully reproduced by the lightweight Node regression test. If the
deployed iframe still does not shrink, inspect the Hatena parent message handler in a
separate follow-up rather than mixing that change into Phase 3A.5.

---

# Phase 3A handoff: shadow article-text metadata extraction (preserved)

## Baseline and boundary

Phase 3A started from the required baseline
`771eaa6dd7c52146efeacc5dee132e34798c785d`.

This phase is deliberately **shadow mode only**. The production gallery continues to
use the unchanged `fetch_images(article_files)` result, whose `alt` values remain the
classification keys passed to `generate_gallery(entries, exif_cache)`. Shadow metadata
is never substituted for those entries, so there is no production cutover in Phase 3A.

## Shadow metadata schema

Every image occurrence is retained in article DOM order without global URL deduplication:

- `src`: image URL.
- `detected_label`: original normalized-whitespace label found in article text, or
  `null` before a subject is known.
- `gallery_name`: future classification name; `null` when undetected and `不明` for
  labels containing `?`, `？`, or `不明`.
- `legacy_alt`: current image alt, retained only for comparison and audit.
- `subject_type`: always `review` in Phase 3A.
- `source`: `standalone_text_state`.
- `confidence`: agreement with legacy alt (`high`, `medium`, or `low`).
- `article_path`: source article file path.

## State machine and conservative subject detection

Each article starts with `current_subject = None`. The extractor walks article content
in DOM order. An image-free standalone `<p>` or `<h1>` through `<h6>` updates the state
only when it passes the conservative candidate rule. Each image receives the current
state; images, explanatory prose, and legacy alt never change it. The state persists
through consecutive images and descriptions until a later valid subject label appears.

Candidates are limited to at most 24 characters and principally hiragana/katakana with
safe label punctuation (question marks, middle dot, and brackets). At least three kana
are required. Labels containing `不明` are explicitly allowed. Sentence punctuation,
URLs, date-like text, known Hatena boilerplate, general kanji text, and the short
description terms `幼菌` and `傘の裏` are rejected. These rules intentionally favor
precision over recall for the audit phase.

## Unknown, confidence, and classification rules

- A detected label containing ASCII `?`, full-width `？`, or `不明` keeps its original
  `detected_label` but maps future-facing `gallery_name` to `不明`.
- `high`: a detected label and legacy alt match after trim/whitespace cleanup and
  Unicode NFKC normalization.
- `medium`: a label was detected but differs from legacy alt.
- `low`: no article-text label was detected.
- `subject_type` remains `review` for every record. Phase 3A does not infer mushroom or
  non-mushroom status from text alone.

## Shadow output and failure behavior

The build prints `total_images`, `detected`, `undetected`, `legacy_alt_match`,
`legacy_alt_mismatch`, and `unknown_mapped`. It then prints at most 25 mismatch or
undetected audit rows, followed by an omitted count when necessary.

The full metadata list is written to `cache/phase3-shadow-metadata.json`. The existing
`cache/` ignore rule keeps it out of Git and Pages deployment; EXIF cache and Actions
cache settings are unchanged. Because this is audit-only, an extraction/report/write
exception is clearly logged as `Phase 3A shadow metadata extraction failed: ...`, while
the legacy production build continues rather than losing the existing gallery.

## Validation

- `python -m py_compile main.py tests/test_article_extraction.py`: passed.
- `python -m pytest -q`: passed (`43 passed`).
- `node --check assets/gallery.js`: passed.
- `node tests/test_gallery_highlight.js`: passed.
- `git diff --check`: passed.

Coverage includes state persistence, consecutive images, intervening descriptions,
subject switching, alt independence, unknown mapping, all confidence levels, review
classification, pre-subject images, short-description rejection, DOM ordering, summary
counts, bounded reports, JSON persistence, shadow failure isolation, unchanged legacy
fixture output, and identity of the legacy entries passed into production generation.

## Phase 3B recommendation

Before any cutover, run Phase 3A against the complete current Hatena data and review the
summary plus bounded audit examples (and the local JSON where available). Phase 3B
should add Hatena category and other corroborating signals to classify records as
`mushroom`, `non_mushroom`, or `review`, tune candidate precision/recall from real-data
results, and only then separately decide whether to replace the alt-based production
classification. UI, workflows, Hatena integration, and production output were not
changed in Phase 3A.

---

# Phase 3B handoff: category-aware shadow classification

## Baseline and boundary

Phase 3B started at `26aa47d6dc90cf120b64589c60b00778b1b74319` and remains
strictly shadow mode. Production still passes the exact `fetch_images(article_files)`
list to `generate_gallery(entries, exif_cache)`, so legacy alt remains its classification
source. No cutover occurred. Phase 3A.5 iframe height code, `assets/gallery.js`, and
`assets/gallery.css` were not changed.

The Phase 3A full-data comparison baseline remains `total_images=948`, `detected=865`,
`undetected=83`, `legacy_alt_match=740`, `legacy_alt_mismatch=125`, and
`unknown_mapped=111`; legacy production had 896 images. Compare the next Actions run
against these values without treating alt as truth.

## Article metadata capture and sidecar

Each Atom entry contributes id, title, category terms, alternate URL, published, and
updated metadata while `fetch_hatena_articles_api()` retains its `list[str]` contract.
Metadata is keyed by normalized article path in
`cache/phase3-article-metadata.json`. A sidecar write error is explicitly logged but
cannot stop successfully fetched article content or production. The existing `cache/`
ignore keeps this and `cache/phase3-shadow-metadata.json` out of Git and Pages.

## Detection and schema

The Phase 3A state machine remains intact: each article starts at `None`; valid
standalone body labels update state; images, prose, and alt never update it. Candidate
validation temporarily strips only allowlisted `仮称` and `広義` parenthetical
annotations, preserving the complete detected label. A conservative two-word Latin
binomial pattern accepts `Lanmaoa angustispora？` but rejects ordinary English. Unknown
mapping for `?`, `？`, and `不明` is unchanged.

Each shadow record now has `src`, `detected_label`, `gallery_name`, `legacy_alt`,
`subject_type`, `source`, `confidence`, `article_path`, `article_title`,
`article_categories`, `article_id`, `classification_reason`, and
`classification_confidence`. Missing sidecar data safely yields no title/id, no
categories, and review classification.

## Category and classification rules

Comparison applies trim plus Unicode NFKC/casefold while preserving original terms.
Initial mushroom signals are `キノコ`, `きのこ`, `菌類`, and `茸`. Initial
non-mushroom signals are `野鳥`, `鳥類`, exact `鳥`, `昆虫`, `植物`, `花`, and `風景`.
These small constants should only grow based on inventory evidence.

No detected label gives `review` / `no_detected_label` / low. A detected label with one
unopposed category direction gives `mushroom` / `mushroom_category` or
`non_mushroom` / `non_mushroom_category`, with high classification confidence.
Conflicting directions give `review` / `conflicting_category_signals` / low, and no
signal gives `review` / `no_category_signal` / low. Alt is never a classifier input.

The existing `confidence` remains body-label versus alt agreement (`high`, `medium`,
`low`). The separate `classification_confidence` measures certainty in subject type.

## Inventory, summary, audit, and isolation

Logs include a top-50 category inventory and uncategorized count; Phase 3A counters;
three subject-type totals; high/low classification totals; empty-alt count; and legacy
production count. A bounded 30-row audit prioritizes undetected, mismatch, review,
conflict, non-mushroom, and detected empty-alt cases, with a separate maximum-20
non-mushroom audit. Any shadow extraction/report/write error is visible and production
continues with its already-created legacy entries.

Validation covered Python compilation, the full pytest suite, JavaScript syntax,
highlight and height regressions, and `git diff --check`. After merge, inspect the real
Actions inventory, detection delta, mismatch delta, all subject-type totals, and audit
examples. Tune only from that evidence; production cutover remains a separate phase.

---

# Phase 3B.1 handoff: evidence separation and weak-match audits

## Baseline and reason for the change

Phase 3B.1 starts from `7f6e35bdab5097d2433e8cc58418def5436c21fc`. The Phase
3B real-data baseline was `total_images=948`, `detected=871`, `undetected=77`,
`legacy_alt_match=768`, `legacy_alt_mismatch=103`, `unknown_mapped=109`,
`subject_type_mushroom=807`, `subject_type_non_mushroom=0`,
`subject_type_review=141`, `classification_high=807`, `classification_low=141`,
`shadow_images_with_empty_alt=52`, `legacy_production_image_count=896`, and
`uncategorized=21 articles`.

The inventory contained `キノコ探索日記=82 articles`. Treating its `キノコ`
substring as image taxonomy caused broad mushroom/high classification and helps explain
the suspicious zero non-mushroom count. Real-data evidence includes a `ミツバアケ`
subject category in an article also categorized `キノコ探索日記`, while an earlier Phase 3A
audit found detected label `コブハクチョウ` with empty alt. Article context must not be
treated as the taxonomy of every image.

## Evidence, matching, and classification

Category evidence is now split into explicitly maintained mushroom context, exact
generic mushroom signals, and exact generic non-mushroom signals. `キノコ探索日記` is
context only. Short strings such as `花`, `鳥`, and `茸` are no longer substring matches.
Because categories remain article-wide, neither context nor a generic mushroom category
alone promotes an image to mushroom/high. An unopposed explicit non-mushroom category is
non_mushroom/high; opposing signals, context-only, generic mushroom-only, missing
signals, and mere subject/category corroboration remain review/low. Reasons are
`no_detected_label`, `mushroom_context_only`,
`explicit_mushroom_category_review`, `explicit_non_mushroom_category`,
`conflicting_category_signals`, `subject_category_match_review`, and
`no_category_signal`.

Each shadow record adds `matched_categories`, `category_match_type` (`exact`,
`normalized`, or `none`), `has_mushroom_context`,
`has_explicit_mushroom_signal`, and `has_explicit_non_mushroom_signal`. Matching is
audit corroboration, not taxonomy. It preserves stored labels/categories and uses only
NFKC, trim/whitespace normalization, removal of allowlisted `(仮称)` / `(広義)`
annotations, and trailing `?` / `？` removal for comparison. Legacy alt is not an input.

## Actions audits and validation after merge

The existing bounded shadow audit is supplemented by a dedicated detected-plus-empty-alt
audit (up to 50), mushroom-evidence A/B/C audit (up to 40), suspicious-label audit (up
to 50), and distinct detected-label aggregation (all labels aggregated, up to 150
printed). The summary adds mushroom-context, category-match exact/normalized/none,
detected-empty-alt, unique-label, context-only-review, and conflict counts. Category
inventory also reports total unique categories, categorized/uncategorized articles,
context articles, explicit non-mushroom articles, and conflicting articles.

After merge, check how mushroom=807 falls and review rises; the actual non-mushroom,
`mushroom_context_only_review`, match/no-match and exact/normalized totals; unique labels;
conflicts; whether the empty-alt audit shows `コブハクチョウ`; whether `ミツバアケ`
stays out of mushroom/high; whether mismatch remains 103 (or understand its change);
and whether production remains 896. Also confirm the unchanged EXIF baseline
896/797/0/99.

Production continues to pass the identical legacy `entries` list from `fetch_images()`
to `generate_gallery()`; shadow failures are logged and isolated. `confidence` still
means detected-label versus alt agreement, independently of `classification_confidence`.
The Phase 3A DOM state machine, Phase 3A.5 iframe JS/CSS, UI, workflows, Hatena markup,
and EXIF code/cache are unchanged.

Future toxicity work remains separate: use the union of the planned mushroom sources
only as a provisional population; distinguish `provisional_poisonous`,
`confirmed_poisonous`, and `unknown`; confirm observed species against authoritative
material; and never infer safe/edible from absence. No toxicity master or spore effect
is implemented in Phase 3B.1.

---

# Phase 3B.2 handoff: static subject taxonomy master foundation

## Baseline and boundary

This clean reimplementation started at `74579938d60d72eb3469311cd18eae3fa21d5ee4` (the Phase 3B.1 merge commit). The local checkout did not contain a `main` ref, but the checked-out commit exactly matched the required main SHA; work proceeded on the new `phase3b2-taxonomy-rebuild` branch without resetting or using the old PR #12 branch. The baseline was **65 passed / 65 collected**.

Phase 3B.1's production Actions baseline remains the comparison point: 948 shadow images, `detected=871`, `undetected=77`, 280 unique detected labels, 779 category matches (`exact=742`, `normalized=37`), and 896 legacy production images. In particular, exact category matches for `コブハクチョウ`, `ヨシガモ`, and `ミツバアケビ` must not imply mushroom classification.

## Taxonomy design and classification

`data/subject-taxonomy.json` is the version-controlled, static source of truth. Builds perform no Wikipedia, search, external taxonomy API, or LLM lookup and use no name/suffix heuristic. Its only eight seeds are five mushroom subjects (`ヤマドリタケモドキ`, `シイタケ`, `ベニテングタケ`, `ドクヤマドリ`, `カエンタケ`) and three non-mushroom subjects (`コブハクチョウ`, `ヨシガモ`, `ミツバアケビ`). Everything else remains `review`.

The loader validates the root, schema version as integer `1`, entry list, required names/types, allowed subject types, aliases, sources, required verification status/notes fields, and all normalized canonical/alias collisions. Expected malformed JSON types—including unhashable lists and dictionaries—are explicitly converted to `SubjectTaxonomyError`, rather than leaking `TypeError`. Normalization is comparison-only: NFKC, trim, whitespace collapse, casefold, allowlisted `(仮称)` / `（仮称）` / `(広義)` / `（広義）` removal, and trailing question-mark removal. It does not remove `の仲間`, `科`, `属`, `sp.`, `cf.`, or unknown annotations. Lookup priority is canonical exact, alias exact, normalized canonical/alias, then none.

Only the taxonomy can produce `mushroom/high/taxonomy_mushroom` or `non_mushroom/high/taxonomy_non_mushroom`. Unmatched labels are `review/low/taxonomy_unmatched`; missing labels are `review/low/no_detected_label`; unavailable taxonomy is `review/low/taxonomy_unavailable`. A missing, malformed, or invalid master retains detected labels and allows the legacy production build to continue.

Each shadow record now has `taxonomy_subject_type`, `taxonomy_canonical_name`, `taxonomy_match_type`, `taxonomy_verification_status`, and `taxonomy_sources`. `gallery_name` is classification-aware: it is always null unless subject type is mushroom; a confirmed mushroom with `?`, `？`, or `不明` maps to `不明`; otherwise its canonical taxonomy name is preferred. Consequently, `unknown_mapped` now counts only taxonomy-confirmed mushroom records mapped to the future gallery's `不明`, and must not be compared with Phase 3B.1's value of 109.

## Independent category audits

Article categories remain corroboration/audit evidence only. Exact/normalized matching, matched categories, mushroom context, and explicit mushroom/non-mushroom signals remain available but never drive taxonomy classification. Category anomaly metrics no longer depend on taxonomy-oriented `classification_reason`.

A category conflict is defined solely as `has_explicit_non_mushroom_signal` AND (`has_mushroom_context` OR `has_explicit_mushroom_signal`). `mushroom_context_only_review` means taxonomy-unmatched `review`, mushroom context true, and both explicit signals false; category exact matching is not required. The shared conflict helper is used by summary and suspicious auditing.

The summary adds master counts, matched/unmatched image and unique-label counts, mushroom/non-mushroom taxonomy image counts, and canonical-exact/alias-exact/normalized match counts. A bounded 50-row matched audit and up-to-300-row unmatched distinct-label audit are emitted. All unmatched distinct labels are also exported to ignored `cache/phase3-subject-taxonomy-candidates.json`; export failure is visible but non-fatal.

## Production and future work

Production remains the legacy-alt path: the exact list object returned by `fetch_images()` is passed to `generate_gallery()`. Taxonomy does not filter or reconstruct it, and `gallery_name` is not used for production grouping. Phase 3A's DOM state machine and Phase 3A.5 iframe shrink implementation are unchanged. Assets, workflow, Hatena header/footer/design/iframe/fixed pages, and EXIF behavior/cache are unchanged.

Taxonomy is not toxicity. No edible/safe/poisonous inference or spore effect was added. Next, humans should verify unmatched candidates against external sources and extend the static master. The intended sequence remains taxonomy completion, Phase 3C production metadata cutover, gallery-top redesign, a separate toxicity master, and only then poison spore effects. Possible later gallery redesign work includes a wider mobile layout, large photo hero/search, compact gojuon navigation, best-shot history with 1–3 monthly photos, today's/random mushroom, quiz, recent finds, and frequently appearing mushrooms; none is implemented here.

---

# Phase 3B.3 Batch 1 handoff: evidence-backed mushroom knowledge master

This batch started at `3b2a8ff217fbe2450b1cb6cde14c1c2bd2d61fee` and introduces an evidence-backed knowledge layer without a production cutover. `data/sources.json` is the eight-record source registry, `data/mushroom-master.json` contains 11 mushroom records, and `mushroom_knowledge.py` validates both masters plus their optional subject-taxonomy links. Facts carry field-level source provenance.

The subject taxonomy now has 18 entries: 15 mushroom and 3 non-mushroom. Its original eight `project_seed` entries are preserved, while ten mushroom labels are newly `externally_verified`. The existing カエンタケ seed and all ten new labels link to their knowledge records. Scientific names in this batch are `source_reported`, never `accepted_verified`, because no accepted-name database check was performed.

Food safety defaults to `unknown`; absence of a poisonous record never means edible or safe. Only ドクツルタケ and カエンタケ are `poisonous_confirmed`, based on the registered Ministry of Health, Labour and Welfare sources. This knowledge is not an eating-safety system.

There is no Phase 3C production cutover and no toxicity UI, color, or spore effect. `main.py`, gallery assets, workflow, Hatena presentation, and EXIF behavior remain unchanged. Later batches should continue evidence-backed expansion, retaining explicit unknown/null values wherever the cited material does not establish a fact.

---

# EXIF ISO regression fix handoff

ISO extraction now checks piexif's supported tags in this order:
`ISOSpeedRatings`, `ISOSpeed`, `StandardOutputSensitivity`, then
`RecommendedExposureIndex`. Tag constants are resolved with `getattr`, and empty
list or tuple values are skipped safely. A photo with no usable ISO value returns
`iso=""` while retaining its other EXIF fields.

The EXIF cache key and format are unchanged. Existing cache hits remain valid, and
the 99 production URLs that previously failed before being cached will therefore be
retried by the next Actions build. Regression coverage exercises every fallback,
missing tag constants, empty sequences, and preservation of the camera, lens,
aperture, exposure, focal length, and date fields when ISO is absent.

---

# Phase 3B.3 Batch 2 handoff: 10 high-impact mushroom subjects

This batch started at `f937a3b38909992bf449ac925b23e505aaf5a5b7` and adds 10 evidence-backed mushroom subjects while preserving the three-layer Phase 3B.3 structure. The source registry grows from 8 to 25 records, the mushroom master from 11 to 21 records, and subject taxonomy from 18 to 28 records. Mushroom taxonomy entries grow from 15 to 25; all 3 non-mushroom entries and all existing records remain unchanged.

The evidence hierarchy used is peer-reviewed original description, government records and guides, university culture collection records, national research institute guidance, and supplementary GBIF/Catalogue of Life data. All 10 scientific names remain `source_reported`; none is promoted to `accepted_verified`.

For アミガサタケ, TUFC 100721 reports *Morchella esculenta*, while TUFC 102132 records 広義アミガサタケ as *Morchella* sp.; the broad name is not an alias and the project does not assert one project-wide accepted identity. For キクラゲ, the Ishikawa and TUFC sources use differing scientific-name treatments, so the master records that nuance and does not assert every blog photo is *Auricularia heimuer*.

`edibility_reported` only records what a source calls edible and never means safe, safe to eat, or medically recommended. ヘビキノコモドキ is `poisonous_confirmed` from the cited government guide, without inferring an unreported toxin. There is no Phase 3C cutover: production remains unchanged on the legacy-alt path. EXIF code and cache behavior are also unchanged.
