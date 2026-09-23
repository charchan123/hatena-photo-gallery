# Phase 2A handoff: EXIF cache persistence

## Purpose and scope

Phase 2A persists `cache/exif-cache.json` between GitHub Actions clean runners, avoids
persisting transient download failures, and exposes cache-use metrics in the build log.
It deliberately does not change gallery rendering, embedded CSS/JavaScript, image
classification, incremental HTML generation, workflow triggers, or deployment behavior.

Work started from Phase 1's merged `main` baseline
`d02dec9a73314b93b386a1bb4a204b7cb8efdd2b`.

The GitHub PR #4 relationship is:

- base: `main`
- head: `codex/github-actionsexif`
- current GitHub commit: `39be8f585b7e8d5d57d6d051b9861cecb332799b`

The local checkout exactly matched that supplied baseline.
A fetch of GitHub `main` was attempted before work, but this environment's outbound
GitHub connection was rejected by its proxy (HTTP 403), so no newer remote ref could be
independently fetched. The baseline commit itself is the Phase 1 merge commit.

## Actions cache design

The workflow uses the split `actions/cache/restore@v4` and `actions/cache/save@v4`
actions for `cache/exif-cache.json`.

- Primary key: `exif-cache-v1-${{ runner.os }}-${{ github.run_id }}-${{ github.run_attempt }}`
- Restore prefix: `exif-cache-v1-${{ runner.os }}-`
- `exif-cache-v1` is an explicit format/version namespace that can be incremented if
  the JSON format or cache policy changes.
- Run ID and run attempt make each successful build's primary key immutable and unique;
  the broad version/OS restore prefix lets a later run select the most recently created
  compatible cache rather than becoming stuck on one fixed key.
- Restore occurs after checkout, Python setup, dependency installation, and the existing
  Secrets presence check, but before `python main.py`.
- Save occurs immediately after `python main.py`. Normal GitHub Actions step semantics
  mean it is not reached when that command fails. The save action uses the restore
  step's `cache-primary-key`, keeping restore and save keys identical.
- Deployment remains `JamesIves/github-pages-deploy-action@v4`, targets `gh-pages`, and
  retains `clean: true`. Push-to-`main` and `workflow_dispatch` remain the only triggers;
  no schedule or deploy-skip logic was added.

## Transient failure policy and metrics

For each unique image URL, an existing dictionary entry (including `{}`) remains a cache
hit and is not downloaded. A successful HTTP 200 response is parsed and stored: actual
EXIF fields are stored when present, while `{}` is intentionally stored for a valid image
with no EXIF so it is not fetched on every run. Non-200 responses and request/parsing-path
exceptions are not added to the cache, allowing the next build to retry them. Existing
cache entries are not migrated or deleted.

Each build prints an `EXIF cache summary` with:

- `total`: unique image URLs in the current input;
- `hits`: URLs already present in the cache;
- `fetched`: successful HTTP 200 image downloads cached during this build;
- `failed`: non-200 responses or exceptions left uncached for retry.

Thus `total = hits + fetched + failed` for the current build.

## Changed files

- `.github/workflows/generate.yml`: restore/save the versioned EXIF Actions cache.
- `.gitignore`: ignore the local `cache/` directory.
- `main.py`: retain only successful downloads and emit cache metrics.
- `tests/test_article_extraction.py`: cover hits, EXIF/no-EXIF HTTP 200 responses,
  HTTP 404/500, exceptions, unique URL handling, and summary counts with mocks.
- `HANDOFF.md`: record the Phase 2A design, validation, and rollout plan.

`HATENA_CHANGES.md` is unchanged because Phase 2A requires no Hatena-side changes.

## Validation results

- `python -m py_compile main.py tests/test_article_extraction.py`: passed (the pre-existing
  embedded JavaScript regex still emits Python `SyntaxWarning` messages).
- `python -m pytest -q`: passed, including all eight Phase 1 tests and the Phase 2A tests.
- `git diff --check`: passed.
- Workflow YAML was parsed with Ruby/Psych and its trigger/step ordering, cache keys,
  deploy action, and `clean: true` were programmatically asserted.

No test used the real image network or Hatena API; EXIF HTTP behavior was mocked.

## Production status

This work has not been merged to `main`, has not changed or pushed `gh-pages`, has not
run a production deployment, and has not changed the Hatena administration screen.

## Performance verification after a future merge

1. Run the merged workflow once. With no compatible persisted Actions cache yet, this may
   be a cold build. Record total job/build duration and the four EXIF summary values.
2. Run `workflow_dispatch` again against the same `main`. It should restore the preceding
   compatible cache and act as a warm build. Compare duration and summary values, with a
   particular focus on increased `hits` and reduced `fetched` counts.
3. Compare both measurements with Phase 1's approximately 18-minute production run.
   Do not assume a fixed target duration: the improvement must be measured because it
   also depends on runner, API, network, and image population conditions.

The next step is review and merge of the Phase 2A PR into `main`, followed by those cold
and warm workflow measurements. Production deployment must only occur through the normal
review/merge process.
