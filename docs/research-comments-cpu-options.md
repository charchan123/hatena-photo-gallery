# staging CPUとOPTIONSの検証境界（2026-11-01）

2026-11-04追記：[前回のHTTP404停止と準備確認のオフライン改善](../audit/comments-access-readiness-20261104/README.md)。元の403/CPU未達を保持し、HTTP経路準備確認を独立させる補助コードと試験を追加した。Cloudflare再接続・再試験は行っていない。以下は11月1日当時の記録。

今回はPR137のオフライン修正だけ。Cloudflareアカウント接続、token発行、URL有効化、migration、既存D1再seed、deploy、設定変更は行わない。実試験スクリプトを再実行しない。実環境再試験は別承認。

## 実環境の失敗履歴を維持

基準HEAD：`582a6c19e136fe5f7f6b2c2448cb0f63f14d1235`。提供された `kinoko-cloudflare-staging-audit-20261101.md` を基準にした。

- 既存29件成功、最新16/17成功（2件の追加否定試験＋14件の認証済み成功）。累計45は重複観点を含む。
- `AUTH_TEST_AUTHENTICATED_OPTIONS_FAILED`：204期待、実際HTTP403、APP_ERRORなし。この失敗を消したり成功へ変更したりしない。
- 実CPU：15 invocations、P50 10.08ms / P90 19.29ms / P99 23.53ms、CPU超過エラー0。10ms条件は未達。修正後の実Cloudflare CPUは未測定。
- 前回の閉鎖記録：URL/Preview無効、READ/WRITE=false、release=not-approved、Service Token全件Disabled、構築API token削除済み。今回再接続で確認したという主張はしない。

## CPU削減の比較と選択

| 方法 | 判断 |
|---|---|
| ハッシュ期待値のビルド時ファイル生成 | 初回も軽くできるが、registry/manifest/生成物の同期管理と信頼対象が増える。今回は不採用 |
| ビルド時の検査だけで実行時検査を省略 | 手順を通らないbundleへの防御が減る。実行時初期検査も残す |
| 固定期待値のisolate内再利用 | 既存の全体SHAと66 identity検証を残せる。新たな生成物なし。採用 |
| 可変D1結果のTTL cache | 次要求での改変検知を損なうため禁止、不採用 |

`createRegistryChecker()` は固定registry/manifestをprivate snapshotへ変換する。最初の認証済み要求で全体SHA・manifest version/active IDs・66 identity hashを検査し、期待するcases/aliasesの正規化文字列だけを保持する。lazy promiseは同時初回要求で共有し、失敗も保持して閉鎖する。WebCryptoは要求コンテキスト内で起動する。

毎回のJWT検証後、D1 metadata・全cases・全aliasesをそれぞれSELECTし、現在のinstallation/schema/registry SHAと全行を照合する。DB読取結果・JWT認証結果のcacheは追加しない。既存JWKS cacheは公開鍵だけで、RS256・issuer・AUD・exp・iat・nbf検証は毎要求行う。3秒timeoutと異常時503を維持する。

通常要求の固定SHAは67→0、初回は67のまま。D1全件読取は3→3。期待値側のsort/canonicalを初期化へ集約し、現在のDB行の正規化比較は維持する。

```sh
node comments/staging/benchmark-registry.mjs /tmp/comments-cpu-local.json
```

比較対象はgit object内の基準HEADのcheckRegistry関数そのもの。Node process.cpuUsage（user＋system）とwall timeを分け、in-memory SQLiteで100要求×7標本を実行順交互に測る。初回と新checker20個も別に測る。SHA/D1読取は実カウント。JWT・ネットワーク・実D1・Cloudflare CPUを含まない。速度の揺らぎでCIを通す閾値は置かず、67→0 / 3→3と改変拒否をテストする。

## OPTIONSを4経路へ分ける

| 経路 | 検証・合格条件 | 今回の証明範囲 |
|---|---|---|
| Access外周CORS preflight | 未認証でアプリ本文を取得できない。過去のACR-Method付き403は別の失敗履歴として保持 | 公式仕様と照合。ローカル境界モデルは拒否とWorker到達0を検査。実Access再試験ではない |
| Worker内部OPTIONS | 正しい署名JWT＋Origin＋ACR-Method/Headersで204・空本文・厳格CORS。JWTなし/不正Origin/管理OPTIONSは拒否 | Workerへ直接要求する単体試験。204期待を維持 |
| stagingブラウザ | HTTPS同一origin UI/API、HttpOnly Cookie、same-origin credentials、redirect=error。GET/JSON POSTが成功しOPTIONS発行0 | 実Chromium＋ローカルSQLite/署名JWT。Cookie omitは拒否、投稿/表示/ページ送りを別途検証 |
| Windows localhost管理室 | ブラウザ→localhostは既存Host/Origin/CSRF。Python→WorkerはService Auth 2ヘッダー＋別Bearer。Origin/Cookie/ACR-Methodなし | 同じPython管理室をLinux/Windows CIで実行。ローカル接続アダプタ経由の返信/管理/backupを検証。本人PCは操作しない |

公式CORS資料は、ブラウザのcross-origin preflightには認証Cookieが付かず、Access配下ではログイン済みでも403となると説明する。過去の手製要求はService Authも付いており、その個別403の根本原因まで公式の一般説明だけでは確定できない。APP_ERRORなしだけで処理層を断定しない。

**利用経路の変更は不要、検証の層分けが必要。** stagingの同一origin JSON POSTにCORS preflightは不要。Pythonのserver-to-server要求もブラウザCORSの対象外。機能成功とOPTIONS増加0を独立して証明する。新規ローカル403試験は漏えい防止の否定試験で、過去の実環境失敗を合格へ付け替えない。

Bypass、Everyone、email domain許可、未認証preflight応答、無制限CORS、JWT緩和は使わない。`access-snapshot.mjs` は11月1日の回復ガードを元にした純粋なオフライン検査。渡されたsnapshotの対象Worker・本人完全一致・専用Service Auth・preflight非迂回を検査し、不整合で停止する。APIクライアントではなく、実アカウントの現在状態の証明でもない。オフラインだけで外周の設定変更を検知できるとは主張しない。

## 維持・追加する安全試験

- warm workerでmetadataのschema/installation/registry SHA変更・欠落、case identity変更・case追加/削除、alias変更/追加/削除の次要求を拒否。ストレージ破損を再現するためのtrigger除去はin-memory fixtureだけ。実SQL/migrationは不変。
- registry/manifest/version/active IDsの破損、自己整合する改変bundleと元DBの組合せも拒否。
- warmでも毎回RS256検証を計数し、期限/issuer/AUD/iatの改変を拒否。
- Access snapshotの対象拡大、本人置換、Everyone/Bypass、Service Token置換、CORS/OPTIONS緩和を拒否。
- 既存の厳密な統合比較は維持。変更するworker.mjsとregistry.mjsの2ファイルだけ監査SHAへ更新し、それ以外の元staging runtimeは元PRのバイトを固定。本番・管理室・写真・LightGallery・日次同期・削除保護はmainとの比較を維持する。

## 別承認後に必要な実試験

1. Free契約・既存環境不変・専用閉鎖設定・All traffic・優先するhostname設定・token期限を確認。既存D1は履歴照合のみでseedしない。
2. JWT/実D1を含むcold/warmと実要求種別別のCPUを測る。ローカル削減率を実Cloudflare値へ掛け算しない。
3. 全経路未認証拒否、本人Cookieの同一origin GET/POST、Windows Python Service Authを実証し、実ブラウザのpreflightなしを確認。
4. 過去のACR-Method付き403は診断項目として保持。必要なら普通のOPTIONSやAccessログと切り分ける。設定緩和で通さない。
5. CPU/認証の条件を満たした後、実Turnstile・合成コメント一連・backup/ローカルrestore・Android/Windowsを検証。成功/中断とも閉鎖し専用tokenを失効。本番公開は別承認。

## 一次資料（2026-11-01閲覧）

- [Access CORS/preflight](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/cors/)
- [Worker単位Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/)
- [Service Auth headers](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)
- [CPU統計とrollover](https://developers.cloudflare.com/workers/observability/metrics-and-analytics/)
