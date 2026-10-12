# Hatena article/image synchronization — Phase 1

## Scope and starting point

Starting main: `df1a5dfe69a9c01b39d44ee2421fd77b3940ad7a`.
Starting tree: `2697ef1cf5df4a3a8709a216726601014640d9ec`.
The remote matched both values and the working tree was clean before implementation.
Branch: `phase1-hatena-daily-sync-2026-10-12`.

This adds a guarded wrapper around the existing generator, not a replacement for
Phase 3C extraction/classification. Knowledge data, approved facets, Best Shot and
research registries, UI styles, Hatena parent handlers and the localhost
admin server remain unchanged. PR #103/#104 typography remains untouched. The
approved retirement follow-up restricts only favorite rendering to current gallery URLs.

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
2. Keep every retained published `observation_id` unchanged. The only retirement
   is the explicitly approved, commit/hash-bound seven-photo event described below.
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

Drafts are excluded. Strict capture preserves explicitly HTML `content`; non-HTML
source requires explicitly typed HTML `formatted-content`. Plain source markup is
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
remain resolvable (apart from the exact pinned approved retirement) and all other gates pass. The first full-inventory difference is
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
* Any unapproved detected article/image deletion, possible replacement, disappeared published
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
* A later PR #105-only read-only Actions preflight completed authenticated Atom
  pagination but blocked photo compatibility. See the evidence below. No schedule,
  deployment or Hatena write was executed; live API completion is not publication
  readiness. Failure retention is demonstrated by local fixtures and workflow gates.

Only the generator entry/integration, fetch health safeguards, workflow, isolated
sync/retirement modules, regression tests, the scoped favorite visibility/export boundary,
the dev-only YAML parser dependency and these review documents change. No biological,
provenance, facet, toxicity, registry, Hatena, poison, CSS or typography data changes.

## Historical PR #105 preflight — BLOCKER before explicit retirement approval

Starting main remained `df1a5dfe69a9c01b39d44ee2421fd77b3940ad7a`.
Starting PR head was `9e3f8d2d8047767437752ec9100c96c3732cbcf9`.
The existing PR CI showed all three configured Secrets available. A temporary
`pull_request` workflow restricted to PR 105 and same-repository heads used only
`contents: read`, credential-free checkout and Hatena GET requests. It ran the
existing `article_sync.py` / `main.py` in a runner temporary directory. Only
allowlisted counts/codes were logged/uploaded. No API body, article HTML, draft
identity, credential value or generated site was uploaded. The workflow contained
no deployment, write operation, dispatch or cache save and was removed from the
final PR diff after diagnosis, including because this preflight was blocked.

Executed runs:

* [First guarded preflight](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38165841209): complete API fetch, compatibility blocked.
* [HTML representation diagnosis](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38166003032): no image-source difference between raw HTML and formatted HTML in the 110 public articles.
* [Draft-related identity diagnosis](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38166194193): confirmed cause below; head `4770dfa38f1ac2e0910099d16db8855f2be02eb7`.

All three used the read-only publication baseline
`f3114e2bbd367047eef04d7a9291303ae7161f4c`.
The final diagnosis returned:

| Check | Observed result |
| --- | --- |
| Completed Atom pages | 12; terminal `rel=next` absent; metadata save completed |
| Total entries received | 112 |
| Published articles / verified HTML articles | 110 / 110 |
| Excluded drafts | 2 |
| Public article DOM image occurrences | 976 |
| Phase 3C gallery candidate | 906 photos; not approved/published |
| Previous published observations | 913 |
| Missing prior photo keys | 7, all in one currently excluded draft article |
| Missing affected articles from the entire API harvest | 0 |
| Error stage / code | ID reconciliation / `REMOVED_OR_REPLACED_PUBLISHED_PHOTO` |
| Inventory differences | `UNKNOWN`; no previous full Atom inventory |
| Best Shot 3 / research 67 final reference checks | NOT REACHED in this live run |
| Completed observation/guide/top downstream generation | NOT REACHED in this live run |
| Publication / Hatena write | None |

This is not an API transport/response-format failure. All 110 public entries had
explicit `text/html` content and formatted HTML; both representations contained
the same ordered image URL lists. The previous portal contains seven photo keys
whose article is now explicitly `app:draft=yes`. The previous site has no full
article inventory, so whether it was already a draft when historically generated
or was changed to a draft later is unknown. No private article identity/body is
recorded in this report.

The 913-ID preservation requirement therefore **fails**. Do not call the 906-photo
candidate an approved adoption or claim all protected references passed: execution
stopped before final reference validation and page generation. Earlier offline
913/3/67 compatibility tests remain valid fixture evidence, not evidence that this
current API harvest passes. Classification review count 597 is an aggregate of
pending image occurrences and legacy review signals, not 597 new problems; the
bootstrap cannot determine newly changed classification counts.

### Decision and necessary follow-up

**Historical decision at that point: do not merge or enable daily publication.** Including the draft would undo
privacy filtering; deleting/rebinding the seven old photo records or resetting the
baseline would bypass preservation. Neither is authorized. A human must review
publication intent for the affected draft and resolve the legacy-publication
compatibility discrepancy before a new read-only preflight can succeed. The
registered Best Shot/research data remains unchanged. No automatic approval,
force-regenerated ID, alias or knowledge edit was introduced.

This follow-up only adds safe fetch/provenance counts, draft-related compatibility
diagnosis, full-photo preservation counting, and an explicit existing research
case/photo-reference preservation gate. Regression fixtures check complete vs
partial fetch telemetry, hidden draft exclusion, guarded bootstrap counts and an
unregistered research case disappearing. Workflow/bootstrap safety gates were not
weakened, and `generate.yml` is unchanged from the starting PR head.

Final local tests: **670 pytest passed / 670 collected**, **265 focused passed**
(including 64 sync cases); **40 Node test-runner tests passed**, plus direct execution
of all eight JS files. Python compilation, all JS syntax, workflow YAML, workflow
removal, protected-path comparison and `git diff --check`: PASS. Full fixture
builds exercise bootstrap and zero-diff repeat; the actual live build remained
blocked. Counts and all three sanitized run summaries are retained in
`ARTICLE_SYNC_PHASE1_VALIDATION.json`.

Hatena production, gh-pages, main, knowledge/provenance, facets, Best Shot/research
registries, UI assets and admin behavior were not modified. PR #105 remains Draft.

## 承認済み7写真の移行とHTML互換性修正（2026-10-12）

**Status: PASS（公開しない実API事前検証）。実際の公開・移行適用は未実施。**

開始mainは `df1a5dfe69a9c01b39d44ee2421fd77b3940ad7a`、treeは
`2697ef1cf5df4a3a8709a216726601014640d9ec`。
開始PR headは `a818f8f7630072a5b3b0af0c2f6cf37d12134d3a`、treeは
`d9386c680b293b4710277b775c9d04ff24dbadde`。remoteはいずれも一致した。

ユーザーは「2025年ベストショット集」を下書きのままにし、指定7写真だけを
ギャラリーから除外することを明示承認した。記事、写真ストレージ、登録Best Shot、
同定履歴、知識データは変更しない。この判断が上の歴史的BLOCKERを解消する承認である。

### 固定承認境界

`sync-migrations/hatena-draft-photo-retirement-2026-10-12.json` に7 ID、旧登録名、
記事ID／画像URL／旧記事URLのSHA-256、旧commit、portal全体のpayload hash、理由・条件を記録。
manifest bytesのSHA-256 `4e081702d97bb62b0a05de33f02244e3af8376082e31a77fd03feda3b1d0a36c`
を `sync_retirement.py` に固定した。汎用削除リストではなく、この承認だけの記録である。
認証情報・非公開本文・生の移行対象URLはmanifestに含めない。

初回のみ、read-only gh-pages checkoutのHEADが
`f3114e2bbd367047eef04d7a9291303ae7161f4c` と一致し、原本913枚とpayload hash、7件のID・
名前・記事・URL hashesがすべて一致することを要求する。完全API取得で対象記事が明示的な
下書きであること、7枚だけが欠落すること、Best Shot／研究室／同定履歴に保護参照がないことを
確認してから、**メモリ上の比較対象**を残る906枚へ限定する。原本ファイルは編集しない。
原本checkoutやその親を出力先として上書きする操作も拒否する。

通常の `reconcile_ids()` は維持し、906 ID・名前・Atom記事ID・完全一致画像URL・重複数を
照合する。その他の1枚でも削除、名前変更、URL置換、重複不整合があればBLOCKED。
新規写真は従来のaccepted-subject/high-confidenceゲートを通る必要がある。

正常候補のchecksum付き `article-sync-snapshot.json` 内にretirement監査記録を封入する。
記録にはmigration ID、manifest hash、原本commit/payload hash、記事hash、件数、適用時刻を含む。
2回目はその記録を検証して新しい906枚のsnapshotを通常の比較元にし、同じ7枚を再削除しない。
manifestや監査記録の欠落・変更は拒否。対象記事が公開状態になった場合は
`RETIRED_ARTICLE_REVIEW_REQUIRED`。将来記事がAPIから消えて下書き状態を確認できなくなった場合も
保守的に停止する。自動復活・恒久的な一般削除許可はない。

### HTML選択と5枚の互換性

Atomのcontentが明示的にHTMLなら元HTMLを採用する。Markdown／はてな記法などは、明示的に
HTMLとされたformatted-contentを使用する。適切なHTMLがない場合は推測変換しない。
下書き除外、page/ID/update/origin検証、Phase 3C DOM順抽出・hybrid検証は維持する。
キノコ名の強制上書き・taxonomy変更はない。

実APIで、以前名前が変化した5 IDを個別に照合し、旧名「不明」2枚と
「ヤマドリタケモドキ」3枚がすべて一致した。906枚全件の名前も一致した。

### 公開候補の残存検査と観察ノート

最終検査はHTML/JSON/JS/CSS全体の7 ID、対象記事・リンク、画像URLを確認する。
別の公開記事に正当に存在する同じ画像は削除しない（現在の公開inventoryを根拠に認める）。
通常生成が作るJSONを再帰解析するため、JSONのescaped URLも検査する。

初回検証でfavorite.htmlへの古いEXIF cache URLの露出を検出した。内部cacheを削除せず、
公開EXIFを現galleryのsrcだけに限定した。また観察ノートの保存済みURLは現SRC_TO_ALTに
存在する場合だけ描画する。localStorageは編集せず、正当な掲載やEXIFなし写真は維持する。
`assets/gallery.js`の変更はこのfavorite選択条件だけ。iframe／PAGE TOP／毒胞子は変更しない。

### 完了した実API検証

[最終runtimeのread-only preflight](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38188053970)
はhead `2cd6764de8a91860d2c1d609308b2891f3edebc2` で成功した。
PR105・same-repo限定のpull_request、contents:read、GET-only、runner temporary output、
集計値と原因コードだけのartifact。デプロイ・workflow_dispatch・cache saveは含めず、
一時workflowは終了後の最終差分から除去した。以下の数値は実測であり、固定件数へ調整していない。

| 項目 | 実測 |
| --- | --- |
| Atom pages / entries | 12 / 112、ページネーション完了 |
| 公開記事 / 除外下書き | 110 / 2 |
| 公開HTML内の画像 | 976 |
| 旧公開写真の内訳 | 913 = retired 7 + ID・名前維持906 |
| 追加採用写真 | 0。通常の初回新規・削除差分はUNKNOWN |
| Best Shot / 研究室 | 3 / 67、ケース・写真参照PASS |
| 同定履歴 | 登録ファイル未変更（現在0件） |
| HTML生成 | 322ページ。portal、図鑑、観察記録、new-topを含む |
| 公開候補検査 | 345テキストファイル、7 ID／対象URL残存なし |
| 初回通常比較 | UNKNOWN、null countsを保持。retirementは別イベント |
| 同じ取得結果で2回目 | KNOWN、通常差分すべて0、retired_this_run=0 |

2回目は最初の実GET応答をメモリ上で再使用し、既存runnerで再生成した。
新たな本文公開や別の同期実装はない。実入力からの限定的なfault probesで、他の写真の
削除・名前変更・URL置換、manifest欠落・改ざん、違うbaseline commit、対象記事再公開が
すべて固定コードでBLOCKEDとなることも確認した。

### 回帰テスト・保護範囲・リリース判断

最終検証：Python 706 passed / 706 collected、focused 103 passed、Node 43 passed。
compileall、JS syntax、workflow YAML、diff-check PASS。manifest境界、台帳継続、
保護参照、出力残存、JSON escaped URL、正当な共有画像、古いお気に入りの非再描画をfixtureで検証。
今回のmanifest/runtime/test/documentationと必要なfavorite公開データ境界以外は変更しない。
`data/**`、`audit/**`、feature overlay、知識・provenance・Best Shot／同定registry、admin、
Hatena、poison runtime、portal styles、既存generate.ymlは開始PRから差分なし。

技術的なマージBLOCKERは解消した。ユーザーのレビュー後に手動マージ可能。
既存main-push生成公開と09:00 JST相当のcronは、マージ後に初めてこのコードを使用する。
今回の作業ではmain／gh-pages／Hatena本番を変更せず、マージ・deploy・auto-merge・dispatchを行わない。
本番の初回実行・スケジュール実行は未実施であり、read-only candidate PASSと区別する。
Phase 2の未分類／曖昧写真の確認・修正・承認UIは引き続き別作業。552 review signalsは
既存分類状態を含む集計で、552件の新規問題という意味ではない。
