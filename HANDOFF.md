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
# Phase 3B.4 residual gap audit

- Starting SHA: `201b29854f77caba7a2bd76216c6063b01817e5f`.
- Phase 3B.3 Batch 2 Actions baseline: 960 shadow images, 883 detected, 77
  undetected, 315 taxonomy matched, 568 taxonomy unmatched, 255 unmatched
  unique labels, and 896 legacy production images. These are observations, not
  fixed assertions; use the post-merge Actions result as the new measurement.
- This phase is audit-only. Subject detection rules and the `current_subject`
  state machine, taxonomy data, legacy production grouping, EXIF behavior, and
  UI/assets/workflow are unchanged. Production still passes the exact object
  returned by `fetch_images(article_files)` to `generate_gallery(entries,
  exif_cache)`.
- `cache/phase3b4-residual-gap-audit.json` is schema version 1 with `summary`,
  complete `undetected_images`, article-level `undetected_articles`, and all
  distinct `taxonomy_unmatched_labels`. Image indexes are zero-based shadow
  occurrences, so repeated URLs are retained. Surrounding blocks are stored in
  DOM order: previous blocks are the last three before the image (oldest to
  nearest), and next blocks are the first three after it.
- Every undetected occurrence is also emitted as one JSON line prefixed
  `Phase 3B.4 undetected-image audit:`. Diagnostics include containing and
  surrounding blocks, relative position, next valid subject, and legacy-alt
  category corroboration. Legacy alt is audit evidence only and never a
  classification driver.
- Candidate diagnostic reason codes are `accepted_kana_label`,
  `accepted_latin_label`, `accepted_unknown_label`, `empty`, `too_long`,
  `stopword`, `sentence_punctuation`, `url`, `date_like`, `excluded_pattern`,
  `unsupported_annotation`, `unsupported_characters`, and `too_few_kana`.
  The diagnostic result is checked against the unchanged production/shadow
  predicate.
- Decide the ordering and scope of a detection fix, taxonomy Batch 3, and the
  Phase 3C cutover only after reviewing the measured residual audit.

---

# Phase 3B.5 conservative residual subject-detection fixes

- Starting SHA: `122d332ff45387e5356360ca3d8516d067fae7b7`.
- The Phase 3B.4 production measurement was 974 total shadow images, 897
  detected, and 77 undetected: 30 before the first valid subject, 47 in
  articles with no valid subject, and 0 after the first valid subject.
- Three narrowly scoped detector gaps were fixed: an image-containing subject
  block can establish state from its own text (never from image alt), the
  allowlisted trailing operational suffixes `編集中`, days 1–31, and days 1–31
  followed by `撮影` are removed, and Latin binomials followed by `和名無し`
  are validated after that annotation is removed. Operational annotations and
  `和名無し` do not remain in `detected_label`.
- `アルビノ` is a validation-only descriptive annotation and remains in
  `detected_label`. Existing `仮称` and `広義` behavior is preserved. Unknown
  annotations remain rejected.
- `の仲間`, `の残骸`, and `の事について` are not stripped or accepted by a
  new fallback. Legacy alt and category remain audit/corroboration evidence and
  never create a subject.
- The residual audit now uses the same effective candidate helper for its
  first/next-valid-subject calculations while retaining the existing raw
  diagnostics and adding effective candidate fields. Generation, reporting,
  and export failures remain isolated from production.
- Taxonomy, mushroom master, sources, production legacy-alt grouping, EXIF,
  UI/assets, and workflow are unchanged. Phase 3C has not been performed.
- Next: re-audit remaining undetected images in post-merge Actions, apply only
  another justified small correction if needed, then proceed to Batch 3
  taxonomy work and finally Phase 3C.

## Phase 3B.6 / Batch 3 — evidence-backed taxonomy expansion (2026-09-24)

- Starting SHA: `70effb8425a299499e5064af827d2e1777e501cc`.
- Phase 3B.5 production baseline: 974 shadow images, 951 detected, 23 undetected, 332 taxonomy matched, 619 taxonomy unmatched, 268 unmatched unique labels, and 896 legacy production images.
- Added 10 high-frequency mushroom subjects with an exact-current-impact candidate of 73 images: オオワライタケ, アオロウジ, ウラベニガサ, トガリアミガサタケ, ノウタケ, ウコンハツ, エノキタケ, キニガイグチ, コテングタケモドキ, タマゴタケ.
- Evidence inventory changed from 25 to 37 sources; mushroom master from 21 to 31; subject taxonomy from 28 to 38; mushroom taxonomy from 25 to 35; non-mushroom taxonomy remains 3.
- All 10 scientific names are `source_reported`; this batch adds 0 `accepted_verified` names.
- Food-safety policy: オオワライタケ and コテングタケモドキ are `poisonous_confirmed`; the six source-reported edible records (アオロウジ, ウラベニガサ, トガリアミガサタケ, ノウタケ, エノキタケ, タマゴタケ) are `edibility_reported` only and are not project safety determinations; ウコンハツ and キニガイグチ remain `unknown`.
- `Lanmaoa angustispora` and `Lanmaoa angustispora？` remain deliberately on hold pending scientific-only canonical taxonomy design.
- Subject detection and residual-gap audit logic are unchanged. Legacy production, EXIF behavior/cache, UI/assets, and workflow are unchanged. Phase 3C has not been performed.

# Phase 3B.7 / Batch 4 — evidence-backed taxonomy expansion (2026-09-25)

- Starting SHA: `15f03bf62fc2f6e6ab2a0de102b975ea6770dea5`.
- Baseline validation: **205 passed / 205 collected**. Final validation: **215 passed / 215 collected**.
- Evidence inventory changed from 37 to 47 sources; mushroom master from 31 to 41; subject taxonomy from 38 to 48. Mushroom taxonomy grew from 35 to 45 and non-mushroom taxonomy remains 3.
- Added 10 subjects: アラゲキクラゲ, ウラグロニガイグチ, オオキツネタケ, キアミアシイグチ, セイタカイグチ, タマチョレイタケ, ツバアブラシメジ, ホテイシメジ, ミドリニガイグチ, ミヤマタマゴタケ.
- Expected exact-label candidate impact is 50 images if the current article dataset is unchanged. This observation is deliberately not a fixed test assertion.
- All 10 scientific names are `source_reported`; this batch adds 0 `accepted_verified` names and does not infer modern accepted nomenclature from older source names.
- Food-safety policy: five public-source records (アラゲキクラゲ, ウラグロニガイグチ, オオキツネタケ, セイタカイグチ, タマチョレイタケ) are `edibility_reported`, which records only the sources' wording and is not a project safety determination. キアミアシイグチ, ツバアブラシメジ, ホテイシメジ, ミドリニガイグチ, and ミヤマタマゴタケ remain `unknown`; no toxin name is inferred.
- ホテイシメジ uses the Kyoto inventory's source-reported *Ampulloclitocybe clavipes*. JATAFF reports *Clitocybe clavipes*, so the project does not select an accepted nomenclature. JATAFF's alcohol-combination warning is preserved in notes, while the schema status remains `unknown` rather than oversimplifying a conditional risk.
- ツバアブラシメジ remains `unknown` for food safety: the source reports regional food use but also says DNA analysis is needed to establish whether the alpine material and ordinary specimens are fully identical. The project does not generalize edibility across that identity uncertainty.
- Deliberately held labels include 不明, `Lanmaoa angustispora`, `Lanmaoa angustispora？`, ベニタケ, both parenthesis forms of キイロオオフウセンタケ(仮称) and フリルイグチ(仮称), 不明アワタケ, `○○の仲間`, `○○の残骸`, and other provisional, unknown, or overly broad labels. None was added as an alias.
- Protected scope is unchanged: subject detection, residual-gap auditing, `main.py`, knowledge validation code, production/shadow cutover, fetch/generation paths, EXIF and cache, UI/assets/iframe/Hatena markup, and workflow are untouched. Production is still the legacy path, and Phase 3C was not performed.

# Phase 3C.0 — production cutover readiness audit

- Starting SHA: `92e283ea155bc937a0954f8e303a9515ee78bd2c`.
- Baseline: `python -m pytest -q` passed (215 tests); `python -m pytest --collect-only -q` collected 215 tests.
- This phase is audit-only. Phase 3C production cutover has **not** been performed, and production remains the unchanged legacy alt-based path.
- The readiness report is written to `output/phase3c-readiness.json`. Because GitHub Pages deploys the complete `output/` directory, the report can be retrieved for analysis after merge.
- The audit-only candidate consists exclusively of shadow occurrences with `subject_type == "mushroom"` and a non-null `gallery_name`; there is no taxonomy-unmatched promotion, category-driven classification, or legacy-alt fallback.
- Exact `(src, name)` and src-only comparisons use multisets, preserving duplicate occurrences while separating additions/removals from same-src name changes.
- Every distinct taxonomy-unmatched review label is emitted in `blocked_review_labels`, ordered by descending image count and then stable label order, without truncation.
- Final validation commands and results are recorded in the Phase 3C.0 implementation handoff/final response.
- Next: inspect the measured report, then decide separately on taxonomy additions, uncertain-name policy, and whether to perform a future production cutover.

# Phase 3C.1 — hybrid migration preview

- Starting SHA: `7cdaff323f1fffffaaa13faeeb0ee9c127400efb`.
- Baseline validation: `python -m pytest -q` passed **218 tests**; `python -m pytest --collect-only -q` collected **218 tests**. Final validation passed **223 tests**, and collect-only collected **223 tests**.
- Phase 3C.0's 2026-09-25 production observation was 896 legacy images (307 names), 988 shadow images, 454 strict confirmed-mushroom candidates, 504 taxonomy-unmatched review images, 398 exact overlaps, 498 legacy-only occurrences, and 56 candidate-only occurrences. These runtime observations are not fixed test assertions.
- A strict cutover is still inappropriate because it would retain only 454/896 legacy images while 249 distinct review labels remain blocked. This phase is preview/audit-only and performs no production cutover.
- The hybrid policy adopts a confirmed mushroom's non-null `gallery_name`, removes confirmed non-mushrooms, and otherwise preserves an existing legacy occurrence. Only unmatched new confirmed mushrooms are added; new review, undetected, and non-mushroom occurrences are audit-listed but not candidate-published.
- Matching preserves order and multiplicity: shadow indices are queued by `src`, each legacy occurrence consumes the earliest unused index, and remaining shadow occurrences are processed in original order. This relies on legacy and shadow extraction sharing the same `article_files` order and DOM order.
- Review fallback does not promote or rewrite taxonomy: `subject_type == review` and its original `classification_reason` remain intact; only the hybrid production-shaped preview temporarily retains the legacy entry.
- New unverified review/undetected images are not added to the candidate. This intentionally differs from preserving already-published legacy occurrences.
- The complete schema-version-1 audit is generated at `output/phase3c-hybrid-preview.json`, including all renames, additions, removals, fallback/exclusion rows, grouped audits, observed article metadata, and summary metrics.
- Production is still the exact legacy list returned by `fetch_images(article_files)`. The preview entries are never passed to `generate_gallery`, including when preview build/report/save fails.
- Next: inspect the post-merge runtime preview and every article-linked rename, then separately decide whether production cutover is acceptable. Do not cut over merely because the preview exists.

# Phase 3C.2 — subject-boundary safety and guarded hybrid preview

- Starting SHA: `a545cda14e477600441b091a6fdff7d71b81770f`.
- Baseline: `223 passed`; `223 collected`. Final validation: `236 passed`;
  `236 collected`, Python compilation passed, both Node regression scripts
  passed, JavaScript syntax passed, and the protected diff remained empty.
- Phase 3C.1 runtime observation was 925 hybrid images (`+29` versus 896 legacy
  images). Its 33 renames were audited as 15 compatible and 18 conflicting.
  These figures are observations, not test constants.
- Root cause: an accepted subject updated `current_subject`, but a rejected,
  subject-like heading did nothing, allowing a stale subject to leak into later
  images.
- Phase 3C.2 distinguishes accepted subjects, rejected subject boundaries, and
  ordinary prose. A rejected boundary clears `current_subject`; it is not a
  mushroom classification, taxonomy lookup, category inference, alt inference,
  or label transformation.
- The narrow rejected-boundary rules cover short group/remains/about headings,
  multiple-subject separators, unsupported unknown headings, and parenthetical
  possibility/candidate annotations. Sentence prose, URLs, dates, exclusions,
  and stopwords remain ordinary text.
- Shadow rows now retain subject-state/source provenance, last rejected-boundary
  provenance, and surrounding DOM blocks for audit.
- Existing-image renames require the legacy alt and detected label to match under
  `normalize_taxonomy_key()`. Incompatible proposals retain the exact legacy
  occurrence and are emitted as `rename_conflict_manual_review` with DOM context.
- New confirmed mushroom images are added only from an explicitly accepted
  subject state. Images after a rejected boundary and before the next accepted
  subject are excluded and audited separately.
- `phase3c-hybrid-preview.json` is schema version 2. Phase 3C.0 readiness remains
  schema version 1.
- Production remains on the exact legacy `entries` list passed to
  `generate_gallery(entries, exif_cache)`. Phase 3C cutover was not performed.
- Next: inspect the merged report's runtime measurements, then decide separately
  whether a production cutover is safe.

# Phase 3C.3 — guarded hybrid production cutover

- Starting SHA: `982e79feab213c6b10a771c8599c9ca6ec62004b`.
- Baseline: `236 passed`; `236 collected`. Final: `252 passed`; `252 collected`.
- Phase 3C.2 production-data observation: legacy 896 / guarded hybrid 923 / net +27.
- All 896 legacy occurrences remain represented: 881 exact occurrences plus 15 compatible renames.
- The seven rename-conflict occurrences remain on their legacy alts for manual review.
- The candidate adds 27 newly confirmed mushroom occurrences.
- Production now cuts over only to a successfully built and runtime-validated Phase 3C hybrid candidate.
- The runtime validator checks schema, count accounting, rename/new-image safety, conflict preservation, and exact `src` occurrence accounting with `collections.Counter` (including duplicate sources).
- Taxonomy load, shadow extraction/audit, hybrid build, or cutover validation failure selects the exact original legacy list as the production fallback.
- EXIF collection and gallery generation both consume the single selected `production_entries` object.
- `output/phase3c-production-status.json` (version 1) records the active mode, fallback reason, counts, report version, and validation result; failure to save it is isolated from gallery generation.
- Existing `output/phase3c-readiness.json` (version 1) and `output/phase3c-hybrid-preview.json` (version 2) audits remain in place. Preview print/save failures after successful validation do not undo cutover.
- Next: after merge, inspect the deployed production status and generated gallery; if both match the observed accounting and safety expectations, decide whether Phase 3C is complete.

# Phase 3C.3.1 — cutover schema integration hotfix

- Starting SHA: `708976bbbc8a71be208dd9840acb25a4347d8d05`.
- Baseline: `252 passed`; `252 collected`. Final validation: `254 passed`;
  `254 collected`, Python compilation passed, both Node regression scripts
  passed, JavaScript syntax passed, and the protected diff remained empty.
- Post-Phase 3C.3 production observation was a safe `legacy_fallback`: 896
  legacy images, 923 hybrid candidate images, and reason
  `added occurrence is not a mushroom`. The published gallery therefore stayed
  on all 896 legacy images and was not broken.
- Root cause: `_phase3c_shadow_audit_row()` omitted `subject_type`, disconnecting
  the Phase 3C.2 report producer schema from the Phase 3C.3 validator schema.
- The validator remains strict and unchanged. The producer now preserves the
  source `subject_type` in every audit row; it does not infer or coerce values.
- A real `build_phase3c_hybrid_preview()` to
  `validate_phase3c_hybrid_cutover()` integration test fixes the producer and
  validator schema contract for newly confirmed mushrooms.
- After a successful hybrid build, preview reporting and saving now occur before
  validation. A validation failure therefore retains the candidate audit while
  still selecting the exact legacy object; a build failure has no report to save.
- The production status remains schema version 1, and the hybrid preview remains
  version 2. The preview note now points to the production status report instead
  of asserting that production always uses legacy entries.
- Next: after merge, recheck `phase3c-production-status.json` and confirm
  `production_mode == phase3c_hybrid`, `cutover_active == true`, and
  `validation.valid == true`.

# Phase 4A.0 — portal data contract and export

- Starting SHA: `27df6cc2b6082c24f308b61f218afbcbda2df4a3`.
- Baseline validation was 254 passed / 254 collected; final validation is recorded below after implementation.
- Phase 3C production cutover remains complete: the observed hybrid baseline is 923 production occurrences (`phase3c_hybrid`, cutover active), with all Phase 3 safety semantics unchanged.
- Portal data is a supplemental, read-only consumer of the already-selected production occurrences. It does not change production selection, EXIF cache content, gallery generation, index generation, or favorites generation.
- Production builds export `output/portal-data.json` schema version 1 and `output/portal-data-status.json` schema version 1; Pages consequently exposes `/portal-data.json` and `/portal-data-status.json`.
- The contract contains ordered one-to-one observations, deterministic name-grouped subjects, dynamic summaries, and faithful copies of subject taxonomy, mushroom master, and source reference data.
- The no-inference policy is strict: no species, date, location, habitat, season, feature, food-safety, or favorite/ranking values are invented. Capture dates come only from valid `YYYY/MM/DD` EXIF cache dates; article publication timestamps are never substituted.
- No location parsing is performed from article titles, bodies, categories, or other fields.
- Knowledge links require an exact production gallery name to taxonomy `canonical_name`, a taxonomy `subject_type` of `mushroom`, and an explicit valid `mushroom_master_id`. Alias, normalized, punctuation-stripped, broad-sense, and unknown-label matching are prohibited.
- Observation IDs are stable SHA-256 identifiers derived from source URL, source-backed article path, and occurrence ordinal. Duplicate sources are retained and matched through ordered per-source unused occurrence state.
- Matching prefers exact shadow `gallery_name` or `legacy_alt`, never associates confirmed non-mushroom rows, records source-only fallback for audit, and emits shadow-missing observations rather than guessing.
- Portal build, data-save, and status-save failures are isolated and cannot prevent gallery, index, or favorite output generation. A best-effort failure status is emitted where possible.
- UI, CSS, gallery appearance, Hatena iframe behavior, browser favorites, Phase 3 reports, validators, and hybrid selection semantics are unchanged.
- Next: after merge, audit deployed portal data measurements and decide the first Phase 4A.1 portal UI.

# Phase 4A.1 — EXIF撮影月による「季節から探す」

- Starting SHA: `3a90cfbd8b7567877c6f5c7c673237f46cc81ee6`。開始時に `HEAD` との完全一致を確認し、baseline は **266 passed / 266 collected** だった。
- 目的は Phase 4A.0 の `portal-data.json` を初めて UI から利用し、トップページに入口を1つ追加して、春（3–5月）・夏（6–8月）・秋（9–11月）・冬（12・1・2月）から既存 gallery subject を探せるようにすること。
- `season.html` は portal schema v1 の `subjects[].capture_month_counts` だけを source of truth とする。カードには `cover_src`、`gallery_name`、該当撮影月、その季節の観察写真枚数、既存の `safe_filename()` と同じ命名規則による gallery リンクを表示する。
- EXIF月がない subject はどの季節にも配置しない。同じ subject に複数季節の実績があれば各季節へ表示する。不明、`?` / `？` 付き、仮称、広義などの名称も変更・除外しない。記事日時、一般知識、mushroom master の season、location、taxonomy 推測は使わない。
- UI本文には「実際に撮影した写真のEXIF撮影月」であることと、「一般的なキノコの発生時期」ではないことを明記した。白基調、mobile 12px余白、広い写真、余白中心の専用 `season.css` と、操作しやすい4季節タブ用 `season.js` に分離し、既存 gallery CSS/JS、favorites、LightGalleryを変更していない。
- Failure isolation: season UI は、その run の portal export status が `build_ok == true` の場合だけ、直前に正常保存された portal file を読み生成する。portal build/save failure時は stale data を読まず、season load/render/write failureも捕捉して、後続の `generate_gallery`、`generate_index`、`generate_favorite_page` を止めない。
- Changed files: `main.py`, `season_ui.py`, `assets/season.css`, `assets/season.js`, `tests/test_season_ui.py`, `HANDOFF.md`。
- Tests: season境界、日付なし非配置、複数季節、uncertain/provisional name保持、既存galleryリンク、説明文、portal failure時のstale非利用、season failure isolation、portal schema v1とfuture schema拒否、production-selection境界の回帰を追加した。最終件数は **276 passed / 276 collected**。
- Production safety: Phase 3C hybrid候補構築・validator・選択部分の後、既存の単一 `production_entries` を portal exportへ渡す構造は維持し、season生成は production selection 完了後の補助出力に限定した。Phase 4A.0 portal schema/versionと `portal_data.py` は変更していない。
- Known issue: `generate_index()` の `hero-world` と `gallery-guide` が `<head>` 内にある既知の invalid HTML は、scope外として維持した。
- Phase 4A.2候補: productionで季節別実測値とmobile操作を監査後、同じ portal contract の範囲内で観察年・撮影月など別の観察導線を小さく追加する。一般発生時期やknowledge seasonを統合する場合は、EXIF観察季節と明確に分離した別設計にする。

# Phase 4A.1.1 — 季節ポータルUI・iframe遷移 hotfix

- **Objective / starting point:** production PC/Android verificationで判明した季節導線の表示、iframe高さ、遷移問題を修正し、五十音別分類ページとUIを統一する。Starting SHA は `bd27d40abd9d2cfadf8b781bb99f285e9a78f5da`、許可された作業ブランチ `work`、clean treeを確認した。Baseline は **276 passed / 276 collected**。
- **Screenshots / production issues:** トップの季節見出しにアイコンがなく説明が技術的、`season.html`だけ独自の `OBSERVATION ARCHIVE`・Georgia/明朝hero・カード・戻るUIだった。PC/Androidともカード一覧や遷移先詳細がiframe途中で切れ、詳細からbrowser backした季節一覧も切れる場合があった。
- **Root cause:** season pageが `season.js` のみを読み、共通 `gallery.css` / `gallery.js` の実コンテンツ高さ計測、ResizeObserver、遅延再計測、requestHeight、HTMLリンクの `scrollToTitle`、カードfavorite同期を利用していなかった。またbfcache復帰時は文書側の `__lastSentHeight` が残る一方、親iframeは遷移先の高さになり得るため、同値dedupeが必要な再送を抑止していた。
- **Shared gallery UI reuse:** season pageは `.aiuo-page`、`.aiuo-title`、`.mushroom-list`、`.mushroom-card`、`.mushroom-card-thumb`、`.mushroom-card-name`、`.card-fav`、`.back-btn` と `gallery.css` / `gallery.js` を直接再利用する。季節固有CSSは説明、4タブ、季節見出し、撮影月・季節内観察枚数metaの配置だけに縮小した。`.gallery` / `.favorite-gallery` は生成しないため、共通JSのLightGalleryループは起動しない。
- **Height force resend / pageshow design:** `sendHeight(reason, force)` を追加し、通常のResizeObserver/resizeは従来どおり同値dedupeする。force要求は二重requestAnimationFrameの予約中にも失われないよう集約する。loadは即時・800ms・2000ms、pageshowは即時・100ms・800ms・2000msを有限のforce送信とし、`event.persisted` では `pageshow-bfcache` reasonを送る。requestHeightも親の明示要求なのでforce応答する。`setHeight` message shape、`"*"` origin、実content root計測、増減監視は維持した。
- **Browser back / navigation:** bfcache復帰では高さだけをforce再送し、`scrollToTitle` は発火しないためseason内スクロール復元を妨げない。seasonのキノコカードは通常の `.html` anchorなので、既存gallery.jsのclick bridgeが遷移時だけ親へ `scrollToTitle` を通知する。season専用の重複handlerは追加していない。
- **Changed files:** `main.py`, `season_ui.py`, `assets/season.css`, `assets/gallery.js`, `tests/test_season_ui.py`, `tests/test_gallery_height.js`, `HANDOFF.md`。
- **Tests:** トップ文言、shared stylesheet/scriptと既存class群、独自hero削除、撮影月/meta、既存HTML navigation bridge、force/dedupe/pageshow/bfcache/requestHeight/ResizeObserver contractを回帰テスト化した。最終コマンドと件数はcommit時のtransfer reportを参照。
- **Production / portal safety:** Phase 3C candidate build、validator、hybrid/legacy selection、production status schema、`production_entries` identityには触れていない。`portal_data.py` とportal schema v1、observation/matching/taxonomy/EXIF policyも不変。season groupingは引き続き `subjects[].capture_month_counts` のみで、春3–5、夏6–8、秋9–11、冬12/1/2、月なし非配置を維持する。fresh portal成功時だけseason生成するfailure isolationも不変。
- **Known issue:** scope外の `generate_index()` にある `hero-world` / `gallery-guide` のhead内invalid HTMLは変更していない。実ブラウザが利用できない環境では、PC/mobileのproduction iframe実機確認が引き続き必要。
- **Next Phase 4A.2 candidate:** deployment後にPC/Androidでseason→detail→browser backの高さ、親スクロール、favorite星を再監査する。その後、portal schema v1の観察年・撮影月など次の小さな観察導線を検討し、一般的発生時期はEXIF観察季節と明確に分離する。

# Phase 4A.1.2 — shared navigation / top action alignment polish

- **Starting SHA / objective:** `b9242633906edcfbf964a53ad50ed83f5ce6591a` のclean tree、baseline **279 passed / 279 collected** から開始し、本番確認で見つかったbrowser back時の親スクロールとトップの単独action 2件の配置だけを局所修正した。
- **Browser back / history detection:** 共通 `gallery.js` の `pageshow` で `event.persisted === true` をbfcache復帰として扱い、加えて標準の `PerformanceNavigationTiming.type === "back_forward"` を検査する。history traversalの場合だけ親へ `{ type: "scrollToTitle" }` を `"*"` originで送信し、通常の初回 `pageshow` では送らない。通常 `.html` link、back button、breadcrumbの既存click bridgeも維持した。
- **Height resend coexistence:** Phase 4A.1.1の `sendHeight(reason, force)`、通常同値dedupe、load/pageshowの有限force resend、bfcache reason、requestHeight force応答、ResizeObserver、`setHeight` contractを変更せず、pageshowではheight再送とhistory traversal時のscrollを両方実行する。無限pollingは追加していない。
- **Top action alignment:** `.aiuo-links` grid外にある季節リンクと観察ノートリンクだけが `justify-items: center` の対象外だったことが左寄せの原因。両方へ共通 `.feature-action-link` を付け、block + fit-content + auto横marginで中央配置した。通常の五十音 `.aiuo-link` には付与せず、グローバル `.aiuo-link` とgrid配置は不変。
- **Changed files:** `assets/gallery.js`, `assets/gallery.css`, `main.py`, `tests/test_gallery_height.js`, `tests/test_season_ui.py`, `HANDOFF.md`。
- **Tests / safety:** history traversal判定、通常pageshow非送信、pageshow height force、既存HTML/back navigation、`setHeight`、2つの共通action class、五十音class非付与を回帰確認した。Phase 3C candidate/validator/production selection/status schema、`portal_data.py`、portal schema v1、season grouping、taxonomy、master/source、EXIF、observation ID、Hatena API、favorites、LightGalleryは変更していない。
- **Next Phase 4A.2:** deploymentでback/forward時の高さと親スクロール、およびPC/mobileの中央配置を確認後、別スコープとして次の観察導線を検討する。

# Phase 4A.2 — 観察記録ポータル

- **Objective / starting SHA:** `f4e53f9ad90e0f5b801b76b6f188efe8b0fd8466` のclean tree、baseline **280 passed / 280 collected** から、最終構想「キノコ観察ポータルの中に観察ブログもある」に向けた小さな導線として Hatena の探索記事を正式機能「📔 観察記録」に統合した。「観察記録」は実際のブログ記事であり、★保存機能の「📓 観察ノート」とは別物である。
- **Source / eligibility:** current runで正常生成された portal-data schema v1 の `observations[].article` だけを読み、categories listに exact string `キノコ探索日記` がある記事だけを採用する。substring、fuzzy match、titleや一般知識による分類は行わず、81件などの件数もhardcodeしない。
- **Identity / aggregation:** observationを記事単位へ集約し、利用可能な最初の `article_id` → `article_path` → `url` をidentityとする。全identity欠損はskipする。最小`production_index`の`src`をcoverにし、production observation数を写真枚数、stored `gallery_name` の未加工distinct数を種類数とする。
- **Chronology / no inference:** 正常なISO `article.published`だけをUTC時刻として比較して新しい順にし、invalid/missingは後方でidentityによるdeterministic orderにする。`updated`、EXIF `capture.date`、title内の日付は順序に使わない。publishedは記事公開日であり観察日ではない。titleから日付や場所を解析・修正せず、verbatim値をHTML escapeして表示する。
- **UI / navigation:** `records.html` は shared `gallery.css` / `gallery.js`、`.aiuo-page`、`.aiuo-title`、`.back-btn` と観察記録固有の `records.css` を使う。白基調のresponsive 3列/1列article cardsにcover、公開日、title、写真枚数、種類数を表示し、一覧先頭だけbuild日時非依存の`NEW`を付ける。有効URLのcardはescaped `article.url`へ `target="_top"` で移動し、URLを推測しない。URLなしは非clickable cardとする。戻るリンクは通常の`index.html` back buttonで、共通iframe height / ResizeObserver / pageshow / bfcache / scroll bridgeを再利用しexternal用handlerは追加しない。
- **Top preview:** 季節から探すの直後、観察ノートの前に、同一のsorted article modelの先頭3件を表示する。先頭だけ`NEW`、各articleは`target="_top"`、`観察記録をもっと見る`は `records.html` と共通 `.feature-action-link` を使う。recordsが空ならsectionを一切出さずbroken linkを防ぐ。
- **Failure isolation / build order:** portal export成功statusのcurrent runだけfresh portal fileを読み、season生成後にrecordsをbest-effort生成する。portal failureではstale fileを読まずrecords.html/previewを作らない。records load/render/write failureは`[]`へ隔離し、その後のgallery/index/favoriteおよび既存seasonを止めない。
- **Changed files:** `records_ui.py`, `assets/records.css`, `main.py`, `tests/test_records_ui.py`, `HANDOFF.md`。`portal_data.py`、portal schema/version、Phase 3C candidate/validator/hybrid・legacy selection/status/production identity、observation/shadow/taxonomy、3 data files、EXIF、season grouping/policy、Hatena retrieval、favorite、LightGallery、Actions workflowは変更していない。
- **Tests / production validation:** exact category、identity fallback/skip、dedup、cover/count、published chronology、invalid order、no inference/escaping、schema rejection、shared assets/back/target、latest-only NEW、top latest3/optional section、portal/records failure isolationを追加した。productionでは `phase3c_hybrid`, legacy 896 / production 923 / delta 27、portal observations 923 / subjects 302 / shadow missing 0 / master linked 41、EXIF hits 923、既存season（春49/186、夏86/178、秋163/366、冬48/100）と、実データから得るeligible article数・順序・linksを再確認する。

## Phase 4A.2.1 — Observation records production polish

- **Starting point / findings:** starting SHAは `0d42f4dacef2f28486a79574ef90798e1873e22a`。Phase 4A.2の本番スクリーンショット・実機確認で、トップpreview 3件が縦に大きい、more linkがcardに密着している、NEWが目立たない、metaが記事全写真数に見えること、およびHatenaへの`target="_top"`遷移後にbrowser Backすると古いiframe/index snapshotから観察記録sectionだけが消える場合があることを確認した。
- **Preview / external route:** トップpreviewをpublished newest-firstの先頭3件から先頭1件へ変更した。`.record-list-preview`だけを最大620pxの横長画像＋本文gridにし、小画面では段階的に1列へ戻す。全件`records.html`の`.record-list` card layoutは変更しない。専用marginでmore linkとの間隔を確保し、more linkは`records.html`ではなく明示されたHatena home `https://exsudoporus-ruber.hatenablog.jp/`へ`target="_top"`で遷移する。
- **Category audit / production policy:** 2026年9月19日記事が欠けたroot causeはHatena API metadataの`categories=[]`でありsort bugではない。eligibilityはcategoriesがlistかつexact `キノコ探索日記`を含む場合だけ、という規則を維持し、title/date/location/body/image/URLによるfallback、substring/fuzzy match、9/19 URL特例は追加していない。ユーザーがHatena側でexact categoryを付けた次回buildでは、metadataへ反映されpublished chronologyが同じなら先頭recordになる（件数はhardcodeしない）。
- **9/18 audit / wording:** 9/18記事のshadow画像6枚は、taxonomy unmatchedのreview 3枚（チチタケ、サザナミイグチ、ムラサキヤマドリタケ）、taxonomy mushroom 1枚（アカヤマドリ）、未解決境界2枚で、安全側production採用は実質1枚。このpolicyと`photo_count`（portal production observations）/`subject_count`（stored `gallery_name` distinct）の算出は変更せず、表示だけを「現在の図鑑掲載 N枚・N種類」に明確化した。
- **NEW / accessibility:** sorted recordsの先頭だけを示す既存判定は維持し、表示を`NEW!`、赤橙色・white text・太字へ変更した。1.8秒の穏やかなpulse/glowを追加し、`prefers-reduced-motion: reduce`ではanimationを無効にする。
- **External Back refresh:** 観察記録のarticle cardとtop more linkだけに`.record-external-link[target="_top"]`を付け、click時にsessionStorageの`record-external-return-refresh-v1` markerを保存する。history traversalの`pageshow`でmarkerをconsume（reload前に削除）し、pathnameが `/` 終端または `/index.html` 終端のgallery indexだけを1回reloadする。records/season等のnon-indexやmarkerのない通常navigationはreloadしない。sessionStorage例外は局所的に無視しnavigationを妨げないため、reload loopも発生しない。
- **Height/navigation coexistence:** 既存`sendHeight(reason, force)`、同値dedupe、load/pageshow/bfcache/requestHeight force resend、ResizeObserver、`setHeight` messageと`"*"` origin、history判定、`scrollToTitle`はそのまま残し、marker consume/index-only reloadをhistory traversal branchへ追加した。
- **Changed files:** `main.py`, `records_ui.py`, `assets/records.css`, `assets/gallery.js`, `tests/test_records_ui.py`, `HANDOFF.md`。portal schema v1、Phase 3C hybrid candidate/validator/selection/status、production identity、`portal_data.py`、taxonomy/master/sources、EXIF、season、Hatena API retrieval、favorites、LightGallery、workflowは変更していない。
- **Tests / next validation:** preview 1件、最新だけ`NEW!`、Hatena home external more link、compact/spacing/reduced-motion CSS、wording、exact category、marker set/consume/index-only condition、failure isolationを回帰対象にした。transfer前に全pytest/collect、py_compile、JS syntax/highlight/height、diff check、protected diffを実行する。次回productionではHatena category修正後のmetadata exact category、最新順先頭、desktop/mobile compact表示、外部遷移→Back時の一度だけのindex refreshとheight/scroll bridgeを実機再確認する。
- **Next Phase candidate:** deployment後にdesktop/mobileおよびHatena iframe上でcards、`target=_top`、戻る/高さ、実際のeligible countを監査し、その後もportal schema v1内の別軸を推測なしの独立Phaseとして検討する。

## Phase 4A.3 — 根拠付き図鑑詳細と観察記録 reverse links

- **Objective / starting point:** starting SHA `e33cfe6b3ee2c89eb2cbfcdbe09d9cde0b926a2a` のclean tree、baseline **292 passed / 292 collected** から、写真を主役のまま各詳細を「観察写真＋根拠付き図鑑情報＋登場した観察記事」へ拡張した。free textの特徴からfacetを推測せず、次Phaseのevidence-backed structured feature facetsより先に、既存41 master entries（features 26、habitat 28、season 25、family 36、genus 7、food status known 22）の表示基盤を作った。
- **Source / explicit link policy:** current runで正常生成されたportal-data schema v1の`subjects`、`observations`、`reference_data`だけがsource of truth。knowledgeは`subjects[].mushroom_master_id`の明示linkだけで接続し、gallery名一致、alias、正規化、疑問符除去、学名・一般知識による推測をしない。gallery title identityも変更しない。
- **Knowledge / provenance:** 学名（source-reportedは「資料記載名」）、科、属、特徴、生育環境、「資料に記載された発生時期」、食毒情報、資料記載成分のうち値があるrowだけを表示する。EXIFの実撮影季節とは明示的に区別する。表示情報のsource IDsをdedupし、既知sourceのorganization/titleと、存在する場合だけURLを`target=_blank rel="noopener noreferrer"`で示す。不明sourceを補完しない。
- **Food safety:** `poisonous_confirmed`は「公的・専門資料に毒性の記載あり」、`edibility_reported`は「資料に食用の記載あり」、`unknown`は「食毒情報は未確認」。安全badgeや安全断定はせず、「採取・調理・飲食の判断には使用しない」「情報がないことは安全を意味しない」という固定注意を全knowledge panelに付ける。
- **Reverse links / chronology:** exact `observation.gallery_name`のarticleだけを、`article_id`→`article_path`→`url` identityでdedupする。`published`だけでnewest-first、欠損・invalidはdated後にidentityで安定化し、`updated`、EXIF、title解析を使わない。公開日・escaped titleをcompact listにし、実URLだけ`target=_top`、URLなしはnon-clickableとする。knowledge未接続subjectでも記事sectionは表示できる。
- **UI / failure isolation:** 既存の写真gallery直後、五十音リンク前に単一knowledge sectionと記事listを挿入し、詳細専用`assets/detail.css`のみ追加した。LightGallery、星、localStorage、spores、EXIF caption、fullscreen、kana links、iframe bridge、back behaviorは既存構造を維持する。portal statusがfresh successでない場合は読まず`{}`、load/model failureも`{}`へ隔離し、gallery/index/favorite/season/records生成を継続する。
- **Changed / protected:** `detail_ui.py`, `assets/detail.css`, `main.py`, `tests/test_detail_ui.py`, `HANDOFF.md`を変更。`portal_data.py`、portal schema、3 reference data files、`.github/workflows`、Phase 3C production selection、season counts logic、records logicは変更していない。
- **Production validation / next:** deploy後に923 observations / 302 subjects / 41 linked subjects、41 panels、unlinkedのpanel不在、896→923（+27）、82 records、既存4季節集計、source/reverse linksを実データ監査する（コードにはhardcodeしない）。次Phaseは根拠付きstructured feature facetsによる「特徴から探す」であり、summary keyword抽出は行わない。

## Phase 4A.3.1 — 図鑑詳細の読者向け仕上げ

- **Starting point / rationale:** required starting SHA `bd88b9db3125ffc0b9b026307f917426c75afcf6` のclean treeと **301 passed / 301 collected** を確認した。Phase 4A.3の本番実機確認で、内部データ管理語を含むfood note、記事公開日とtitle内の観察日らしい日付の混同、多数の記事による縦長化、図鑑情報未接続ページで状態説明がない点が読者向けUX上の課題だったため、presentation layerだけを仕上げた。
- **Reader-facing terminology / source immutability:** `food_safety.notes` はsource-of-truthのまま一切変更せず、render用helperで `source report` / `source` を「出典資料の記載」/「出典資料」、`project`を「本サイト」、`food safety`を「食毒情報」、`schema`を「データ構造」、`edibility status`を「食用可否の区分」へ決定的に変換する。幼時食、アルコール併用、DNA解析、毒成分名を資料にないため追加しないという限定は保持し、unknownを安全とは表現しない。共通warningと完全重複するexact generic noteだけを表示時に省略し、元データには触れない。
- **Scientific name / records:** `source_reported`の学名補足を「出典資料に記載された学名」へ変更した。観察記録はtitleを解析・変更せず、publishedだけを従来どおりnewest-firstに使い、「記事公開日：YYYY年M月D日」（invalid/missingは「記事公開日：不明」）と明示する。最新5件を通常表示し、6件目以降は同じ共通rendererによる`details.subject-record-more`へ全件保持して、件数を動的に表示する。URLがある場合だけ`target=_top`、escapingも維持する。
- **Knowledge pending / no punctuation inference:** knowledgeなしの場合に限り、`classification_counts`の `confirmed_mushroom_identity_uncertain` / `manual_review_name_conflict` / `legacy_review` が1以上、または明示taxonomyがmushroomかつmaster IDなしの場合だけ `knowledge_pending` とする。小さな整理中noticeはその場合だけ写真gallery後・記事前に表示する。名称の `?` / `？`、substring、alias等からは一切推測しない。アシボソアミガサタケ？はproductionのrename-conflict（detected トガリアミガサタケ、legacy/hybrid alt アシボソアミガサタケ？、proposed hybrid alt トガリアミガサタケ）を安全側に保留した明示review countが根拠であり、固有名をコードへhardcodeしていない。
- **Changed files:** `detail_ui.py`, `assets/detail.css`, `tests/test_detail_ui.py`, `HANDOFF.md`。`main.py`を含むその他の実装ファイルは変更していない。
- **Tests / protected areas / production validation:** reader-facing変換、generic note省略と共通warning、意味のある限定、学名文言、公開日ラベル、0/1–5/6/10件、折りたたみ内link、明示pending各経路、punctuation非推論、source object非mutation、CSS responsive contractを回帰化した。Phase 4A.3のexplicit master link、provenance、article identity/chronologyと、Phase 3C selection、portal schema/version、observation/shadow/taxonomy、EXIF、season、records、Hatena API、favorite、LightGallery、Actionsは不変。protectedな `portal_data.py`、3 reference data files、`.github/workflows`のdiffは空であることをtransfer時に確認する。production基準は hybrid、896→923（+27）、portal 923/302/41/shadow missing 0、records 82、season 49/186・86/178・163/366・48/100のままで、値はコードにhardcodeしていない。
- **Next Phase:** deployment後にアカヤマドリ、カエンタケ、アシボソアミガサタケ？のdesktop/mobile表示を確認し、その後の独立Phaseで根拠付きstructured feature facetsによる「特徴から探す」を設計する。free-text keyword推測は行わない。

## Phase 4A.4 — Evidence-backed feature search

- Starting SHA: `6b8af3b55a7413fa9e640b8ee9b29d18e68057c9`.
- Added a versioned curated `feature-facets` schema because reader search facets must not be inferred at runtime from free-text summaries.
- The controlled vocabulary has four ordered groups and 20 facets. Every assignment stores an exact evidence substring and the complete `features.source_ids` provenance set.
- The pure validator enforces schema/version, uniqueness, references, complete summary-bearing-master coverage, exact evidence, source equality, and use of every facet. No regex, NLP, synonyms, names, or article text creates assignments.
- Portal subjects join exclusively through schema-v1 `mushroom_master_id`; gallery names remain the display/detail identity. Multiple selected facets use AND semantics over exact facet IDs.
- The page includes an explicit non-identification disclaimer, accessible toggle buttons, live result count, clear/empty states, responsive cards and stable portal order.
- The top link appears only after successful generation from a fresh portal export. Portal, validation, model, or output failures are isolated and do not stop existing gallery, season, records, detail, favorite, or index output.
- Changed areas: new curated data, `feature_ui.py`, feature CSS/JS, focused Python/Node tests, localized `main.py` integration, and this handoff entry. Protected portal/taxonomy/master/source/workflow data and Phase 3C contracts were not changed.
- Production acceptance should confirm generated `features.html`, derived linked-subject coverage, one- and two-facet AND filtering, zero/clear behavior, responsive layout, local detail navigation, iframe resizing, and unchanged 923-image/41-link/82-record/season contracts.
- Next phase candidates: evidence display on detail pages, accessibility/browser regression automation, or carefully reviewed expansion of the curated vocabulary/data version.

## Phase 4A.4.1 — Feature result card polish

- **Starting point / UX feedback:** started from clean SHA `1c1bff37834e32df8ca8ddc8f519a2e64d703783` with 320 passing/collected tests. Production review found that narrowing conditions did not make the thumbnail reduction sufficiently explicit and that feature cards diverged from the kana/season gallery UI.
- **Shared cards / favorites:** feature results now use `.mushroom-list`, `.mushroom-card`, `.mushroom-card-thumb`, `.mushroom-card-name`, and `.card-fav`, including the existing 400px cover URL convention. This delegates hover, radius, shadow, cover layout, responsive grid, and ☆/★ synchronization to unchanged `gallery.css` / `gallery.js`. Favorite storage and interaction semantics are unchanged.
- **Filtering / height:** feature chips were removed while `data-facets` remains the sole matching input. Filtering explicitly sets nonmatches to `display: none`, so the shared grid compacts and the existing gallery `ResizeObserver` observes the resulting height reduction; no feature-specific postMessage protocol was added. `selected.every(...)` AND matching is unchanged. Visibility is updated before the derived live count and empty state; clear resets selection, buttons, every card, the full derived count, and empty state.
- **CSS / scope:** feature CSS now contains only page, warning, control, button, count, empty-state, and mobile page-padding rules; it no longer defines a competing result grid or card/chip appearance. Changed files are `feature_ui.py`, `assets/features.css`, `assets/features.js`, `tests/test_feature_ui.py`, `tests/test_features_filter.js`, and `HANDOFF.md`.
- **Safety / acceptance:** no feature facet/master/taxonomy/source data, evidence validation, portal/season/records/detail logic, common gallery assets, workflows, favorite keys, or LightGallery behavior changed. Production acceptance remains 26 initial, 9 for `cap_sticky`, 4 for `ring + volva`, 0 plus empty state for `blue_stain + ring`, and 26 after clear, all derived from data rather than hardcoded; desktop/mobile should verify shared hover/star rendering, grid reflow, and iframe shrink.

## Phase 4A.4.2 — Restore feature chips on shared cards

- **Starting point / regression:** started from clean SHA `5869c143cda09dc9db8d81f49dd134c269aa4e57` with **321 passed / 321 collected**. Production review found that Phase 4A.4.1's shared-card conversion unintentionally removed each mushroom's structured feature list and the selected-facet highlighting along with the obsolete feature-specific card layout.
- **Shared cards / restored chips:** retained `.mushroom-list`, `.mushroom-card`, `.mushroom-card-thumb`, `.card-fav`, `.mushroom-card-name`, the 400px cover URL, shared hover/grid behavior, and ☆/★ synchronization. Each card now renders ordered `facet_ids` / `facet_labels` pairs as non-interactive `.feature-chip` spans after its name; no summary parsing, label inference, or sorting was introduced.
- **Selection / filtering:** feature JS toggles `.is-selected` for every card chip whose exact facet ID is in the selected set. Multiple selections highlight multiple matching chips, and clear removes every highlight. Existing `selected.every(...)` AND matching and `display: none` filtering remain unchanged, including live count, empty state, shared-grid reflow, and the existing gallery `ResizeObserver` iframe-height behavior.
- **CSS / mobile:** feature-only CSS adds a compact wrapping chip row and a selected state distinguished by outline, background, and font weight. It does not redefine `.feature-card`, grid columns, card border/shadow/hover/transform, images, or shared responsive columns; long labels wrap without a feature-specific grid.
- **Safety / scope:** favorites remain exclusively owned by unchanged `gallery.js`; no localStorage or star event logic was added. Evidence validation/data, 20 facets, 26 subjects, 72 assignments, explicit master linkage, portal/season/records/detail behavior, and protected data/common gallery/workflow files are unchanged. Changed files are `feature_ui.py`, `assets/features.css`, `assets/features.js`, `tests/test_feature_ui.py`, `tests/test_features_filter.js`, and `HANDOFF.md`.
- **Production acceptance:** verify 26 initial cards with all structured chips; 9 cards and `cap_sticky` highlights; 4 cards with both `ring` and `volva` highlighted; 0 cards plus empty state for `blue_stain + ring`; and 26 cards with no highlighted chips after clear, on desktop and mobile with shared stars, grid reflow, and iframe resizing intact.

## Phase 4A.3.1.1 — Provenance hotfix

- **Starting point:** clean SHA `b340a75a86493c5a32d28de5a92894b9d64b4340` with **321 passed / 321 collected**.
- **Latent issue:** `detail_ui._knowledge()` unconditionally aggregated `name_ja_sources` even though canonical Japanese name is not rendered as a reader-facing knowledge field, so a future name-only source could leak into provenance.
- **Fix / provenance contract:** removed only that unconditional aggregation. Provenance now comes only from master fields that actually render reader-facing values; reference data and the canonical Japanese name UI remain unchanged.
- **Regression:** a dedicated `s_name_only` fixture is attached only to `name_ja_sources`; the test proves that its identifiable source is absent while rendered-field sources remain present once each, with escaping and safe external-link attributes preserved.
- **Changed files:** `detail_ui.py`, `tests/test_detail_ui.py`, and `HANDOFF.md` only. Protected `portal_data.py`, `main.py`, reference data, feature data, workflows, EXIF, gallery, season, records, feature logic, Phase 3C selection, and Hatena API logic are unchanged.
- **Validation:** focused detail tests **21 passed**; full suite **322 passed / 322 collected**; `py_compile`, `git diff --check`, and protected diff checks passed.
- **EXIF Migration:** independent and already complete; externally verified production context is 923 images, EXIF dated 893 / undated 30, and all 65 images in the target 8 articles have capture date and camera data.
- **Manual review:** remains intentionally human-gated at 2 subjects / 7 observations — `アミヒラタケ？` (2) and `アシボソアミガサタケ？` (5); no automatic rename was introduced.
- **Status:** the Phase 4A.3.1 latent provenance issue is resolved before the next major feature phase.

## Phase 4A.5 — 不明キノコ研究室 v1

- **Starting point / baseline:** clean branch `work` at `ea075d8ae005080ed15e4bacf63589b4a7a88e03`; baseline was **322 passed / 322 collected**. The reader concept is a research notebook for unknown and question-mark observations: the investigation process is content, while an explicit identified-history feature remains future work.
- **Eligibility / safety boundary:** an observation is included only when its exact `gallery_name` is `不明`, or contains the literal ASCII `?` or full-width `？`. Punctuation is used solely for research-page inclusion and is never reused for taxonomy, mushroom classification, `knowledge_pending`, master linkage, renaming, confidence, or candidate inference. No AI, taxonomy, `detected_label`, alias, normalization, or general knowledge supplies a candidate.
- **Cases / photos:** one case is exact `gallery_name` plus article identity, selected in strict `article_id` → `article_path` → `url` priority. With no article identity, each `observation_id` remains separate; no image/name similarity merges cases. Every photo is retained and ordered by `production_index`, without inferred cap/stem/underside/young labels.
- **Dates / article context:** dates come exclusively from `observation.capture.date`; distinct valid values are deduplicated, missing dates display `不明`, and title text is never parsed for dates. Article title is shown only as observation context, with valid HTTP(S) URL navigation via `target=_top`; title text is not mined for a place or environment. No environment inference or reconstructed identification history is present.
- **Reader UI / status:** internal classification terms remain hidden. Status priority is `名称確認中` for any explicit `manual_review_name_conflict`, then `未同定` for exact `不明`, otherwise `候補名あり`. Question-mark cases display the exact stored gallery name as `現在の候補名`. The page uses a white, mobile-first layout with about 12px mobile side padding, thin dividers, wrapping long names, a wide responsive photo grid, accessible full-image links, and no nested gray outer panel.
- **Generation / failure isolation:** `research_ui.py` owns the pure case/model builder and renderer. `research.html` and its CSS are generated only from this run's fresh successful portal export; stale portal data is not read. A research-only load/model/write failure returns no summary, adds no index link, and does not stop gallery, season, records, detail, feature, favorite, or index generation. Successful generation reports derived audit counts and passes only its summary to the historically compatible index call.
- **Production acceptance:** externally established current production expectations are **67 cases / 110 eligible photos / 43 exact gallery-name labels / 21 multi-photo cases**. These values are not hardcoded. Acceptance must also conserve all 110 eligible observations exactly once, keep separate `不明` articles separate, include both question-mark widths, and exclude plain `legacy_review` names without a question mark. Local production re-audit was unavailable because API credentials and a fresh 923-observation portal export were absent; focused fixture tests cover the same invariants.
- **Scope / protected files:** changed only `research_ui.py`, `assets/research.css`, `tests/test_research_ui.py`, localized `main.py`, and this handoff. Protected `portal_data.py`, `detail_ui.py`, `feature_ui.py`, `season_ui.py`, `records_ui.py`, master/source/taxonomy/facet data, workflows, EXIF cache logic, Phase 3C selection, Hatena retrieval, favorites, and LightGallery core behavior remain unchanged.
- **Final validation:** focused research tests, full pytest/collection, Python compilation, whitespace validation, and protected-diff checks are required at transfer. No research JavaScript was added.
- **Phase 4A.5.1 candidate:** add an explicit research-history / resolved-case ledger before displaying `不明 → ○○`, candidate A → B → confirmed, `IDENTIFIED!`, resolution date, or evidence. Add structured environment and research-note fields rather than extracting them from article text.

## Phase 4A.5.0.1 — Research page visibility / iframe hotfix

- **Production symptom:** navigating from the gallery index to `research.html` inside the Hatena iframe showed a blank white page even after hard reloads, although the generated research HTML contained all 67 cases / 110 photos.
- **Root cause:** `research.html` reused `gallery.css`, whose shared `body` starts at `opacity: 0` for the gallery fade-in contract, but the research page did not load `gallery.js`, which normally reveals the body and owns the existing `setHeight` iframe-resize protocol.
- **Fix:** research CSS now fails open with `body { opacity: 1; padding: 0; }`, avoiding both invisible content and the inherited 16px body padding. The research page also loads the existing `assets/gallery.js` so the established iframe height synchronization runs after navigation and image/layout changes.
- **Regression guard:** the research design-contract test now requires the gallery JS include plus explicit visible/zero-padding body overrides. Research eligibility, grouping, statuses, dates, article links, production counts, protected data, and Phase 3C logic are unchanged.

## Phase 4A.5.0.2 — 不明キノコ研究室のUI統一 / browser Back hotfix

- **Starting point / baseline / feedback:** clean branch `work` at required SHA `10f627ddb45004e2b3d0b25e13456d6c71ea3bd1`; baseline was **341 passed / 341 collected**. User visual acceptance found inconsistent top-positioned back links, indistinguishable research statuses, no reader-facing comment roadmap, and a research-to-index browser Back path that could restore a stale index without the research entrance.
- **Bottom navigation:** feature and research pages now place the shared `.back-btn` after all results/cases and immediately before `</main>`, in centered `.feature-back` / `.research-back` wrappers with bottom spacing. Both use the exact wording `◀ トップに戻る`; their former `◀ 図鑑トップに戻る` top links are gone. Season and records implementations were not changed.
- **Research status treatment:** reader text and status priority remain unchanged. `未同定` has a muted blue-gray treatment, `候補名あり` a pale yellow/orange treatment, and `名称確認中` a pale rose treatment, each with its own semantic modifier and contrasting text. The labels remain visible, so color is not the only signal.
- **Comments are planned only:** the separate intro notice says that comment/reply support is planned and is intended for identification hints and information. No timing promise, form, textarea, nickname/localStorage behavior, Supabase, database, API, or posting implementation was added. Comments/replies remain deferred until after top-page publication, together with explicit research history.
- **bfcache root cause / contract:** browser history traversal could restore an older cached index DOM created before the research entrance existed. On `pageshow`, a history traversal now reloads any gallery index path (`/` or `/index.html`) with `window.location.reload()` regardless of the external-record flag. Initial navigation/reload does not refresh; history traversal on detail, feature, research, and other non-index pages does not refresh for this purpose. The existing external-record flag cleanup, `scrollToTitle`, forced height resend/retries, `requestHeight`, and `ResizeObserver` paths remain in place. Reload replaces the current document without adding a history entry and its resulting normal reload is not classified as a traversal, preventing a loop.
- **Data/model boundary:** research eligibility (exact `不明` or literal `?` / `？`), case/article identity, `production_index`, capture dates, candidates, status decisions, article links, history absence, and environment non-inference are untouched. Production expectations remain **67 cases / 110 photos / 43 labels / 21 multi-photo cases**, with no count hardcoding or model/grouping changes.
- **Scope / protected files:** changed `research_ui.py`, `feature_ui.py`, `assets/research.css`, `assets/features.css`, `assets/gallery.js`, their focused regression tests, and this handoff. Protected `portal_data.py`, `main.py`, `detail_ui.py`, `season_ui.py`, `records_ui.py`, all listed reference data, workflows, EXIF/cache, Phase 3C selection, Hatena retrieval, favorites format, and LightGallery behavior remain unchanged.
- **Deferred visual work / order:** large-scale research typography and global visual unification are explicitly deferred until all six portal entrances exist. Roadmap order is (1) Phase 4A.5.0.2, (2) Best Shot, (3) final six-entry top-page redesign, (4) pre-publication comprehensive acceptance, and (5) post-publication research history/comments/replies.
- **Final validation:** record focused research, full pytest/collection, Python compilation, Node gallery history/height checks, JavaScript syntax, whitespace, protected-file diff, and final clean Git status at transfer.

## Phase 4A.6 — ベストショット v1

- **Starting point / baseline:** clean branch `work` at required SHA `d5012e5d809c85570db2afb18ac5de0f5c5e81f7`; baseline was **341 passed / 341 collected**.
- **Manual official Best Shot concept:** Best Shot is the photographer's own official, wholly manual curation. It is separate from visitor ⭐ 観察ノート favorites and from おすすめ・新着・珍しい・人気キノコ. Nothing is automatically selected or ranked from favorites, `POPULAR_LIST`, `RARITY_LIST`, recency, AI/photo quality, EXIF, taxonomy, mushroom master, or identification status.
- **Year/month architecture:** entries reference stable `observation_id`; year and month are derived only from the fresh portal observation's `capture.date`. Years and populated months are descending, entries within a month use ascending manual `order`, zero-entry months do not exist in the model/UI, and schema v1 permits at most three selections per year/month. The landing page uses the latest year actually present in selected capture data—not the system year.
- **Data and manual metadata:** `data/best-shots.json` schema v1 stores only stable `selection_id`, `observation_id`, plain-text manual `comment`, optional explicit `location`, and positive manual `order`. It does not duplicate year/month/name/src/capture/article data and never infers location from an article. Production begins deliberately empty; no fictional Best Shot was added.
- **Annual Best:** optional `annual_best` maps a `YYYY` key to one existing `selection_id` from that same capture year. A selection cannot be reused for multiple years. When configured it renders once as a large hero and remains in its normal monthly list with a badge; no empty annual section is rendered.
- **Fresh portal resolution / safety:** resolution requires exactly one matching observation and a valid ISO `observation.capture.date`; gallery name, image source, capture date, and article title/URL all come from the fresh portal object. Display strings and attributes are escaped, comments remain plain text, optional location rows are omitted when absent, and article navigation is emitted only for HTTP(S) URLs with `target="_top"`.
- **Pages / archive / empty state:** successful fresh generation always writes `best-shots.html`; an empty config displays `ベストショットは現在選定中です`. Every selected year, including the latest, gets stable `best-shots-YYYY.html`; the landing page fully displays the latest selected year and links only older years in descending order.
- **Index / failure isolation:** the optional historically compatible `best_shot_summary=None` index input adds the Best Shot entrance only when derived `entry_count > 0`, between research and records. Empty, stale, invalid, model, or render/write failure does not expose the entrance and is isolated from gallery, index, season, features, research, records, detail, favorite, and Phase 3C production. Stale portal data is never loaded for Best Shot generation.
- **Future editor compatibility:** the stable reference/manual-metadata schema is intended to evolve into a secure admin/editor UI where the photographer can select photos in a browser and set comment, location, display order, and Annual Best. This phase includes no admin UI, login/auth, DB, API, Supabase, client-side GitHub write, config form, localStorage Best Shot storage, or other client-side write.
- **Scope / protected files:** implementation is limited to `best_shot_ui.py`, `assets/best-shots.css`, `data/best-shots.json`, `tests/test_best_shot_ui.py`, localized `main.py` integration, and this handoff. Protected portal/detail/feature/season/records/research modules, master/sources/taxonomy/facets, workflows, EXIF/cache, Phase 3C selection, Hatena retrieval, favorites, LightGallery, and existing recommendation logic are unchanged.
- **Final validation:** focused Best Shot tests, full pytest and collection, Python compilation, whitespace validation, protected diff, exact-transfer diff, and final Git status are recorded in the completion report.
- **Remaining roadmap:** (1) Phase 4A.6 Best Shot framework; (2) photographer manually selects real 2025 Best Shots; (3) register actual observation IDs plus comments and locations; (4) six-entry portal finalization; (5) global typography/visual unification; (6) comprehensive pre-publication acceptance; (7) publication; (8) future secure Best Shot admin/editor UI; (9) post-publication research history/comments/replies.

## Phase 4A.7.0 — Top Portal Structural Prototype

- **Starting point / purpose:** started from clean SHA `95b48151cb2a6a0f449704e82c44ed42fce15e21`; baseline was **360 passed / 360 collected**. This phase restructures only the generated index into an inviting, parent-and-child mushroom observation portal before any final AI imagery is introduced.
- **Design contract:** the index now has a scoped `portal-index` body, an intro, and a semantic two-column (one-column mobile) portal navigation with large 16:9-ready visual areas, restrained forest/soil/light gradients, readable lower overlays, HTML text labels, keyboard focus, subtle hover/active feedback, and reduced-motion handling. `portal.css` is loaded only by the index and copied with shared output assets. Mobile index padding is reduced without changing global page padding.
- **Entrances / conditions:** guide and season entrances are always present. Feature, research, Best Shot, and records entrances retain their existing availability conditions. In particular, the production Best Shot configuration remains empty and no Best Shot card or placeholder is emitted at zero entries; a positive derived entry count exposes `best-shots.html` without a code change.
- **Secondary content:** duplicate season/feature/research/Best Shot feature blocks were removed. Search (with stable `#mushroom-guide` target), kana navigation, observation notebook, unchanged recommendation selection, and the latest one-record preview remain, organized under `キノコを調べる` and `もっと楽しむ`. The record portal and preview action now lead to `records.html`; photo fullscreen and ★ notebook guidance remains in a secondary help area.
- **Files changed:** `main.py`, new `assets/portal.css`, focused `tests/test_top_portal.py`, minimally updated index expectations in records/research/season tests, and this handoff entry.
- **Safety:** protected Best Shot production content/schema, research/feature/records/season/detail models, portal data, mushroom knowledge, taxonomy/facet/master/source data, Phase 3C selection, EXIF/article/subject logic, workflows, recommendation selection, favorites persistence, and LightGallery behavior are untouched.
- **Validation:** baseline **360 passed / 360 collected**; final **365 passed / 365 collected**, plus Python compilation and whitespace checks. Generated HTML/CSS is covered by focused output tests. Chromium/Chrome was not available, so screenshots were not captured and no browser package was installed.
- **Transfer / stop point:** the local commit containing this entry is the Phase 4A.7.0 transfer commit (its SHA and deterministic exact-transfer metadata are reported alongside the handoff because a commit cannot contain its own final SHA). Before adding AI visuals, ChatGPT and the user should inspect the desktop and mobile layout on real target devices/inside the Hatena iframe.

## Phase 4A.7.1 — Separate New Top Preview From Existing Gallery

- **Starting point / baseline:** started from clean SHA `77e22e6fe398758a9c5f324cc7a710c2d5a7c508`; baseline was **365 passed / 365 collected**.
- **Existing gallery restoration:** `generate_index()` again uses the Phase 4A.6 presentation from canonical commit `95b48151cb2a6a0f449704e82c44ed42fce15e21`: the original hero, guidance, standalone search/kana/season and conditional feature/research/Best Shot/record sections, observation notebook, and unchanged recommendation selection. It does not load `portal.css` or render portal-only body, intro, grid, or zone headings.
- **New-top separation:** the Phase 4A.7.0 structural prototype is preserved as `generate_new_top()` and writes `output/new-top.html`. It retains the scoped portal shell, intro, six conditionally available entrances, search/kana tools, notebook, recommendations, latest-record preview, guidance, shared `gallery.js`, and relative links. Production's empty Best Shot configuration still omits only that card; it never prevents new-top generation.
- **Build / assets:** the normal build passes the same production-derived grouped gallery, EXIF cache, observation records, feature availability, research summary, and Best Shot summary to both generators. Shared asset copying still publishes `portal.css`, but only `new-top.html` references it.
- **Hatena / roadmap:** the Hatena fixed page `/new-top` already exists, uses the header/footer layout, and has no right sidebar. The production root `/` remains unchanged. AI imagery has not started. Next, embed `new-top.html` into Hatena `/new-top`; then use scoped Hatena CSS to remove the fixed-page white card/margins; then evaluate the real desktop/mobile layout; then create the first AI visual.
- **Files changed:** `main.py`, `tests/test_top_portal.py`, restored Phase 4A.6 index expectations in `tests/test_records_ui.py`, `tests/test_research_ui.py`, and `tests/test_season_ui.py`, plus this handoff. Protected data, model contracts, workflows, selection logic, gallery JavaScript, favorite persistence, LightGallery, and recommendation selection are unchanged.
- **Validation / transfer:** final suite is **366 passed / 366 collected** (one new index separation regression beyond the 365-test baseline); focused portal/season/records/research/Best Shot coverage, Python compilation, whitespace checks, generated-output audit, and protected-diff audit are part of the local transfer. Local commit message is `Phase 4A.7.1: separate new top preview`. Final commit SHA and deterministic binary patch metadata are reported externally because a commit cannot contain its own SHA or the digest of a patch containing those values.

## Phase 4A.7.1.1 — iframe resize DataCloneError hotfix

- **Root cause / fix:** the native `resize` event listener passed `sendHeight` directly, so the browser supplied an `Event` as its `reason`; including that non-cloneable object in the `setHeight` `postMessage` caused `DataCloneError`. The listener now calls `sendHeight("resize")` explicitly, ensuring a string reason.
- **Behavior / scope:** double `requestAnimationFrame` scheduling, `__lastSentHeight`, force sends, `ResizeObserver`, `pageshow`, `requestHeight`, content-height calculation, `setHeight` message shape, `scrollToTitle`, bfcache behavior, favorites, and LightGallery are otherwise unchanged. Only `assets/gallery.js`, its focused height regression test, and this handoff were changed.
- **Validation / transfer:** baseline and final results are **366 passed / 366 collected**, and the Node iframe-height regression checks pass. The regression test rejects a direct `resize` → `sendHeight` listener and requires the explicit `"resize"` reason. Local commit SHA and deterministic exact-transfer patch metadata are reported externally because a commit cannot contain its own SHA or the digest of a patch containing itself; transfer base is `922af22c5c98a43db7db9148353a9854f3b95724`.

## Phase 4A.8.0 — Records-first new-top information architecture

- **Starting point / baseline:** started from clean SHA `e9199eeb0e1e245dc1bf430443511926e48bf745`; baseline was **366 passed / 366 collected**, and the Node iframe-height regression checks passed.
- **Records first:** the latest observation records are promoted to the top of `new-top.html`. The dedicated, compact preview shows the latest three eligible articles in the existing deterministic published-descending order, using each real cover thumbnail, title, published date, and optional excerpt, followed by a `records.html` action.
- **Additive excerpt flow:** article excerpts are extracted from the already-fetched Atom HTML without another HTTP request, preferring the first non-empty paragraph, excluding script/style and image alt text, normalizing whitespace, and truncating to 80 characters only when needed. `excerpt` is stored in the article sidecar and passed additively through portal-data v1 and observation records; schema version and existing required fields are unchanged.
- **New-top scope:** author/child framing, the separate search/kana section, recommendations, and the observation notebook were removed only from new-top. Search, kana, recommendations, notebook/favorites, and all gallery behavior remain on the existing `index.html`, whose generator and presentation are unchanged.
- **Explore structure:** `キノコを探す` follows the records hero. Its lead guide card now links to `index.html`; season remains unconditional, while feature, research, and positive-entry Best Shot cards preserve their existing availability conditions. There is no duplicate records card.
- **Visual direction:** no AI image or other image asset was added. Gradient media areas provide compact desktop/mobile replacement points for later human-free natural-science illustration featuring forest, mushrooms, field tools, and botanical textures rather than people, faces, hands, children, or silhouettes.
- **Files changed:** `main.py`, `portal_data.py`, `records_ui.py`, `assets/portal.css`, `tests/test_article_extraction.py`, `tests/test_portal_data.py`, `tests/test_records_ui.py`, `tests/test_top_portal.py`, and `HANDOFF.md`.
- **Validation / transfer:** focused excerpt/portal/records tests and the required full test, collection, Node, compilation, whitespace, generated-output, and existing-index regression checks are recorded in the completion report. The local commit uses `Phase 4A.8.0: reorganize new-top around latest records`; its exact-transfer metadata is reported externally because a commit cannot contain its own hash.

## Temporary Best Shot preview selections — 2026-09-28

- Added three owner-provided preview selections to `data/best-shots.json`: 2025 Benitengutake #2, 2025 Kiiro-suppontake #3, and 2026 Yamadoritakemodoki #1, all resolved against the current production portal observations before commit.
- The 2025 Benitengutake selection is also the 2025 annual Best Shot. Schema v1 now accepts optional `annual_comment` so the monthly selection comment and annual-hero comment can differ without duplicating an observation.
- Existing manual-selection rules remain unchanged: stable observation references, capture-date grouping, maximum three entries per month, and optional annual selection by `selection_id`.
- These are explicitly temporary preview selections while the final Best Shot curation is still in progress.

## Best Shot visibility hotfix — 2026-09-28

- Best Shot HTML already contained the selected entries, but rendered blank because it loaded `gallery.css` (which initializes `body` at `opacity: 0`) without loading `gallery.js` (which reveals the body and synchronizes iframe height).
- Best Shot documents now load the same shared `assets/gallery.js` used by season, records, research, and features pages.
- No Best Shot selection data, schema, grouping, or comments were changed by this hotfix.

## Phase 4A.8.1 — Separate research / Best Shot and add quiet blog links

- **Starting point / baseline:** started from clean SHA `868243101235823dfaf270279388c5b9a45651b2`; baseline was **367 passed / 367 collected**, and the Node iframe-height regression checks passed.
- **Information architecture:** `new-top.html` keeps the records hero first and the `キノコを探す` section second. Explore now contains only the guide lead, season, and conditionally available feature search. Research and positive-entry Best Shot are emitted below it in a heading-free `portal-independent-links` section, which is omitted when both are unavailable and naturally supports either card alone.
- **Quiet blog links:** a lightweight, border-separated `このブログについて` footer now provides the exact Hatena category links for `自己紹介`, `日常記録`, and `リンク集`. All three links use `target="_top"` to leave the GitHub Pages iframe. They remain compact horizontal links on desktop and stack without large cards or visual media on mobile.
- **Responsive visual scope:** independent cards use two columns on desktop and one on mobile, with a compact visual height and 20–24px separation from explore. No AI image or image asset was generated or added. The records hero, guide lead, and existing index presentation remain unchanged.
- **Banner follow-up:** repository code does not change the Hatena banner or MENU. The next Hatena Design CSS step must be completely scoped to `body.static-page-new-top`: gradually fade roughly the banner's lower 20–25%, preserve the banner image / ベニテングタケ / title, overlap MENU slightly upward while retaining readability, and raise the portal start by approximately 60–80px desktop or 40–55px mobile. Exact values wait for Phase 4A.8.1 production screenshots and must not affect other pages.
- **Protected contracts:** latest three records, excerpts and published-descending order; `records.html`; existing `index.html` guide/search/kana/recommendations/notebook; research and feature conditionals; Best Shot preview/2025 annual best/`annual_comment`/gallery visibility fix; Phase 3C; portal/taxonomy/EXIF data; favorites; LightGallery; iframe synchronization; and workflows are unchanged.
- **Files changed / tests:** changed only `main.py`, `assets/portal.css`, `tests/test_top_portal.py`, and `HANDOFF.md`. Tests cover section order, explore membership boundaries, both independent-card conditions including empty and single-card states, exact blog URLs and three `_top` targets, responsive CSS hooks, existing-index isolation, the full Python suite/collection, Node iframe checks, Python compilation, and whitespace validation.
- **Local transfer:** local commit message is `Phase 4A.8.1: separate portal feature cards`. Exact transfer is the deterministic `git diff --binary 868243101235823dfaf270279388c5b9a45651b2..HEAD`, with gzip `mtime=0`; final commit SHA, patch/gzip hashes and sizes, line count, and full Base64 are reported externally because the commit cannot contain metadata derived from itself.

## Phase 4A.8.2 — Unified new-top visual language and records preview refinement

- **Starting point / baseline:** started from clean SHA `548fdd04c13d766e4f28e125ac1835f47c8c08c3`; baseline was **369 passed / 369 collected**, and the Node iframe-height regression checks passed.
- **Unified panels:** records and explore now share paper panels, border/radius tokens, visual-first hierarchy, restrained gradients, eyebrow/type scales, and replaceable `background-image`-ready visual areas. Explore adds `MUSHROOM GUIDE`; the smaller Research and Best Shot panels add `RESEARCH LAB` and `BEST SHOTS`, with two desktop columns and one mobile column. No AI image or bitmap asset was added.
- **Icons and interaction:** new-top's major emoji were replaced by deterministic inline, monochrome line SVGs with decorative accessibility attributes. Redundant card arrows and arrow CSS were removed. Record thumbnails use 500px Hatena sources, 150×96px desktop and 108×84px mobile crops, and image-only 1.08 hover zoom disabled under reduced motion. Main headings and descriptions are quieter; About stays lightweight footer navigation.
- **Excerpt contract:** excerpts now join meaningful paragraphs in DOM order from already-fetched HTML, normalize whitespace, exclude script/style/noscript/template and image alt text, default to 130 characters, and append an ellipsis only when truncated. No HTTP request, portal schema, record eligibility, or ordering change was introduced.
- **NEW / UPDATE follow-up (Phase 4A.8.3 candidate):** notices must always say what changed. Observation may use authoritative `published` metadata. Best Shot requires explicit additive `selected_at`/`added_at` plus `update_note`; Research requires explicit update-event history for new case, candidate change, and status change. Never infer Best Shot or Research NEW state from capture date or ordering, never permanently show a context-free `NEW`, and omit the badge when update content is unavailable. Existing `records.html` `NEW!` behavior remains untouched for this phase.
- **Contracts / scope:** feature appears only when `feature_search_available`; Research only for truthy `research_summary`; Best Shot only for positive `entry_count`; the independent section exists when either panel exists. Existing index, records-page logic, Best Shot selection/annual comment/2025 annual best, research identity/status, Phase 3C, portal schema, taxonomy, EXIF, search, kana, recommendations, favorites, LightGallery, iframe sync, workflows, and Hatena banner CSS remain unchanged. Banner fade/page-top positioning remains outside this repository.
- **Files / validation / transfer:** changed `main.py`, `records_ui.py`, `assets/portal.css`, focused article/records/top tests, and this handoff. Required full pytest/collection, Node iframe check, compilation, whitespace, generated new-top audit, and available-browser screenshot status are recorded in the completion report. Local commit message is `Phase 4A.8.2: unify new-top visual language`; exact-transfer metadata is reported externally with deterministic gzip `mtime=0`.

## Phase 4A.8.2.1 — Align new-top background with School Archive paper color

- **Portal background:** the scoped `new-top.html` portal page background now uses School Archive's paper color `#f7fcf4`. Panel paper/white backgrounds, visual gradients, borders, shadows, typography, thumbnails, hover behavior, inline SVGs, and AI visual placeholder dimensions and treatment are unchanged.
- **School Archive reference:** its contract is `--paper: #f7fcf4`, `body { background: var(--paper); }`, with a 150px hero-edge `linear-gradient(transparent, var(--paper))` fade.
- **Hatena follow-up:** in the next repository-external Hatena `/new-top` Design CSS step, unify the background to `#f7fcf4`, replace the mask approach with a 150px pseudo-element fade, preserve the banner's overall opacity, and leave the observation-record visual unchanged. Validate content overlap beginning around `-24px` on desktop and `-14px` on mobile.
- **Protected scope:** no Hatena Design CSS is stored or changed here. `main.py` portal structure, generated `new-top.html` structure, `records_ui.py`, Best Shot, Research, feature facets, portal-data schema, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe height sync, `gallery.js`, workflows, `data/*`, AI visual placeholders, inline SVGs, excerpt logic, and thumbnail hover remain unchanged.

## Phase 4A.8.2.2 — Widen new-top content shell

- **Desktop proportions:** the desktop portal shell was widened from 1040px to 1180px, and its horizontal padding increased from 20px to 22px, based on the School Archive desktop content proportions.
- **Protected scope:** the Hatena banner and fade are untouched, and the existing mobile behavior below 680px is unchanged.

## Phase 4A.8.2.3 — Desktop two-column portal composition

- **Desktop composition:** at 900px and wider, the main portal is now a two-column grid with FIELD NOTES on the left and MUSHROOM GUIDE on the right. Their top edges align, while each panel keeps its natural content-driven height.
- **Compact lower row:** Research and Best Shot span the portal grid as a centered, narrower 920px two-column region. About remains understated footer navigation and spans the full portal width.
- **Artwork readiness:** the records and guide visuals are 170px tall on desktop, and the independent-card visuals are 145px tall, giving future cover artwork more balanced proportions. Desktop record metadata now flows title, date, then excerpt for the half-width panel.
- **Responsive / asset scope:** below 900px the DOM order remains FIELD NOTES, MUSHROOM GUIDE, Research, Best Shot, and About in one-column flow; the existing 680px mobile visual heights remain unchanged. The tracked FIELD NOTES artwork `assets/field-notes-observation-final.webp` is retained byte-for-byte but is not referenced or applied yet.
- **Next phase:** after production screenshot review, apply `field-notes-observation-final.webp` as the FIELD NOTES style-anchor artwork. No AI image was applied in this phase.

## Phase 4A.8.2.4 — Apply FIELD NOTES AI artwork

- **Artwork applied:** `assets/field-notes-observation-final.webp` is now the first production AI visual on `new-top`, applied only to the FIELD NOTES / 観察記録 panel. It is the style anchor for the remaining portal artwork, following a watercolor-and-colored-pencil, natural-history field-notes direction with paper texture, moss green, brown mushrooms, and woodland light.
- **Image treatment:** the tracked source asset is used unchanged, with no people, hands, faces, or silhouettes and no overlay, filter, vignette, blur, opacity reduction, additional gradient, or other darkening added. Its initial crop uses `background-size: cover` and `background-position: center center`; screenshot review is required before any later crop adjustment.
- **Responsive / remaining visuals:** the existing 170px desktop and 88px mobile FIELD NOTES visual heights remain unchanged, and mobile inherits the desktop image positioning. MUSHROOM GUIDE, 図鑑を見る, 季節から探す, 特徴から探す, RESEARCH LAB, and BEST SHOTS remain on their existing placeholder gradients until production screenshot review precedes generation or application of further images.
- **Protected scope:** the 1180px shell, desktop two-column layout, 900px breakpoint, centered 920px Research / Best Shot layout, `#f7fcf4` background, Hatena banner/fade, observation content and excerpts, thumbnail behavior, SVG icons, portal data and schema, Best Shot and Research data, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe height synchronization, `gallery.js`, workflows, and `data/*` are unchanged.

## Phase 4A.8.2.4.1 — Deploy FIELD NOTES artwork asset

- **Root cause / deployment fix:** the FIELD NOTES artwork CSS deployed successfully, but the production image initially returned 404 because `copy_shared_assets()` omitted the WebP. The existing `shutil.copy2` path now also copies `field-notes-observation-final.webp` into `output/assets`.
- **Regression guard:** the new-top asset test now verifies that the deployed artwork exists and that its bytes exactly match the tracked source asset.
- **Asset / visual scope:** the source WebP bytes are unchanged. No CSS, layout, crop, visual treatment, portal content, or other asset changed.
- **Starting-tree verification:** local Starting SHA `a66eb047197c77636d084faa3fc69b1b72a72ad3` differs from GitHub merge SHA `f5582c478899bb5c98be7811e8c80935877d5292`, but its tree SHA `fc1f134826698fadb26bfc9026ed22a855246fd4` was verified identical to the GitHub production tree before work began.

## Phase 4A.8.3 — Reference-design portal composition

- **Reference composition:** the portal now follows the adopted two-column reference composition. FIELD NOTES and MUSHROOM GUIDE use matching image-overlay heroes, aligned type hierarchy, spacing, radius, and a restrained bottom gradient; their desktop panels stretch to the same row height without a fixed total panel height.
- **Guide navigation:** the guide introduction respects feature availability, and the former oversized lead-card treatment is replaced by three equal forest-green navigation cards when feature search is available or two equal cards when it is not.
- **Aligned lower row:** Research and Best Shot now use the full 1180px shell's same two-column system and 24px gap, so their outer edges and widths align exactly with the upper panels. Their eyebrow, icon, title, and description overlay a 185px image-ready visual instead of occupying a white lower content area.
- **About / responsive behavior:** About remains lightweight divider-based navigation but uses three balanced desktop columns with short descriptions, changing to one column on mobile. Mobile preserves the order FIELD NOTES, MUSHROOM GUIDE, Research, Best Shot, About; both upper heroes are 150px and lower image-overlay cards are 155px.
- **Artwork and follow-up:** `field-notes-observation-final.webp` remains the unchanged style anchor. No new AI image binary was added; MUSHROOM GUIDE, Research, and Best Shot retain differentiated gradient placeholders ready for a future `background-image`. Their future artwork should use watercolor, colored pencil, natural-history illustration, paper texture, natural light, and subdued earthy color, with no people, hands, faces, silhouettes, fantasy glow, glossy 3D, or HDR. The Hatena banner redesign remains a separate post-merge Design CSS step.
- **Protected contracts:** the latest-three observation feed, 150×96 desktop thumbnails and 500px sources, excerpt/link behavior, all feature/Research/Best Shot conditionals, portal-data schema, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe height synchronization, shared asset deployment, workflows, and `data/*` remain unchanged.

## Phase 4A.8.4 — Deploy Hatena Hero banner assets

- **Starting point:** GitHub production remained at merge commit `890ce0a1b92b3213b3635117a3af54b7a89cab92` (tree `79d7b9144c345beb293ca54f2f05f91af6c27438`). The dedicated branch `phase4a8-4-hero-assets` was created from that production commit; the owner then uploaded the two reviewed image binaries in commit `9b51b84ecbff3e22f97ebd0dcad4ba829be4fd2b`.
- **Hero assets:** adds `assets/hero-amanita-background.webp` as the standalone 2048×408 forest/moss background with no mushroom, text, filename label, preview panel, Hatena header, or UI, and `assets/hero-amanita-cutout.png` as the reviewed real Amanita muscaria transparent PNG. The cutout remains 725×1000 RGBA with a real alpha range of 0–255; the mushroom itself is not AI-redrawn.
- **Exact binary verification:** the uploaded GitHub blobs match the reviewed local files exactly: background blob `53e99e80b3bb1406847823348a820f8bb9cc9e62`, cutout blob `10481fc6d4bd93269d0ea406c6c4ae2fd5d8bfc3`.
- **Deployment:** `copy_shared_assets()` now copies both Hero assets into `output/assets` alongside the existing shared assets so GitHub Pages can serve them after the normal build/deploy.
- **Regression guard:** `tests/test_top_portal.py` verifies source/output existence and byte identity, exact background format/dimensions (WebP, 2048×408), and exact cutout format/dimensions/alpha contract (PNG, 725×1000, RGBA, alpha extrema 0–255). Pillow was already an existing dependency; no dependency was added.
- **Scope:** this phase does not change portal composition, portal CSS, Hatena Design CSS, title text, banner positioning, FIELD NOTES artwork, portal-data, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe height synchronization, workflows, or `data/*`. The Hatena live Hero composition remains the next post-merge Design CSS step.
- **Validation:** GitHub Actions temporary PR57 full-test workflow passed **371/371 pytest**, **371 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `890ce0a...`. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4A.8.5 — Apply remaining portal artwork

- **Starting point:** production `main` is merge commit `287bbfc8a6a2f6052a255bbde4a751873cdb3783`. The owner uploaded the three reviewed lossless WebP artworks to branch `phase4a8-5-portal-artwork` in commit `13466af1a358b7446c5ef31bc12a5885f7697d63`.
- **Exact assets:** `mushroom-guide-final.webp`, `research-lab-final.webp`, and `best-shots-final.webp` are each 2048×768 RGB WebP. Their Git blob SHAs are respectively `aa3a1bb5d8329cab198b10527efec602d338844d`, `21c019d9db48dd8acf2cc7be6bdb851545e5d22a`, and `cf6efb9f88eb17c7a04bc0616bd8f2bf72fea2a4`.
- **Portal application:** MUSHROOM GUIDE now uses `mushroom-guide-final.webp`; Research uses `research-lab-final.webp`; Best Shots uses `best-shots-final.webp`. Existing HTML text, icons, typography, overlay placement, links, and conditional rendering are unchanged.
- **Height contract:** FIELD NOTES and MUSHROOM GUIDE continue sharing the same desktop visual rule `height:190px` and the same mobile rule `height:150px`; no independent guide-height override is introduced.
- **Deployment:** `copy_shared_assets()` now deploys all three new WebPs into `output/assets`.
- **Regression guard:** the top-portal test verifies exact source/output byte identity, WebP format, 2048×768 dimensions, all three CSS image references, and the shared 190px FIELD NOTES / MUSHROOM GUIDE desktop visual-height rule.
- **Scope:** no portal-data schema, record ordering/excerpts, card text size/position, Hatena Design CSS, Hero banner, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe height synchronization, workflow, or `data/*` behavior is changed.
- **Validation:** GitHub Actions temporary Phase 4A.8.5 full-test workflow passed **372/372 pytest**, **372 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `287bbfc8...`. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4A.8.6 — Reference card proportions and artwork correction

- **Starting point:** production `main` is merge commit `9e2a1eedd61b4345460d66a9171aee2783d36cb4` after Phase 4A.8.5 artwork deployment.
- **Reference sizing pass:** desktop portal spacing is tightened toward the adopted reference with a 20px column gap and 18px row gap. Grid items use natural height instead of row stretching, preventing the three MUSHROOM GUIDE entry cards from becoming excessively tall.
- **Guide height contract:** FIELD NOTES and MUSHROOM GUIDE retain the exact same desktop hero-image height of 190px and the existing mobile 150px rule. The overlay eyebrow/title/description typography and positioning on all AI artwork are intentionally unchanged.
- **Record preview:** the protected 150×96 desktop thumbnails remain unchanged. Only row padding/min-height and the final more-link margins are reduced slightly to bring the FIELD NOTES card closer to the reference proportion without changing record content or thumbnail crop.
- **Lower cards:** Research / Best Shot cards use a 155px desktop minimum height and a 20px inter-card gap, with existing overlay typography/placement unchanged.
- **Artwork correction:** the two lower artworks were previously assigned in reverse. Research now displays `best-shots-final.webp` (the microscope/research-desk illustration), while Best Shots displays `research-lab-final.webp` (the sunrise mountain / mushroom illustration). Asset bytes and filenames are unchanged.
- **Scope:** no Hero/Hatena Design CSS, AI-image overlay text size/placement, portal-data schema, record ordering/excerpts, conditional rendering, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe synchronization, workflow, or `data/*` behavior is changed.
- **Validation:** GitHub Actions temporary Phase 4A.8.6 full-test workflow passed **373/373 pytest**, **373 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `9e2a1eed...`. The first temporary run failed only because one pre-existing regression assertion still expected the old 24px gap; that test expectation was updated to the new reference proportions, after which the full suite passed. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4A.8.7 — Equal-height guide card with useful filler

- **Starting point:** production `main` is merge commit `27fba20df9104aa341f3fd88c68c4cc4e3dba2ef` after Phase 4A.8.6.
- **Goal:** make FIELD NOTES and MUSHROOM GUIDE equal-height desktop cards without vertically stretching the three dark green guide entry cards or leaving a large empty area.
- **New useful filler:** MUSHROOM GUIDE gains a compact `こんなときは` helper panel beneath the three entry cards. It maps the user's known clue to the existing destination: name → 図鑑, shooting season → 季節, and (only when feature search is available) unknown name → 特徴.
- **Equal-height behavior:** the desktop two-column portal row returns to `align-items:stretch`. The guide content can flex, but the three entry cards remain on their existing 135px minimum-height contract; the helper panel absorbs the remaining height as meaningful content.
- **One-line guide labels:** only the three dark green guide-entry labels are adjusted: horizontal content padding is reduced to 10px, icon/title gap to 6px, icon size to 22px, title size to 1rem, and `white-space:nowrap` prevents `季節から探す` / `特徴から探す` wrapping. AI-artwork overlay headings and descriptions are untouched.
- **Image-height contract:** FIELD NOTES and MUSHROOM GUIDE remain exactly 190px on desktop and 150px on mobile.
- **Mobile:** the helper panel stacks into a compact single-column list and does not force the desktop minimum height.
- **Scope:** no artwork binaries, AI-image overlay text size/position, Hatena Design CSS/Hero banner, portal-data schema, record ordering/excerpts, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe synchronization, workflow, or `data/*` behavior is changed.
- **Validation:** GitHub Actions temporary Phase 4A.8.7 full-test workflow passed **374/374 pytest**, **374 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `27fba20d...`. The first temporary run failed only because one Phase 4A.8.6 regression assertion still expected `align-items:start`; that expectation was updated to the intentional equal-height `stretch` behavior, after which the full suite passed. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4A.8.8 — Two-column Mushroom Guide actions

- **Starting point:** production `main` is merge commit `886716bc8bd6be54d796f61f126a7817b38d0ed6` after Phase 4A.8.7.
- **Guide simplification:** removes the standalone `図鑑・季節・見た目の特徴。3つの視点から…` intro sentence below the MUSHROOM GUIDE artwork.
- **Desktop layout:** the lower MUSHROOM GUIDE area becomes a two-column matched-row layout. The left column contains the existing three dark-green actions as wide, low horizontal cards stacked vertically; the right column contains a corresponding explanation for each action.
- **Action-card text:** titles stay one line. Each existing action description is also forced to one line with ellipsis safety, reducing vertical card height without removing the description itself.
- **Explanations:** right-side copy is `名前がわかる場合は → 図鑑から名前や写真、五十音で探せます。`, `撮影した時期がわかる場合は → 季節から候補をたどれます。`, and, when feature search is available, `名前がわからない場合は → 傘やヒダなど、見た目の特徴から絞り込めます。`.
- **Equal-height contract:** FIELD NOTES and MUSHROOM GUIDE remain equal-height in the desktop portal row; their AI artwork heights remain exactly 190px desktop / 150px mobile. AI-artwork overlay text size and placement remain unchanged.
- **Mobile:** the two-column guide layout stacks into one column; the three action cards remain compact and the explanation blocks follow below.
- **Scope:** no artwork binaries, Hatena Design CSS/Hero banner, AI-artwork overlay text size/position, portal-data schema, record ordering/excerpts, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe synchronization, workflows, or `data/*` behavior is changed.
- **Validation:** GitHub Actions temporary Phase 4A.8.10 full-test workflow passed **374/374 pytest**, **374 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `9418a985...`. Earlier temporary failures were limited to regression-test formatting / stale exact-string expectations; the implementation itself did not require rollback. The temporary workflow is removed before merge and is not part of the final PR diff.
- **Validation:** GitHub Actions temporary Phase 4A.8.9 full-test workflow passed **374/374 pytest**, **374 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `2c34d1dd...`. The temporary workflow is removed before merge and is not part of the final PR diff.
- **Validation:** GitHub Actions temporary Phase 4A.8.8 full-test workflow passed **374/374 pytest**, **374 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `886716bc...`. The first temporary run failed because an older regression still required the intentionally removed `3つの視点` intro; a second run passed functional tests but exposed only a blank line at EOF; after updating the expectation and normalizing the file ending, the full suite passed. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4A.8.9 — Guide row polish

- **Starting point:** production `main` is merge commit `2c34d1dd12fc478bcfc08006f274c4c2304c692f` after Phase 4A.8.8.
- **Row-based guide layout:** each Mushroom Guide action and its explanation is now one matched row. The row uses a narrow left action card and plain right-side text, which is closer to the FIELD NOTES visual language than the prior pale-green explanation cards.
- **Separators:** the first two guide rows use exactly the FIELD NOTES separator color and thickness: `border-bottom:1px solid #d9ddcf`.
- **Guide-card width:** desktop rows use `grid-template-columns:minmax(220px,.9fr) minmax(0,1.1fr)`, keeping the left card only as wide as needed for a single-line action description while giving the explanation more breathing room.
- **Guide copy:** `図鑑を見る` description changes to `名前、五十音順からキノコを探す`. Season and feature descriptions remain unchanged. All three left-card descriptions remain single-line on desktop.
- **Right-side explanations:** explanatory content is plain text only — no pale-green background, border, or rounded card. Existing headings remain and the body copy stays subordinate in size/color.
- **Equal-height contract:** FIELD NOTES and MUSHROOM GUIDE remain equal-height on desktop; artwork heights remain exactly 190px desktop / 150px mobile. AI-artwork overlay text size and placement remain unchanged.
- **Mobile:** each guide row stacks its action and explanation vertically; separators remain between rows and action descriptions may wrap on narrow screens.
- **Scope:** no artwork binaries, Hatena Design CSS/Hero banner, AI-artwork overlay text size/position, portal-data schema, record ordering/excerpts, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe synchronization, workflows, or `data/*` behavior is changed.

## Phase 4A.8.10 — Match guide rows to FIELD NOTES metrics

- **Starting point:** production `main` is merge commit `9418a985ebf8cdfeed546d836e320cd4c74f1b92` after Phase 4A.8.9.
- **Guide description:** `図鑑を見る` subcopy changes from `名前、五十音順からキノコを探す` to `名前、五十音順から探す`.
- **Exact desktop geometry parity:** each guide action card is exactly **150×96px**, matching the protected FIELD NOTES thumbnail size. Guide rows use the same **18px column gap** and **8px vertical padding** as FIELD NOTES rows.
- **Separator parity:** the guide list starts with the same `1px solid #d9ddcf` top border as FIELD NOTES, and every guide row—including the third/final row—ends with the same separator. Grid tracks use content height with `align-content:start` so separator Y positions are not stretched.
- **Right-side heading typography:** guide explanation headings use the same effective visual tokens as FIELD NOTES record titles: `#24472f`, `1rem`, weight `650`.
- **Right-side body typography:** guide explanation body copy uses the same visual tokens as FIELD NOTES excerpts: `#526056`, `.88rem`, line-height `1.45`.
- **Card shape:** guide action cards use a 10px radius to align visually with FIELD NOTES thumbnails while retaining the existing dark-green action treatment.
- **Mobile:** guide actions return to full width and may wrap on narrow screens; desktop parity values are protected.
- **Scope:** no artwork binaries, Hatena Design CSS/Hero banner, AI-artwork overlay text size/position, portal-data schema, record ordering/excerpts, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe synchronization, workflows, or `data/*` behavior is changed.


## Phase 4A.8.11 — Dedicated guide artwork and indoor Research Lab

- **Starting point:** production `main` is merge commit `fb4bd25cf88cc3082628c948499e20aa7fa51135` after Phase 4A.8.10. PR #64 remains intentionally unmerged while artwork is finalized.
- **Owner-uploaded dedicated assets:** commit `e82a69c72fe04f871d02099909a791c33086751c` adds four reviewed WebPs. Git blob SHAs match the locally approved files exactly:
  - `guide-action-book.webp` — 1698×926, blob `44cae87a97406774325d3aaaca66332642aacdc6`
  - `guide-action-season.webp` — 1698×926, blob `8fd0a862a605cf6796b1326da022ff40fae53e0c`
  - `guide-action-features.webp` — 1698×926, blob `b40dfb684f6dc451f07f9fe55e5856cdce3f72f3`
  - `research-lab-cabin.webp` — 2028×302, blob `75f43e5c4709056a1a47597ab7277825efdc6397`
- **Guide-card mapping:** 図鑑→`guide-action-book.webp`, 季節→`guide-action-season.webp`, 特徴→`guide-action-features.webp`. The existing dark readability overlay and 176×96 desktop card geometry remain.
- **Research Lab replacement:** `不明キノコ研究室` now uses the indoor mountain-cabin illustration `research-lab-cabin.webp`. The card uses `background-position:78% center` so the microscope, right-side work area, window, and forest view dominate while the fireplace is de-emphasized.
- **Deployment:** `copy_shared_assets()` includes all four new WebPs. Regression tests verify source/output byte identity, WebP format/dimensions, dedicated CSS references, and the Research Lab crop position.
- **Protected contracts:** guide-card width 176px, height 96px, row separators and spacing, right-side FIELD NOTES-matched typography, upper portal artwork heights, AI-overlay typography, Best Shots artwork, Hero/Hatena Design CSS, and all data/search/gallery contracts remain unchanged.
- **Scope:** no new generated image beyond the four explicitly reviewed owner-uploaded assets, no portal-data schema, Phase 3C, taxonomy, EXIF, favorites, LightGallery, iframe synchronization, workflow, or `data/*` behavior is changed.
- **Validation:** GitHub Actions temporary Phase 4A.8.11 dedicated-artwork workflow passed **376/376 pytest**, **376 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `fb4bd25c...`. The first dedicated-artwork run failed only because one existing regression still required the now-unused `best-shots-final.webp` CSS reference; after updating that stale expectation, the full suite passed. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4A.8.12 — Artwork brightness polish

- **Starting point:** production `main` is merge commit `058f1fb6644572c0d515fa6058340986f72dae53` after Phase 4A.8.11.
- **Goal:** make AI artwork backgrounds visibly brighter while preserving the existing white overlay text hierarchy and readability.
- **Upper FIELD NOTES / MUSHROOM GUIDE artwork:** the existing shade is reduced from `.78/.25` to `.70/.18`. Heading typography and text-shadow remain unchanged.
- **Three guide action cards:** only the background-art layer receives `brightness(1.12) saturate(1.03)`. The card content gradient and white text remain unchanged, so the artwork opens up without washing out copy.
- **Research Lab / Best Shots:** only the background-art layer receives `brightness(1.10) saturate(1.02)`. The existing content gradient remains unchanged for text contrast.
- **Protected contracts:** dedicated artwork mapping, Research Lab 78% crop, 176×96 guide geometry, row separators/spacing, right-side typography, portal layout, Hero/Hatena Design CSS, data/search/gallery contracts remain unchanged.
- **Scope:** `assets/portal.css`, regression coverage, and HANDOFF only. No artwork binaries are modified.
- **Validation:** GitHub Actions temporary Phase 4A.8.12 artwork-brightness workflow passed **377/377 pytest**, **377 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe height regression checks, feature-filter checks, and `git diff --check` against production `058f1fb6...`. The first run failed only because an older regression prohibited every `filter:` declaration; that stale expectation was narrowed so `blur()` and `sepia()` remain prohibited while the intentional background-only brightness/saturation filters are allowed. The implementation itself did not require rollback. The temporary workflow is removed before merge.

## Phase 4B.1 — Mushroom Guide index PC redesign

- **Starting point:** production `main` is merge commit `1093e0521b4f7ee2dba2b790178241c704b79b24` after Phase 4A.8.12.
- **Goal:** redesign the internal `index.html` ("図鑑を見る") for PC so it visually belongs to the adopted new-top portal while preserving all existing search, favorite, LightGallery, iframe-height, and downstream detail-page behavior.
- **Dedicated stylesheet:** adds `assets/guide.css`, loaded only by `index.html` and scoped under `body.guide-index`. Existing kana/detail/gallery pages continue to use legacy `gallery.css` untouched.
- **Hero:** the guide page now opens with a 1180px-shell watercolor hero using `mushroom-guide-final.webp`, HTML text `MUSHROOM GUIDE / キノコ図鑑`, and an internal `← トップへ` link to `new-top.html`.
- **Primary find area:** name search and gojuon browsing are presented as a two-column desktop block. Existing JS hooks `.index-search-input`, `.index-search-results`, `.search-empty`, and `.index-pagination` are preserved exactly.
- **Search results:** existing gallery.js result rendering is restyled only on `body.guide-index` into a four-column desktop card grid; search URL/query behavior and favorite synchronization are unchanged.
- **Other routes:** season/features/research/best-shots are consolidated into a responsive "ほかの探し方" artwork-card row. Conditional availability rules remain unchanged.
- **Observation:** observation-record preview and favorite observation note are reorganized into a two-column desktop block without changing their existing data or storage behavior.
- **Recommendations:** the existing new/rare/popular selection logic is unchanged and receives a compact three-column PC presentation.
- **Markup cleanup:** invalid visible hero content that previously lived inside `<head>` is removed; all visible guide content is now under `<main id="gallery-content-root">`, which keeps iframe height measurement explicit.
- **Mobile strategy:** this phase is PC-first. Only safe single-column fallbacks at 899px/680px are included so mobile remains usable; visual mobile optimization is intentionally deferred until all PC content pages are complete.
- **Protected contracts:** no detail page, kana page, gallery.js logic, favorite keys, LightGallery integration, data files, portal-data, taxonomy, EXIF, Phase 3C, or Hatena parent-page CSS is changed.
- **Validation:** GitHub Actions temporary Phase 4B.1 guide-index workflow passed **378/378 pytest**, **378 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe-height regression checks, feature-filter checks, and `git diff --check` against production `1093e052...`. The first temporary run failed only because four older tests still asserted the legacy index.html labels/classes; those expectations were updated to verify the preserved routes and behavior in the new markup. The implementation itself did not require rollback. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4B.2 — Unified Guide hero/search/note card

- **Starting point:** production `main` is merge commit `71f7075a099526092028bf54c5488b781004f69e` after Phase 4B.1 / PR #66.
- **Reason for change:** the standalone Mushroom Guide artwork hero visually read like a separate clickable card. The page now treats the artwork as the header of the same white card that contains the primary guide controls.
- **Unified card:** `guide-hub` contains the watercolor hero plus a shared lower body. On desktop, the lower body is `キノコを探す | gray vertical separator | 観察ノート` using tracks `minmax(0,2.15fr) 1px minmax(260px,.85fr)`.
- **Separator:** a neutral gray `#d6ddd4` 1px vertical separator is placed between the search area and Observation Note. Safe tablet/mobile fallbacks convert it to a horizontal rule; full mobile visual optimization remains deferred.
- **Search:** name search, gojuon links, search-result hooks, query behavior, favorites, and pagination remain intact. Search results are three columns within the now narrower left area.
- **Observation Note:** remains directly linked to `favorite.html`, preserves `#favorite-count`, and is moved into the right side of the unified card.
- **Removed from Guide index:** the Observation Record preview card and the entire Recommended Mushrooms card/selection UI are no longer rendered on `index.html`. Their underlying systems and dedicated pages/data are not deleted.
- **Other ways:** season/features/research/best-shot artwork links remain below the unified card with their existing conditional behavior.
- **Protected contracts:** no gallery.js behavior, favorite storage, LightGallery, iframe-height sync, downstream detail/kana pages, records generation page, portal-data, taxonomy, EXIF, Phase 3C, data files, or Hatena parent-page CSS is changed.
- **Validation:** GitHub Actions temporary Phase 4B.2 unified-guide workflow passed **379/379 pytest**, **379 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe-height regression checks, feature-filter checks, and `git diff --check` against production `71f7075a...`. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4B.3 — Typography, Observation Note overlay, and portal-card spacing polish

- **Starting point:** production `main` is merge commit `e47cbc9f344b7fa34d73c1897d2ec8e978cddb13` after Phase 4B.2 / PR #67.
- **Guide hero title:** `キノコ図鑑` no longer forces a Mincho/serif stack. It now inherits the same sans-serif family used by the rest of the Guide UI, including the lower `季節から探す` card typography.
- **Observation Note artwork:** removes the green-tinted overlay over `guide-action-book.webp`. A neutral black transparency (`.18 → .30`) is retained only for white-text readability, so the artwork color is no longer shifted green.
- **Top portal lower-card spacing:** `不明キノコ研究室` and `ベストショット` now use the same eyebrow-to-title spacing as `FIELD NOTES → 観察記録`: effective 6px. The independent-card grid gap is neutralized only for those cards, while title-to-description spacing is preserved explicitly at 5px.
- **Scope:** CSS-only visual polish plus regression coverage and this HANDOFF note. No markup, data, route, search, favorite, LightGallery, iframe-height, taxonomy, EXIF, or Phase 3C behavior changes.
- **Validation:** GitHub Actions temporary Phase 4B.3 visual-polish workflow passed **380/380 pytest**, **380 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe-height regression checks, feature-filter checks, and `git diff --check` against production `e47cbc9f...`. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4C.1 — Seasonal Finder PC redesign

- **Starting point:** production `main` is merge commit `986a885d3f85562df2c042e05add5e137c1db869` after Phase 4B.3 / PR #68.
- **Goal:** redesign `season.html` for PC so it visually matches new-top and the redesigned Guide index without changing the EXIF-only seasonal classification contract.
- **Hero:** adds a watercolor `SEASON FINDER / 季節から探す` hero using the existing dedicated `guide-action-season.webp`, plus a `← 図鑑へ戻る` link.
- **Season picker:** Spring/Summer/Autumn/Winter remain the same JS tab controls and ARIA relationships, but are presented as four large cards in the shared green/white visual system.
- **EXIF disclaimer:** the existing warning remains verbatim and is moved into a pale neutral information strip under the picker. No inference of occurrence season is introduced.
- **Results:** the selected seasonal panel is presented as a white rounded card with a four-column PC mushroom grid. Existing `mushroom-card`, favorite-star hook, detail-page filename rule, and gallery.js navigation bridge remain unchanged.
- **Responsive safety:** tablet falls to three columns and narrow screens to two; full mobile visual optimization remains deferred until the PC content pages are completed.
- **Protected contracts:** `SEASONS`, month mapping, EXIF-only grouping, counts, uncertain/provisional names, detail links, favorite behavior, gallery.js navigation, portal-data schema, taxonomy, EXIF extraction, and Phase 3C are unchanged.
- **Validation:** GitHub Actions temporary Phase 4C.1 season-PC workflow passed **380/380 pytest**, **380 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe-height regression checks, feature-filter checks, and `git diff --check` against production `986a885d...`. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4C.2 — Feature Finder, Research Lab, and Best Shots PC redesign

- **Starting point:** production `main` is merge commit `8b4bced7c147579b433d29957e4bc62fcbd349bc` after Phase 4C.1 / PR #69.
- **Combined scope:** redesigns the remaining three Guide content destinations in one PC-first phase: `features.html`, `research.html`, and `best-shots.html` plus yearly Best Shot archive pages.
- **Feature Finder:** adds a `FEATURE FINDER / 特徴から探す` watercolor hero using `guide-action-features.webp`, a structured filter card, evidence warning, coverage count, and a four-column PC result grid. Existing facet IDs, AND filtering, chips, counts, evidence contracts, and `features.js` hooks remain unchanged.
- **Research Lab:** adds a `RESEARCH LAB / 不明キノコ研究室` cabin hero using `research-lab-cabin.webp`, summary counters, identification warning, coming-soon note, and two-column PC case cards. Inclusion rules, case grouping, status rules, photo/article URLs, candidate-name handling, and derived counts remain unchanged.
- **Best Shots:** adds a `BEST SHOTS / ベストショット` watercolor hero using `research-lab-final.webp`, shared green/white content cards, yearly/archive navigation, and two-column monthly card layout. Manual config validation, monthly limit/order, annual-best logic, comments, locations, capture-date derivation, and archive generation remain unchanged.
- **Navigation:** all three landing pages now use consistent `← 図鑑へ戻る` hero navigation and `← キノコ図鑑へ戻る` footer navigation. Yearly Best Shot pages return to the Best Shots landing page.
- **Responsive safety:** only safe tablet/mobile fallbacks are included; full mobile visual optimization remains deferred until all PC pages are completed.
- **Protected contracts:** no portal-data schema, taxonomy, EXIF extraction, feature evidence data, research inclusion/grouping logic, Best Shot config/data, gallery.js behavior, favorite storage, LightGallery, iframe-height sync, or Phase 3C behavior is changed.
- **Validation:** GitHub Actions temporary Phase 4C.2 content-pages workflow passed **381/381 pytest**, **381 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe-height regression checks, feature-filter checks, and `git diff --check` against production `8b4bced7...`. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4C.3 — Research Lab copy and two-column row alignment

- **Starting point:** production `main` is merge commit `8b9fd97c3d16103eca7b7fbc2ec0a3688e972b2d` after Phase 4C.2 / PR #70.
- **Hero copy:** changes the Research Lab description to `まだ名前が分からないキノコや、候補名を調べているキノコを集めました。`.
- **Overview copy:** replaces the unnatural heading `調べている途中も観察記録` with `名前が分かるまでの調査記録`, and replaces the supporting sentence with `名前が分かるまでに調べたことや、候補になった特徴を記録しています。`.
- **Candidate slot parity:** every Research case now always renders `現在の候補名`. Truly unidentified cases display `-`; candidate/review cases display their current gallery name. This removes the prior structural mismatch between left/right cards.
- **Desktop alignment:** each two-column Research case uses the same five row tracks — header 52px, candidate 52px, facts 42px, photos 190px, article auto — so `撮影日 / 写真枚数`, photo top edges, and `観察記録` start on the same Y positions across paired cards.
- **Photo row:** PC photos stay in a single 190px-high horizontal row. Multiple photos can scroll horizontally rather than adding another vertical row and pushing the Observation Record section downward.
- **Responsive safety:** below 899px the fixed row tracks are removed and the existing natural single-column flow is restored. Full mobile visual optimization remains deferred.
- **Protected contracts:** Research inclusion/grouping/status logic, case ordering, candidate classification, photo/article URLs, counts, portal-data, gallery.js, iframe height, taxonomy, EXIF, and Phase 3C are unchanged.
- **Validation:** GitHub Actions temporary Phase 4C.3 research-alignment workflow passed **382/382 pytest**, **382 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe-height regression checks, feature-filter checks, and `git diff --check` against production `8b9fd97c...`. The temporary workflow is removed before merge and is not part of the final PR diff.

## Phase 4C.4 — Annual Best Shot black presentation and Gojuon page redesign

- **Starting point:** production `main` is merge commit `2f80acc04e6c64e721a79952097710afeece58cd` after Phase 4C.3 / PR #71.
- **Annual Best Shot:** the annual-best section changes from the pale orange treatment to a near-black presentation (`#0c0f0d`) so the selected photograph receives visual priority. The annual hero card also becomes dark (`#111412`) rather than remaining a white card inside a black section.
- **Annual Best typography:** `🏆 YYYY年 年間ベストショット` becomes near-white; the annual badge uses subdued gold; the mushroom name becomes white; metadata uses neutral gray; the comment uses light gray; the article link uses a muted pale green. Monthly/non-annual cards remain unchanged.
- **Gojuon page shell:** generated `あ行.html`–`わ行.html` pages are now complete HTML documents with `body.aiuo-index`, `main#gallery-content-root`, and a dedicated scoped `assets/aiuo.css`.
- **Gojuon hero:** each page gets a `GOJUON INDEX / ●行のキノコ` watercolor hero using the existing `mushroom-guide-final.webp`, plus a consistent `← 図鑑へ戻る` link.
- **Gojuon filters:** existing `.kana-btn`, `.search-input`, `data-kana`, and `data-name` hooks are preserved exactly. The initial buttons and name search are reorganized into one white/green filter panel.
- **Gojuon results:** the existing mushroom cards and favorite-star behavior are preserved, but results use a four-column PC grid inside a rounded white card. Safe fallbacks use three columns on tablet and two on narrow screens; full mobile visual optimization remains deferred.
- **Navigation contract:** mushroom detail links still append `?from=aiuo&kana=●行`, preserving the existing detail-page contextual return behavior and gallery.js scroll/height bridge.
- **Deployment:** `copy_shared_assets()` now includes `aiuo.css`.
- **Protected contracts:** kana normalization, voiced/semi-voiced grouping, search normalization/highlighting, favorites, detail-page filenames, LightGallery, iframe-height sync, portal-data, taxonomy, EXIF, Best Shot selection/config rules, and Phase 3C are unchanged.
- **Validation:** GitHub Actions temporary Phase 4C.4 best-shot/gojuon workflow passed **383/383 pytest**, **383 collected**, Python compilation, `node --check assets/gallery.js`, 4 kana-insensitive highlight cases, iframe-height regression checks, feature-filter checks, and `git diff --check` against production `2f80acc0...`. The temporary workflow is removed before merge and is not part of the final PR diff.
