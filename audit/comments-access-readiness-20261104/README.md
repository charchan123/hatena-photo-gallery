# PR137 Access経路準備確認・オフライン引き継ぎ

記録日：2026-11-04 JST。今回の変更は**オフライン補助コード・試験・記録だけ**。
Cloudflareアカウントへの再接続、認証情報発行、設定変更、URL再開、deploy、D1変更は0件。
CPU/Service Auth/OPTIONSの実環境再試験は未実施。コメント総合試験へは進めない。

## 開始状態・既存成果

- PR137開始HEAD `4fdb9bc70359c22f448cec02a864535984d41333`、tree `44cef9d68c4710e22870c4d0bf47b482368310cf`。Draft/open/未マージ。
- 読取取得main `cd51ca486c542ff6f33f2c9803397110b39893ec`、gh-pages `f59f1bf9cb897ac5d0663cd39e37e717b1cdafdc`。開始ahead11/behind2。
- mainのPR141（ガイド画像差し替え）を通常mergeで取り込み、履歴を維持。画像試験 `tests/browser/ai_artwork_fixture.py` の同等な条件・コメントが1箇所競合し、mainの表記で解消。基準コミットに画像があるときは削除しない条件を保持。画像・CSSの変更はmainからの取り込みであり、今回の独自編集ではない。
- CPU最適化後Workerの配置済みversion `6ff1d822-8419-47e7-8c46-15c1d4282493`。compiled SHA256 `0f363c931bd791aaa92b1b89d513fa4709b0ce5504ab5c1c206043c6d847d68a`。`run_worker_first=true`・ASSETS bindingは前回API読返しで確認済み。今回再deployしない。
- 既存CI11 workflows/13 jobs成功、Python1132件等は開始HEADの既存成果として再利用。新HEADのCIと混同しない。
- `comments/staging/worker.mjs` / `registry.mjs` / JWT verifier / SQL・manifest / 公開設定 / 管理室実装は今回変更しない。

## 実環境の失敗記録（変更禁止）

`previous-stop.json` は前回保存済みの停止監査をそのまま保全したもの。JSONのGitHub書込0等は**前回試験時点**の記録であり、今回の監査保存を指さない。

2026-11-03 13:32:28.186〜13:32:39.516 UTC、最初の未認証GET `/`がHTTP404、19984bytes、app_error=none。1件中0件成功、認証済み要求0件で停止。D1件数とAccess設定不変、URL閉鎖は本人レポートによる。

確定：想定するAccess入口を確認できなかった。**未確定**：404の応答層、経路反映遅延か別の設定要因か。本文・Location・Content-Typeは元レポートに残っていない。サイズやapp_error=noneから漏出なしと断定しない。URL-enable API成功直後にHTTP試験へ進む旧helperの実装は確認したが、反映遅延説は仮説に留める。

11月1日のCPU P50 10.08 / P90 19.29 / P99 23.53ms、認証済みpreflight OPTIONS403、過去のService Auth401も未解決履歴として既存 `audit/comments-cpu-options-20261101/live-history.json` 等に保持。11月3日はDashboard No data、CPU未測定。ローカル91.49%削減を実CPU値へ換算しない。

## 今回の補助コード

`comments/tools/access-readiness.mjs` は既定のfetchもAPIクライアントもCLIも持たない。資格情報・env・ファイルを読まず、直接実行しても通信しない。将来の承認済みrunnerから明示的にコールバックを渡すための補助モジュールであり、**まだWindows向け実行パッケージへ組み込んでいない**。

- 固定の専用Worker originのGET `/`だけ。Cookie/Authorization/Service Authヘッダーを付けず、credentials=omit、redirect=manual。リダイレクト追従を拒否する。
- 最大3観測・全体15秒・各要求4秒・間隔3秒。上限を拡大できない。HTTP404だけを準備未確認として有期限に観測し、成功やセキュリティ試験件数へ加算しない。
- 本人用Access teamのHTTPS originと`/cdn-cgi/access/`への転送だけを準備確認に使う。401/403の一律成功扱いはしない。これは外周全経路の保護証明ではない。
- JSON、既知アプリ本文、CPU等の既知エラー、想定外の応答/転送、64KiB超の本文、タイムアウトは停止。404でアプリの未知の本文を完全識別できるとは主張しない。その後も全未認証試験が独立して必要。
- 保存するのはstatus、Content-Type分類、転送先の一致分類、body bytes/SHA256、経過wall time、固定の理由コードのみ。生の本文、Location、クエリ、Cookie、ヘッダー、例外文は保存しない。wall timeはCPUではない。
- `runGuardedReadiness()` は準備確認後に既存の全未認証試験を呼び、明示的なtrueを受け取るまで認証付きフェーズを呼ばない。成功・停止・例外とも必ずcloseを呼ぶ。閉鎖検証がtrueでなければ `CLOSURE_UNCONFIRMED` を最優先にし、先行の失敗理由も保持する。
- コールバックの実装自体や外部のwatchdog・期限・Control API検査はこのモジュールでは代替しない。実環境の閉鎖を模擬試験で証明したとは扱わない。

試験は `comments/tests/access-readiness.test.mjs`。既存 `staging.test.mjs` からimportし、既存Linux/Windows CI両方で実行する。元のJWT・D1・OPTIONS期待値と固定バイト検査は無変更。

## 再開手順と残作業

1. 最新のPR137/main/gh-pagesとCIを読む。今回のmoduleは実Worker bundleに入らないため、配置済みversionを再利用できるかを読み取り照合する。既存D1は再seed・migration・再作成しない。
2. **旧期限2026-11-04 00:00 JSTは終了済み。** 実試験前に、新しい絶対期限を含む資格情報の具体的承認を得る。旧tokenは再利用・再有効化しない。
3. 承認待ちの間に、既存Windows runnerへこのmoduleを組み込む新パッケージを作る。旧レポート・attempt markerは削除/上書きしない。新attemptへ前回証跡のSHAを結び、旧helperをそのまま再実行しない。
4. 専用Workerだけの編集、D1/Access/service metadataと使用統計は必要な読み取り権限に限定。Access編集をbuild tokenに付けない。Service Token（最大1h）の作成と専用Service Auth参照だけ本人Dashboardで行い、終了時に元の無効token参照へ戻す。
5. Freeプラン・本人限定Allow・All traffic・優先するhostname/path設定・Worker version/worker-first・閉鎖flags・D13/66/66/空を読み取り確認。以前の閉鎖を現在も維持と推測しない。
6. 既存の独立watchdogと期限ガードを開始してから専用Production URLだけ有効化。Preview/custom domains/routesは追加しない。このmoduleで無資格の準備観測→独立した全未認証試験→最少認証GETの順に進める。準備未確定なら閉鎖し、自動の再開・無限再試験はしない。
7. 少数の実CPU指標を確認し、初回/通常を区別できない場合は限界を明記。10ms条件に達しない場合や認証不整合はPaidへ移らず停止。OPTIONS通常要求・preflight・同一origin・Python server-to-serverを分け、過去403を残す。コメント/Turnstile試験へは進まない。
8. 成否を問わずREAD/WRITE=false・not-approved・URL/Preview無効・Access維持・新Service Disabled・build token削除・参照復旧を実確認。閉鎖不成立は最優先報告。閉鎖確認のためURLを再開しない。

今回の停止状態は**前回確認記録を維持**。本日Cloudflareへ接続し直して確認したものではない。旧構築token削除、新Service Disabled、旧3件Disabled、専用policy参照旧r3復旧、Windows資格情報消去は前回/本人出力の証拠による。

## 検証コマンド・CI

```sh
node --test comments/tests/access-readiness.test.mjs
node --test comments/tests/api.test.mjs comments/tests/staging.test.mjs
python -m pytest -q tests/test_comments_preflight.py tests/test_ai_artwork.py
python tests/browser/comments_integration_protection.py /tmp/protection.json origin/main
```

新規単体26件、Nodeコメント全体56件、Pythonコメント＋画像46件が成功（失敗/skip0）。保護データ照合も成功。コマンド・SHAは `local-tests.json`、保護照合は `protection.json`。最終HEADのCIはPR137の今回の監査コメントとActionsを正本とする。CI開始前に結果を成功と先書きしない。今回ローカルChromium・本人Windows管理室全機能・Android・Cloudflare CPU/認証/OPTIONS/実Turnstileは未実施。

公開一次資料だけ2026-11-04再読：
- https://developers.cloudflare.com/workers/configuration/cloudflare-access/
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/cors/

Worker単位の保護と、ブラウザcross-origin preflightがCookieを送らず403になる一般仕様を確認。これらは今回の404やService Auth付きOPTIONS403の個別原因を確定する証拠ではない。公式のBypass等の選択肢は採用しない。
