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
