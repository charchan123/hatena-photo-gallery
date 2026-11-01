# PR137 CPU最適化・OPTIONS検証 引き継ぎ

2026-11-02追記：保存HEAD `c4728dd8b52687092bad48fc25f19b11c416305f` の確定CIは10 workflows成功/Validate1件失敗だった。[履歴不足の原因・最小修正・再利用した成績](audit/comments-cpu-options-20261101/ci-history-fix-20261102.md)を参照。最初のcheckoutがdepth1のため過去の固定SHAを読めず、1131 passed/1 failed。テストを変えず、admin-validate最初のcheckoutだけfetch-depth:0とした。最終HEADのCI結果はPR137の最新監査コメントを正本とする。以下は11月1日停止時点の履歴として保持する。Cloudflare操作は引き続き禁止。

同日追加：履歴修正HEAD `8e40593d7980ab5d10bc0cde87d511fc709b9321` のValidateは1132 passed/JSも成功。comments WindowsだけCRLFによる固定SHA不一致で停止（40 passed/1 failed）。同じ監査資料に失敗を保存し、comments CIの準備stepを新規prefix＋明示LFでindex原本を復元する方式へ修正した。テストやruntimeは不変。次回は最新HEADの全13job結果をPR監査コメントで確認し、これらの途中HEADを全件成功と混同しない。

保存日：2026-11-01 JST、21:14時点の確認に基づく。Work残量約7%の緊急指示により、新規実装・追加の長時間試験を停止し、成果保全を優先した。

**次回はGitHubの最終HEADとCIを読むところから再開する。実装・全件試験・Cloudflare構築を最初からやり直さない。今回はCloudflareアカウント操作0件。実環境は別承認なしに再開しない。**

## A. 目的と承認範囲

Repository：`charchan123/hatena-photo-gallery`、既存[PR137](https://github.com/charchan123/hatena-photo-gallery/pull/137)。既存ブランチ `fix/comments-staging-access-20261022` を使用。

- Workers Free向けcheckRegistry CPU削減。固定registry/66 identity期待値の重複計算を減らす。
- 毎回のD1 metadata・66ケース・alias照合、JWT署名/issuer/AUD/期限検証は維持。可変DBのTTL cacheは禁止。
- 認証済みOPTIONS403をAccess外周/Worker内部/同一originブラウザ/Windows localhost Service Authへ分け、実利用経路の機能で検証する。
- PR137だけに保存し、Draft・未マージを維持。main/gh-pages/PR136/138、本番コメントOFF、写真、トップ、LightGallery、同期/削除保護、管理室下書きを変更しない。
- Cloudflareログイン・token発行・URL有効化・remote migration・再seed・deploy・設定変更・Paid化は今回すべて禁止。

## B. 開始・保存状態

| 項目 | SHA・状態 |
|---|---|
| 開始PR137 HEAD | `582a6c19e136fe5f7f6b2c2448cb0f63f14d1235` |
| 開始tree | `87d9b8206d46013cb234db4404b247b809e040d8` |
| 開始main | `b913ad7b07f689f14f5c8dcecea11b7c99363827` |
| 開始gh-pages | `3549e4ea9fa5619fe6eb53f7c5716d675250ce4f` |
| 実装修正のGitHub保存HEAD | `1caa405e72406bbecfd498e699ecc1b2e3c2dec5` |
| 実装tree | `fbf710c257b039ce46266a82a593b24d4752e682` |
| 実装commit親 | 開始HEADそのもの。通常のfast-forward、force=false |
| mainとの差（実装HEAD） | ahead8 / behind0 |
| 最後のPR状態 | open / draft=true / merged=false |

本MDは実装HEADの後へ別の保存commitとして追加する。このMDを含む最新HEADはPR137から確認すること。自己参照のためMD中へ自身のcommit SHAを埋め込まない。最終チャットでも保存HEADを報告する。

ローカルCLI pushは認証不足 `fatal: could not read Username for 'https://github.com': No such device or address` で失敗。GitHub接続のcreate_tree/create_commit/update_refを使用し、上記の20ファイルを保存済み。GitHub treeとローカル実装treeは完全一致した。

ローカルには同じtreeの未push commit `79fd6aa1e2161fa6f0a70ff1c66567e3e15f5eae` も作ったが、これはGitHub HEADではない。次回このSHAをpushしたり必要な基準としたりしない。履歴を書き換えたのではなく、同じ内容をGitHub接続で保存した。

作業パス（再作成可能、一時環境への依存は禁止）：`/workspace/scratch/5cbb85c53a21/cpu-options-work`。このworktreeはdetached HEADで実装GitHub HEADへcheckout済み。元の `/workspace/scratch/5cbb85c53a21/repo` は変更せず、そこに元々ある未追跡ファイルも操作していない。

### 前回のCloudflare実測（今回再試験していない）

提供された停止監査 `kinoko-cloudflare-staging-audit-20261101.md` を全文読了し、同内容の添付コピーとも照合済み。実環境履歴は `audit/comments-cpu-options-20261101/live-history.json` に元監査SHA付きで保存。

- 15 invocations、CPU P50 **10.08ms**、P90 **19.29ms**、P99 **23.53ms**。CPU超過エラー0でも10ms条件は未達。
- 既存未認証29件成功、最新16/17成功（2件追加否定試験＋14件認証済み成功）。累計45は重複観点を含む。
- `AUTH_TEST_AUTHENTICATED_OPTIONS_FAILED`、204期待に対してHTTP403、APP_ERRORなし。OriginとAccess-Control-Request-Method付き。失敗を消さない。
- 前回閉鎖：Production/Preview無効、READ/WRITE=false、RELEASE_APPROVAL=not-approved、Access All traffic維持、Service Token3件Disabled、構築API token削除済み。D1/Turnstile/secretsは保持。
- 今回はアカウントへ接続していないので、「閉鎖を再実証した」とは報告しない。秘密値・管理者メール・個人情報を引き継がない。失効済みtokenを復活させない。

## C. 完了した実装と変更ファイル

調査元：`comments/staging/worker.mjs`、`access.mjs`、`build.py`、manifest、既存共通Worker、D1 migrations/tests、staging browser/server fixture、管理室comments_client、既存保護比較、CI、runbook/access資料。Cloudflare公式CORS/Worker Access/Service Token資料を参照（公開文書だけ。アカウント接続なし）。

| 変更・新規 | ファイル | 目的 |
|---|---|---|
| M | `comments/staging/worker.mjs` | 既存checkRegistryを専用checkerへ抽出、factoryで生成。JWTの後・全経路の前の照合順とtimeoutを維持 |
| A | `comments/staging/registry.mjs` | 固定期待値のみlazy promiseで1回検証・再利用。毎要求D1の3 SELECTと全行比較 |
| A | `comments/staging/benchmark-registry.mjs` | 基準HEADの関数をgit showで取得し、同じSQLiteでCPU/壁時計/SHA/D1回数を比較。ネット接続なし |
| A | `comments/staging/access-snapshot.mjs` | 前回回復guardを元に、渡されたAccess snapshotを純粋に検査。APIクライアントではない |
| A | `comments/tests/registry.test.mjs` | 同時初期化67 SHA、warm0 SHA、D1毎回3読取、warm後DB改変拒否、JWT毎回検証 |
| A | `comments/tests/access-snapshot.test.mjs` | scope拡大・owner/service差替・Everyone/Bypass/CORS緩和を拒否 |
| M | `comments/tests/staging.test.mjs` | 新試験を既存実行経路へimport。Worker内部OPTIONSはOrigin＋ACR headers付きでも204期待を維持 |
| M | `tests/browser/comments_staging_server.mjs` | ローカル外周モデルのpreflight拒否とWorker到達/OPTIONS/Service Authヘッダー統計を追加 |
| M | `tests/browser/comments_staging.cjs` | 外周否定試験と実利用経路を分離。ブラウザ/管理室機能成功に加えOPTIONS増加0、秘密がブラウザへ渡らないことを検査 |
| M | `tests/browser/comments_integration_protection.py` | 変更したruntime2ファイルだけ今回の正確なSHAへ固定。他の元runtimeと本番保護比較を維持 |
| M | `tests/test_comments_preflight.py` | 新runtime SHAを変えれば失敗し、他のJWT moduleを勝手に変えても拒否する試験 |
| M | `.github/workflows/research-comments.yml` | 既存Linux/Windows jobにオフラインCPU記録とartifactを追加。Cloudflare権限・secret追加なし |
| A | `docs/research-comments-cpu-options.md` | 方式比較、採用理由、4経路検証、実403履歴、別承認の再試験条件 |
| M | `docs/research-comments-staging-access.md` | 11月1日の新設計への案内。古い「未構築」記述は当時の履歴と明記 |
| M | `docs/research-comments-staging-runbook.md` | 同上、再seed・旧実試験スクリプト再実行の禁止を追記 |
| A | `audit/comments-cpu-options-20261101/README.md` | ローカル成績・失敗履歴・未解決・保護条件 |
| A | `audit/comments-cpu-options-20261101/live-history.json` | 元実Cloudflare403・CPU未達を失敗のまま保存 |
| A | `audit/comments-cpu-options-20261101/local-cpu.json` | 7標本・初回・cold20個・実操作回数・機器/Node環境 |
| A | `audit/comments-cpu-options-20261101/protection.json` | main/公開データ比較・各保護ファイルhash・counts |
| A | `audit/comments-cpu-options-20261101/runtime-hashes.json` | 意図したworker/registryの2ファイルSHA固定 |

上記20ファイルは保存済み。この引き継ぎMDを加えると21ファイル。共通Worker・Access JWT verifier本体・公開JS・管理室実装・SQL/migrations・registry/manifest・本番config・写真・トップ・LightGallery・日次同期・削除保護は開始HEADから変更なし。

### 実装の重要点

`createRegistryChecker()` はprivateなregistry/manifest snapshotを作る。最初の認証済み要求で全体SHAと66 identity SHA、manifest version/active IDsを検証。期待するcases/aliasesの正規化文字列だけ保持する。WebCryptoをグローバルで開始せず、lazy promiseを同時初回要求で共有。初期化失敗は以後も拒否。

毎要求のJWT検証、DB metadata/schema/installation/registry SHA、全66cases/全aliases照合は省略しない。DB/JWTの認証結果cacheなし。期待値のsort/canonicalだけも初期化へ移した。3秒のregistry timeoutと503 fail closedを維持。

方式比較：ビルド時の期待値生成は初回を軽くできるが生成物の信頼・同期対象が増える。ビルド検証だけへの依存は手順迂回に弱い。今回isolate内の固定期待値再利用を採用。可変DB TTL cacheは禁止。

## D. 測定・検証結果

### ローカルCPU（実Cloudflare CPUではない）

Node24.22.1/Linux x64、in-memory SQLite、process.cpuUsage user+system。基準HEADの元関数そのものを比較。100要求×7標本、順序を交互。JWT/ネットワーク/実D1は含まない。

| 項目 | 従来 | 修正後 |
|---|---:|---:|
| warm照合CPU中央値/要求 | 2.13228ms | 0.18148ms |
| 削減率 | — | 91.49% |
| 固定SHA/warm要求 | 67 | 0 |
| D1全件SELECT/要求 | 3 | 3 |

初回は67 SHAを残す。初回ローカルCPU13.955ms、cold20 checkerの総CPU47.501ms。**初回負荷は解消していない。実Cloudflare10ms達成は未確認。ローカル削減率を実CPUへ掛け算しない。**

### ローカル試験

| 実行 | 結果 |
|---|---|
| `python -m pytest -q` | 最終1132 passed、skipなし |
| `node --test comments/tests/api.test.mjs comments/tests/staging.test.mjs` | 30 passed、fail/skipなし（TAPログで確認） |
| `node --test tests/*.js` | 86 passed、fail/skipなし |
| `python -m pytest -q tests/test_comments_preflight.py tests/test_comments_staging.py tests/test_research_comments.py` | 41 passed |
| `python comments/tools/seed.py` + migration差分比較 | 差分0。オフライン生成だけ、既存実D1には接続しない |
| `python tests/browser/comments_integration_protection.py /tmp/comments-protection.json origin/main` | 合格、pendingなし、enabled=false |
| Wrangler4.151.3 `deploy --dry-run --config comments/staging/wrangler.example.jsonc --outdir ...` | bundle成功。認証情報なし、metrics送信無効、deployなし |
| ローカルChromium | バイナリなし。Playwright配布ZIPが破損してダウンロード失敗。ローカルで成功とは報告しない |

保護比較：写真933 / Best17 / NEW14 / 研究室66 / 退役7 / master141 / sources419 / WebP7。main保護ファイル、公開config、registry、写真/EXIF等のsourceバイト比較を既存gateで維持。

### 途中の失敗と対応（削除禁止）

1. 初期のNode改変試験が `no such trigger: prevent_case_delete` で失敗。試験fixtureで実在しないtrigger名を指定したため。実SQLを変更せず、fixtureだけを実在の `retain_alias` へ修正し、全Node試験成功。
2. 最初のPython実行はpytest/bs4未導入。専用venvへrequirements-devを導入して継続。
3. Python全件の初回は1099 passed / 33 setup errors、`OUTPUT_INTEGRITY_ERROR`。失敗対象の独立再実行34 passed、全件再実行1132 passed。テスト・本番コードを緩和せず合格。生成物やsuite間状態の影響の可能性は未確定。CIクリーンcheckoutの全件成績も確認する。
4. Chromium ZIPで `End of central directory record signature not found`。通常版と既存1.58系の両方で失敗。CIへ検証を引き継ぎ、これ以上ダウンロードを繰り返さない。
5. ローカルgit pushの認証不足。GitHub接続で同一treeを保存し、PR HEADを実確認した。
6. 文書patchの文脈不一致・一括ファイル読取の出力切断は修復済み。保存内容の欠落なし。
7. 過去の実OPTIONS403・CPU未達・r2 Service Auth401の根本原因は未解決。オフライン合格で取り消さない。

### 最終確認時点のCI（実装HEAD）

実装HEAD `1caa405e72406bbecfd498e699ecc1b2e3c2dec5` に11 workflows /13 jobsが起動。21:14JST時点のworkflow：

| Run ID | workflow | 状態 |
|---|---|---|
| 41305364321 | research comments（Linux/Windows） | 実行中。Ubuntu jobの安全試験・dry-run・実ブラウザ・artifact各stepはsuccess確認済み。Windowsは依存導入中だった |
| 41305364325 | admin Draft PR（Linux/Windows） | 実行中 |
| 41305364292 | layout tuning | 実行中 |
| 41305364293 | Validate Admin Changes | 実行中。最新はてな読取validationと保護gateはsuccess、Python全件実行中だった |
| 41305364301 | shared LightGallery | 実行中、PC/mobile browser stepへ到達 |
| 41305364345 | Hatena release preparation | 実行中 |
| 41305364289 | AI artwork | 実行中、WebP実描画stepへ到達 |
| 41305364299 | manual capture date | success |
| 41305364331 | deletion audit | success |
| 41305364333 | Hatena Star | success |
| 41305364296 | deletion browser | success |

Run URL形式：`https://github.com/charchan123/hatena-photo-gallery/actions/runs/<Run ID>`。
コメントUbuntu job ID124844533705 / Windows124844533446。全件Validate job124844533353。**最終CI全件成功は未確認。** このMD保存でさらに新HEADのCIが起動し得る。その新HEADも次回確認する。意図的なskip/削除/期待値緩和はなし。

## E. OPTIONSの結論と未完了事項

1. **Access外周**：公式資料はbrowser cross-origin preflightにCookieが付かず、ログイン済みでも403と説明。過去の手製要求はService Authヘッダー付きだったので、その個別拒否原因まで確定していない。APP_ERRORなしだけで処理層を断定しない。
2. **Worker内部**：署名JWTを直接渡す単体試験でOrigin＋ACR-Method/Headers付き204、空本文、厳格CORSを確認。JWTなし・外部Origin・管理OPTIONSを拒否。元の204期待を維持。
3. **実利用ブラウザ**：既存のHTTPS同一origin＋HttpOnly Access Cookie＋credentials=same-origin＋redirect=errorを維持。同一origin JSON POSTにはpreflight不要。機能成功とOPTIONS増加0を別に検査。
4. **Windows管理室**：localhost browser→Pythonの既存Host/Origin/CSRFを維持。Python→WorkerはService Auth2ヘッダー＋別管理Bearer、Origin/Cookie/ACR-Methodなし。server-to-serverでbrowser CORSに依存しない。

利用経路を変更する必要は現時点で見つかっていない。検証を層分けした。ローカル外周モデルの403追加は否定試験であり、過去の実403を合格に読み替えたものではない。Everyone/Bypass/認証省略/無制限CORSは追加していない。

**未完了**：最終CI全13job/重要stepの確認、CIの実ブラウザ結果/CPU artifactの回収、初回Python setup errorsの必要に応じた原因確定、全件成功後の最終監査コメント。新たな実装途中・未保存の実装コードはない。

**別承認でのみ実施**：実Cloudflare cold/warm CPU、実Access Cookie/Service Auth/preflight原因切分け、Turnstile成功/失敗/timeout、実D1合成コメント投稿/表示/ページ送り/削除/通報/返信/管理操作/レート/重複防止、backup/ローカルrestore、障害時、Android/実Windows一連。これらを今回合格と扱わない。

## F. 次回の具体的再開順序

1. 本MDと `docs/research-comments-cpu-options.md`、監査フォルダを読む。GitHubからPR137/latest main/gh-pagesを読み直す。Draft/open/unmerged、branch名、HEAD、main差分を確認。勝手にmerge/rebase/forceしない。
2. このMDを含む最終HEADのCIと、上記実装HEADのCIを読む。**追加試験より先に既存runの結果を再利用**。各workflow→jobs→重要steps→失敗ログの順で確認。新しいCIが走っていれば重複起動しない。
3. comment Linux/Windows両jobのIdentity/D1/security、Wrangler dry-run、実UI＋localhost proxy、artifactを確認。ValidateのPython全件、admin-pr両OS、LightGallery、正式トップiframe、スター、画像差替、日次同期/削除保護も確認。
4. 失敗がなければ、新実装を追加せずCI成績・実装HEAD/tree・保護状態をPR137へ監査コメントとして保存し、完了報告。READMEの未確認記述と実成績を区別して補足する。ドキュメント追加で新HEADになった場合、必要な最終CIも確認する。
5. 失敗した場合だけ、実行環境問題か今回の回帰か切り分ける。必要な最小修正・該当テストだけ追加/再実行。元の30/86/1132件を理由なく全部やり直さない。最終HEADのCI成功を確認して停止。

再利用コマンド（新しい一時worktreeを使う場合。秘密値は不要）：

```sh
git fetch origin main gh-pages fix/comments-staging-access-20261022
git worktree add --detach ../pr137-review origin/fix/comments-staging-access-20261022
cd ../pr137-review
npm ci --prefix comments --ignore-scripts --no-audit --no-fund
python -m venv ../pr137-venv
../pr137-venv/bin/pip install -r requirements-dev.txt
# 以下は失敗切分けに必要な場合だけ実行
../pr137-venv/bin/python -m pytest -q tests/test_comments_preflight.py tests/test_comments_staging.py tests/test_research_comments.py
node --test comments/tests/api.test.mjs comments/tests/staging.test.mjs
node --test tests/*.js
../pr137-venv/bin/python tests/browser/comments_integration_protection.py /tmp/comments-protection.json origin/main
node comments/staging/benchmark-registry.mjs /tmp/comments-cpu-local.json
```

WindowsのvenvパスはScripts/python.exeへ読み替える。CIはNode24/Python3.11のコメントjob、Linux/Windows matrix。ローカルはNode24.22.1/Python3.12.14だった。実Windows PCへ変更しない。

ブラウザ試験は既存 `tests/browser/comments_staging.cjs` を使う。Playwrightのmodule pathとPython実行ファイルを環境へ指定し、ローカルHTTPへだけ接続する。実Cloudflare用zip/PowerShellスクリプトを取り違えて実行しない。

### 停止時のローカル未追跡物

追跡済みファイルの未保存差分は0。未追跡は試験で生成された `comments/cpu-options-bundle/` と `output/` 内のHTML/JSON/assetsなど。staging/generatedやnode_modules等のignore対象も再生成可能。**これらは未保存の実装ではなく試験生成物。本番公開・stage・pushしない。** 破棄/reset/cleanはしていない。ログと未追跡生成物は別の保全ZIPへまとめる予定で、完了時のリンクを最終チャットで示す。次回はGitHubのコードと監査を正本とし、これら生成物がないことを実装欠落と誤認しない。

旧Cloudflare実試験zip（auth-fresh等）は今回の修正と別成果。今は使用不可。再seed・marker削除・STOP_NO_RETRY無視・token復活・URL再有効化を禁止する。

### 完了条件と安全停止

今回の最優先は成果保全。実装と監査はGitHubへ保存済み、引き継ぎMDを同じPRへ保存して停止する。最終CIが進行中でも成功と偽らず引き継ぐ。次回のオフライン完了条件は最終HEADの必要CIと監査確認。Cloudflare実環境の再試験・本番公開は承認範囲外。

PR137のDraft解除/merge、main/gh-pages書込、PR138環境への影響、保護データ差分、secret漏えい、テスト緩和の必要性、実Cloudflare操作やPaid移行が必要になった場合は停止して報告する。

## G. 一次資料

- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/cors/
- https://developers.cloudflare.com/workers/configuration/cloudflare-access/
- https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/
- https://developers.cloudflare.com/workers/observability/metrics-and-analytics/

この資料に秘密鍵・token秘密値・管理者メール・支払い情報は含めない。
