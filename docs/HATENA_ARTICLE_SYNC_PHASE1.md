# Hatena article/image synchronization — Phase 1

## Scope and starting point

Starting main: `df1a5dfe69a9c01b39d44ee2421fd77b3940ad7a`.
Starting tree: `2697ef1cf5df4a3a8709a216726601014640d9ec`.
The remote matched both values and the working tree was clean before implementation.
Branch: `phase1-hatena-daily-sync-2026-10-12`.

This adds a guarded wrapper around the existing generator, not a replacement for
Phase 3C extraction/classification. Knowledge data, approved facets, Best Shot and
research registries, UI styles/scripts, Hatena parent handlers and the localhost
admin server remain unchanged. PR #103/#104 typography remains untouched.

## Daily execution and persistence

`generate.yml` retains push-to-main and workflow_dispatch triggers and adds
`0 0 * * *` (00:00 UTC, 09:00 JST). Scheduled Actions can be delayed or dropped;
this is not an exact 09:00 service guarantee. GitHub runs schedules on the default
branch. The publication concurrency group serializes builds, with no cancellation
of a running build. No server/database/daemon or ChatGPT scheduled task is added.

Reference: [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Each run reads the last successful `gh-pages` commit via a separate sparse checkout:

* `portal-data.json`: published observations, including legacy IDs and Atom IDs.
* `phase3c-production-status.json`: valid active hybrid publication and photo count.
* `article-sync-snapshot.json`: full published-article/image inventory after bootstrap.

This does not depend on retaining an Actions workspace or an expiring cache. The
snapshot and portal are published together by the existing deployment action;
failed runs do not advance them. The EXIF cache remains the existing performance
cache, not the source of identity or the comparison baseline.

## Photo identity and reference audit

The legacy constructor in `portal_data.py` hashes `src + article_N.html + ordinal`.
Its default behavior is retained for existing standalone callers/tests. The guarded
production export reconciles its candidate before any consumer page is generated:

1. Match by stable Atom `article_id` and **exact** original `src`.
2. Keep every previously published `observation_id` unchanged.
3. Require unchanged multiplicity and ordered labels for repeated identical URLs
   within one article. A changed duplicate occurrence cannot be identified safely.
4. New, explicitly classified photos receive a domain-separated SHA-256 ID over
   `hatena-photo-v2 + Atom ID + exact URL + duplicate ordinal`.
5. Newly published photos require the existing accepted-subject state, high
   classification confidence, and a confirmed named/explicitly unidentified
   mushroom status. Neither names nor knowledge are inferred by the sync wrapper.

Different exact URLs are distinct photos even when their article and position are
the same. Article-local additions plus removals are **possible URL replacements**,
not proof of the same photograph. There is no automatic alias, rewrite or approval.

`best_shot_ui.py` resolves observation IDs exactly once. The final gate invokes its
existing validator and additionally verifies that selected IDs still refer to the
same Atom article and exact URL as the previous publication. EXIF/month/annual
selection checks remain in place.

`research_ui.py` derives research case IDs from the exact name and Atom article ID
when available, and its photos retain observation IDs. The gate invokes the existing
`research_identifications.py` validator. Admin selections use those same observation
and case identities. No admin write endpoint, localhost restriction or CSRF logic
was modified. No registry is automatically edited, including reopened identifications.

Historical unresolved labels remain historical records; they are not silently
reclassified or granted knowledge links. A published label change requires review.

## Complete fetch and comparison

The production workflow uses `python article_sync.py --previous .sync-previous`,
which calls the existing `main.build_gallery(sync_run=...)` with strict API capture.
The unguarded `python main.py` remains available for historical local callers, but
is **not** the daily publication entry point.

The reader follows the entire visible Atom `rel=next` chain. It rejects repeated or
foreign pagination URLs, redirects, non-feed XML, HTTP errors, malformed XML,
missing/duplicate published IDs, missing content/update metadata and unknown draft
state. Requests use a 10-second connection / 60-second read timeout and a 1,000-page
limit. Metadata is committed only after the pagination loop completes. API exceptions
are reduced to fixed error codes, not response bodies or credential-bearing URLs.

Drafts are excluded. Strict capture uses Hatena's rendered `formatted-content` when
present; otherwise only explicitly HTML content is accepted. Plain source markup is
not guessed into public HTML. See [Hatena AtomPub documentation](https://developer.hatena.ne.jp/ja/documents/blog/apis/atom/).

The inventory includes all published articles returned by this feed and all DOM
`img[src]` occurrences, including images that are not production mushroom photos.
Classification comes solely from the existing DOM-order shadow metadata. States
are distinct: named mushroom, explicitly unidentified mushroom, non-mushroom,
unclassified, ambiguous and rejected-boundary conflict. Existing production label
conflicts are also included in the review ledger. No taxonomy data is amended.

Public inventory keys and URLs, updated values, labels and canonical names are
SHA-256 hashes. Classification reasons are allowlisted enums. Titles, author data,
article body, raw API responses, tokens and raw pending image URLs are not added to
these synchronization files. A checksum plus a portal payload hash detects corrupt
or mismatched files; trust comes from the repository's published branch, not from a
claim that these checksums are cryptographic signatures.

Known comparisons report new/deleted articles, new/deleted image occurrences,
updated-time changes and classification/label/reason changes. URL replacement
counts are `possible_url_changes`; `url_changes` is null (UNKNOWN) when same-photo
identity is unproven, rather than a falsely confirmed count. Image reordering alone
is not an addition/deletion, because ordinal is scoped to repeated exact URLs, not
the complete DOM image list.

### Bootstrap and missing baseline

The current public site has no full Atom inventory. Its valid portal can seed a
**compatibility bootstrap**, only if all old published photos and protected references
remain resolvable and all other gates pass. The first full-inventory difference is
UNKNOWN: new/deleted/updated counts are null, never “everything new/deleted.” The
successfully published inventory then becomes the comparison source for the next run.
The pre-inventory site's complete history of non-gallery images cannot be recovered
from portal-data and is not invented.

If the previous portal/status is unavailable, malformed, empty or inconsistent,
or a present inventory is corrupt, the run is blocked. It cannot fall back to an
empty baseline or stale local article files. There is no automatic fresh-site reset.

## Fail-closed gate

The following block publication and retain the old site:

* Incomplete/failed API capture, missing baseline, invalid snapshot or empty harvest.
* Article/photo count below 90% of the previous count (explicit abnormal-drop error).
* Any detected article/image deletion, possible replacement, disappeared published
  photo, changed duplicate multiplicity or published name change. Even smaller
  deletions are held rather than automatically approved in Phase 1.
* A new ambiguous/unclassified legacy-production photo that the existing fallback
  would otherwise assign a name to. Safely excluded shadow images stay excluded;
  they can appear in the pending ledger without entering the gallery.
* Missing protected references or a Best Shot ID pointing to another article/URL.
* Inactive/invalid Phase 3C hybrid, failed portal export, count disagreement, failed
  supplemental page generator or missing essential output page.

Generation occurs in a fresh sibling temporary directory. Only an entirely validated
candidate replaces the local output directory, with a backup for rename failure.
The wrapper exits nonzero on failure; the deployment step has the normal success-only
condition. A report upload uses `always()`, but does not authorize publication.
No retry loop or public mutation API is introduced. The wrapper never writes gh-pages
itself, and it does not operate Hatena.

This intentionally conservative Phase 1 can hold an entire run, including otherwise
safe additions, while a deletion/replacement/new unsafe production label needs review.
It does not quietly publish a partially rewritten registry or keep a stale photograph
under a new source URL. Phase 2 must provide a reviewed resolution procedure.

## Read-only status and Phase 2 handoff

`article-sync-status.json` contains last successful build time, comparison state,
counts, review count/state totals and sanitized error fields. As part of a successful
published snapshot, it refers to the last successful candidate actually published by
the workflow. A failed candidate does not overwrite the public “last success.”

Every attempted wrapper run writes `cache/article-sync-report.json`; the workflow
uploads this sanitized report for 30 days, including failures. It additionally holds
hashed article/image occurrence IDs, allowlisted classification/pending reasons and
possible replacement pairs. A checkout failure proceeds to the wrapper to produce
UNKNOWN + blocked status; a failure before dependencies/wrapper execution may have
no report, and Actions job failure remains the signal in that case.

There is no admin UI change in Phase 1. The localhost administrator can inspect these
JSON files read-only. Phase 2 can resolve hashed IDs against a freshly authenticated
API inventory and existing public portal, display photos, and prepare a human-reviewed
classification/compatibility proposal. Pending operations must recheck the snapshot
hash to avoid approving stale candidates. Do not infer a replacement from position.

Remaining Phase 2 work: secure pending-photo display, explicit classification review,
replacement/deletion approval, audited ID compatibility mapping where proven, stale
review detection, PR creation after human confirmation, and admin UI integration.
There is no hidden bypass flag or automated deletion approval in this phase.

## Validation and limitations

See `ARTICLE_SYNC_PHASE1_VALIDATION.json` for final executed counts.

* Independent fixtures exercise the actual parser, Phase 3C validator, portal export
  and generators with fixture HTTP and EXIF. Bootstrap, a second zero-diff run, a
  newly prepended article and a URL-replacement rejection are tested in sequence.
* Failure fixtures preserve the entire prior output byte-for-byte, including when
  the same directory is used as baseline and output. Partial feed/transport failure,
  missing/corrupt baseline, empty feed, decrease, duplicate ambiguity, broken
  protected selection and supplemental generator failures block publication.
* Read-only published snapshot `f3114e2bbd367047eef04d7a9291303ae7161f4c`:
  all 913 photo IDs survive reversed observation order and changed article paths;
  all 3 Best Shot references and 67 research case IDs remain valid. Actual existing
  generator functions produce 322 HTML files (including favorite), preserving the
  counts 82 / 301 / 67 / 3. This is an offline compatibility/build check, not a new
  live Atom harvest.
* Full Python/JavaScript regression suites cover existing admin localhost/CSRF,
  Phase 3C and HTML/data contracts. Workflow YAML/trigger/order checks are fixtures.
* No live authenticated Hatena request, Actions schedule run or deployment was
  executed in this task. The exact real API result and first scheduled execution
  remain operational checks after human merge; strict validation will block rather
  than guess if their shape or identity is incompatible. No live rollback/deployment
  claim is made; failure retention is demonstrated by local fixtures and workflow
  success gating.

Only the generator entry/integration, fetch health safeguards, workflow, isolated
sync module, regression tests, the dev-only YAML parser dependency and these review documents change. No biological,
provenance, facet, toxicity, registry, Hatena, poison, CSS or typography data changes.
