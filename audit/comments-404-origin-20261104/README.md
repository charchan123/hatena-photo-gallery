# PR137：404発生元のオフライン分析・再診断設計

開始HEAD `3eebaf843085f0d0b31de96dae3797be3b5d149c`。main `cd51ca486c542ff6f33f2c9803397110b39893ec`、gh-pages `ac191df2c0537d32ee86bcc670bdfd3151f84082`。Draft/open/未マージ。Cloudflareのアカウント・API・公開URLには今回一切接続しない。一次資料の公開ドキュメントだけ閲覧した。

## 読んだ正本と証拠の範囲

本人添付 `REPORT_PR137_STAGING_STOP_20261104(1).md`（Library `libfile_26e2e3c801548191918451f526ba3af4`）、`RETEST_PR137_PROGRESS_20261104.md` v5、[最新の停止監査コメント](https://github.com/charchan123/hatena-photo-gallery/pull/137#issuecomment-6632437077)、既存readiness監査・ソース・CPU/OPTIONS資料を使用した。Windowsの旧packetはLibrary `libfile_d7607429b66481918018015122df2d2c` v0の保存済みローカルコピーを静的に読んだ。実行・再配布・変更はしていない。旧source SHAは `runner-comparison.json`。

`previous-stop.json` は保存済み停止監査の複製。過去の404/CPU/OPTIONS403の結果を上書きしない。今回の実装で過去試験が成功したことにはしない。提供されたログ抜粋にはreadiness各要求の正確なUTC時刻がないため、後から時刻やRay IDを補完しない。

## 確定できたこと

2026-11-04T13:34:19.610Z〜13:34:35.838Zに、同じ未認証GET `/`で404 → 正しいAccess302 → 404を観測。本試験0/1、認証要求0。両404はtext/html、19,984 bytes、SHA256 `2000e6b28a1517ba1268e1649cd3163326ef839492edfdba31e8959830580976`。同じ受信bytesを観測した証拠であり、発生層を示す証拠ではない。

`comments/staging/worker.mjs` の `/` はsettings→JWT署名/issuer/AUD/時刻→D1全registry照合の順。JWTなし/偽造なら403 JSON `STAGING_ACCESS_DENIED`、D1不整合なら503 JSON、許可外パス/メソッドなら404 JSON。認証済み `/` はASSETSへ `/research.html` を要求し、assetが200以外なら503 JSON `ASSET_UNAVAILABLE`へ変換する。**このentryの明示的な返却経路に、未認証GET `/`でHTML404をそのまま返す経路はない。** 改変されていないcodeが正常に実行されたという条件での除外で、実際のWorker実行証明ではない。

build.pyのオフライン生成HTMLは30,121 bytes、SHA256 `0bf695879e4c1142ed148dcbe1efe60cebcfcf5ebf0ede392313be5c909cf231`。今回の404本文とは一致しない。assetsにはindex.html/404.html生成がなく、root→research.htmlの写像はWorker内。アップロード済みassetsの現在の内容を今回接続して確認したわけではない。

## 原因候補（証拠が強い順、確率の断定なし）

| 順位 | 候補・判断 | 根拠と限界 |
| --- | --- | --- |
| 1 | 期待するWorker handler以外の経路で404が生成/配信された可能性が最も整合的 | 明示的Worker返却経路とMIME/statusが不一致。workers.dev経路・Access入口・platform routingのどこかまでは未特定。プラットフォームによる置換や中間層も排除できない |
| 2 | workers.dev有効化後のデータ経路/Access対象解決の不安定、反映不一致 | 制御API読返しのenabled=trueと実HTTPは別証拠。302後に再度404なので「最初の404だけ待てば解消」とする単調な反映モデルでは説明不十分。反映遅延、別edge、設定の競合等の内訳は未確定 |
| 3 | より優先されるhostname/path Access設定、対象Worker識別・配信設定の不一致 | 公式の優先順位上は可能。旧preflightは全app/policyと本人/worker/AUDの厳密比較を通っており、単純な設定間違いを支持する証拠は弱い。実要求がどのruleへ解決されたか不明 |
| 4 | キャッシュ・接続/IPv4/IPv6・クライアント中間層の相違 | 旧2経路は同じorigin/root/GET、headers={}、credentials=omit、redirect=manual、cache未指定。ヘッダー・Ray・接続先が未保存で判別不能。本文ハッシュ一致はcache hitの証明ではない |
| 5 | Static Assetsでindex/asset未存在404 | asset-firstなら一般に可能だが、旧読返しでrun_worker_first=trueを検証。正しいentry実行ならASSETS404も503 JSONになるため通常経路としては整合しにくい。run_worker_firstはWorkerへ到達する前のworkers.dev/Access処理を保証しない |
| 6 | 現行Workerの通常のNOT_FOUND/認証/registry失敗 | 明示的返却形式と不一致。無JWTのrootとASSETS404の否定試験でもJSONを確認。Worker CPU/runtime障害による外側のHTML置換の可能性は一般論として残るが、今回CPU要求/ログの証拠はない |

一般のreverse-proxy向け404資料に「Cloudflareはoriginの404をproxyする」とあっても、外部originを持たないworkers.devの未解決routeやStatic Assetsへ無条件に当てはめない。19,984 bytesやapp_error=nullだけでCloudflare既知テンプレート・漏出なしとは断定できない。

## 旧Windows runnerの順序・要求比較

1. closed/read-only proof・Access・D1・version/worker-first・leaseを検証。
2. 新exclusive marker、独立watchdog（90秒、親IPC切断後も存続）を準備。
3. 対象Production URLだけ有効化し、制御APIで読返し。
4. readiness（最大3回/15秒）で最初の302をreadyとして返す。
5. 独立した全未認証試験の最初のGET `/`が404で失敗。認証callbackには入らず閉鎖。

これにより**単発302で進む準備判定の弱さは確定したが、404生成原因そのものではない**。独立ゲートは正しく404を拒否しており、安全条件を緩める必要はない。ソース上、成功経路で閉鎖は本試験前に呼ばれない。90秒watchdogの設計期限は約16秒の試験窓より長いが、実ログがないため外部操作/別processの時刻まで否定しない。

旧readinessと独立rootの指定URL・method・認証・redirect・明示headers・cache指定は同じ。AbortSignal実装と本文読取/size管理、collector、実行時点は別だった。Nodeが実際に送った自動ヘッダー、接続pool、IP family、edgeは保存されていない。302のリダイレクト先を追従した、Cookieを保存したというソース上の根拠はない。

## 最小改善

- `access-readiness.mjs`：最大3回/15秒/各4秒/既定間隔3秒を増やさず、正規Access redirectを**3回連続**観測した窓だけready。初回404後は残り2回しかないため、そのattemptではreadyにならない。302候補の後に404が再発したら即STOP。
- 連続観測は有限窓での観測に過ぎず、安定稼働や全パス保護の証明ではない。security_tests_passedは常に0。独立ゲートは引き続き必須。
- rootの独立試験を同じbounded collectorで実装し、cache=no-store、Cookie/認証なし、redirect=manualを統一。cache条件は旧試験から変更するので将来の比較で明記する。no-storeは中間cacheの不存在の証明ではない。
- `access-origin-diagnostic.mjs`：将来のWindows runner用のオフラインadapter。既定fetch/CLI/資格情報/URL操作なし。必須preflightが不一致ならHTTP0。新protocol `access-origin-diagnostic-v2` とfresh directory内の排他的markerを使用し、既存attemptを見つけたら拒否。準備3回＋独立root1回の**最大4要求/HTTP部最大19秒**。認証要求を行うcallbackは存在せず、root限定の診断完了を全保護/CPU合格にしない。必ずcloseの真偽を要求し、閉鎖不明は最優先STOP。
- 旧RUN_FIRST.ps1/first.mjs/packet/markerは更新・再実行しない。実アカウントpreflight、独立watchdog、期限・閉鎖を担うhostへの接続/組立は次回承認後の別段階。今回、安全な実行用live ZIPを新規提供したとは報告しない。
- 既存positive試験1件は3連続redirectという新しい厳しい成功条件へ更新。元の404→302→404と404→302→302を新規否定試験にし、旧否定試験・JWT/D1/OPTIONSの期待値を維持。削除/skip/拒否条件緩和なし。

## 記録・プライバシー

保存するのはstatus、MIME分類、本文bytes/SHA256、開始/終了UTC・monotonic経過wall time、許可origin/path一致分類のみ。生Location/query、Cookie/Set-Cookie、JWT、Service/API credentials、メール、生HTML、任意ヘッダー/例外文は記録しない。

追加ヘッダーは`server`（cloudflare/other分類）、`cf-ray`（hex+3文字codeの形式検査）、`cf-error-type`（3〜5桁数字）、`cf-error-origin`（短い固定分類/other-redacted）、`cf-cache-status`（固定enum）、`Age`（0〜999999999秒）、`cf-mitigated`（challenge/other分類）のみ。未知値は隠す。エラー/mitigationヘッダー付き応答は停止する。

Ray IDは時刻と合わせたprovider側照合の手掛かりであり、ユニーク性や当Workerの実行証明ではない。Server:cloudflareも同様。`worker_execution=not-established`を保存し、実行ログと照合できた場合だけ別の証拠で扱う。ログなし/サンプリングによる未検出を「実行0」の証明にしない。wall timeはCPUではない。

## 試験・保護

必要8ケース（連続302、404→302→404、404のみ、不正転送先、想定外HTML/JSON、途中timeout、閉鎖失敗、Access条件不一致）に加え、独立root再発、過去marker保存、header秘密値遮断、timestamp、ASSETS404変換を検証。既存Windows/Ubuntu comments jobで新試験をimportする。ローカル45診断試験/76コメントNode/41Pythonと保護照合が成功。起動時のjose/pytest欠落・旧venv interpreter欠落も`local-tests.json`に保持。全Python・ブラウザ等は最終HEADの自動CIで確認し、不要なローカル総合再実行/CPU再計測はしない。

Worker/registry/JWT/SQL/manifest/build.py/管理室clientは開始HEADとバイト一致（`runtime-hashes.json`）。写真933、Best Shot17、NEW14、研究室66、退役7、master141、sources419、本番コメントOFFを保持（`protection.json`）。旧11 workflows/13 jobs成功を基準とし、新HEADのCI結果はPR監査コメントに追記する。CI未完了を先に成功と書かない。

## 次回：最小限の実操作と承認案（未実施）

**まずrootのみの無資格情報診断を独立して行う案を推奨。Service Tokenはこの段階では不要。** 今回発行/操作せず、次の明示承認前に実施日時と絶対期限を確定する。

| 項目 | 提案・制約 |
| --- | --- |
| build token名 | `kinoko-comments-origin-diag-build-<実施日YYYYMMDD>`、新規1件。旧token再利用なし |
| 必要権限 | 今の専用Worker1件だけIndividual Workers Editor（URL開閉/閉鎖検証に必要）。同一accountのAccess apps/policies/service tokensはRead-only、D1は固定SELECT用Read-only。Billing/DNS/Pages/Turnstile/Access編集/他Worker編集なし |
| 有効期間 | 実施開始から最大30分、発行前に固定の年月日・時刻JSTを別承認。期限延長なし、終了直後に削除を確認。期限まで置いておかない |
| 過剰に含まれる権限 | Worker Editorには当Workerのdeploy/settings変更も含まれるが今回はURL開閉以外をallowlistで拒否。権限が1Workerへ限定できなければ停止 |
| Service Token | root診断は不要。全未認証保護とCPU測定計画が成立し、次段階承認を得てから別の新tokenを最大1hで作る。既存専用Service Auth参照だけ本人Dashboardで交換・復旧。本人Allow不変 |
| secret入力 | 本人Windowsの伏字入力・process内のみ。チャット/Work/Git/logへ渡さない。終了時にenv/clipboard消去 |

手順：閉鎖状態でFree/flags/version/worker-first/全Access優先関係/D1不変を読み取り確認→過去証拠をSHAで結び新marker→独立watchdog/絶対期限確認→対象Production URLのみ限定有効化→無認証root最大4要求でメタデータ取得→必ずURLoff読返し・Access/flags/D1不変・token削除。Preview/route/custom domainは追加しない。設定矛盾は修正せずSTOP。deploy/migration/seed・コメント/Turnstile操作なし。

最初の404は未分類観測で、そのattemptではreadyへ進めない。302後の404再発、未知HTML/JSON、誤転送/追従、timeout、CPUエラー、Access/scope/lease不一致、証拠改変、閉鎖失敗はSTOP。資格情報の送信・URL再開・同一attempt再試行なし。閉鎖失敗は最優先のセキュリティ問題として本人へ報告する。

CPU/Service Auth/OPTIONSへ進むには、root有限窓に加え全URL/メソッドの独立した未認証拒否、全Access設定一致、閉鎖能力・残期限、別承認が必要。root4要求の完了だけで進まない。Service Auth成功と別管理Bearer分離を極少数要求で確認した後、provider CPU指標と対応要求窓を評価する。cold/warmと種別の識別限界を記録し、Free10ms未達ならPaidへ移らず停止。OPTIONSはAccess外周・Worker内部・同一originブラウザ・Python server-to-serverを分け、旧403を保持。今回これらはすべて未実施。

## 一次資料（2026-11-04、公開docsのみ）

- [Worker Accessと優先順位](https://developers.cloudflare.com/workers/configuration/cloudflare-access/)：hostname/path→Worker→account。Worker destinationは対象Worker全trafficを保護するが、より具体的なappが優先する。
- [Static Assets binding](https://developers.cloudflare.com/workers/static-assets/binding/)：run_worker_first=trueはscriptを先に呼ぶ。ASSETS.fetchにもHTML/not-found設定が適用される。
- [workers.dev](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/)：route有効/無効とpreview/version経路は別。データ経路の反映時間や本件404を保証していない。
- [Error diagnostic headers](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-error-headers/)：cf-error-type/originをprovider生成エラーの識別に使える。過去未保存ヘッダーを後から推測しない。
- [Ray ID](https://developers.cloudflare.com/fundamentals/reference/cloudflare-ray-id/)：時刻付き照合の手掛かり、ユニーク保証なし。
- [Workers権限](https://developers.cloudflare.com/workers/authorization/workers/)：API tokenにもIndividual Worker scopeがある。次回発行画面で改めて対象/権限を確認する。
- [一般proxy向け404説明](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-404/)：本件Workersの実行経路を断定する資料ではない。

終了時のCloudflare状態は前回の停止証拠を維持（URL/Preview無効、READ/WRITE=false、not-approved、Access維持、Service Disabled/参照復旧、build token削除）。**今回再接続して確認したという主張はしない。**
