# Phase 3A handoff: shadow article-text metadata extraction

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
