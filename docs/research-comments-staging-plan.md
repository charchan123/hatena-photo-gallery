# コメント機能：隔離Cloudflare検証の承認用計画（2026-10-22）

**状態：設計・読み取り調査まで。Cloudflare未ログイン、外部リソース未作成、実環境テスト未実施。**

開始mainは `090eac16c25129695452a10a076532c752d8bd27`、gh-pagesは `35f2c8589553555890a82220e0c73304b017fd35`。mainはPR #135のマージコミットで、実装treeは #135最終HEADと同じ。既存の[導入手順](research-comments-workers-d1.md)と本計画を併読する。本計画は公開承認でもdeployスクリプトでもない。

## 現時点で確認できたこと・できないこと

- 公開 `research-comments-config.json` は enabled=false、API URLとsite keyは空、release_approval=null。
- 本番用Wranglerは workers_dev=false / preview_urls=false / READ=false / WRITE=false / not-approved、DBはplaceholder。これらを変更しない。
- Cloudflareクラウドブラウザは `/login` を表示。既存アカウント・契約・D1・Workers・Zero Trustの有無は未確認。「ない」とは断定しない。
- 管理者が現在Android利用中でも、コード調査・資料・合成データ検証・承認後のクラウド操作はWorkで進められる。実Windowsの既存下書き更新・実機操作は後日別作業。

## 外部操作の承認を分ける

**承認1：Cloudflareへログインし、選択アカウント・無料プラン・既存リソースを読み取り確認する。** 秘密はチャットへ貼らずsecure sign-inで入力。新規登録・規約同意・支払情報・認証権限追加は承認1に含めない。

**承認2：確認できた具体的アカウントと以下の専用リソース・権限・費用を示してから、作成・secret登録・staging migration・deployを承認する。** 名前は提案であり未作成。同名が既にあれば上書きせず再確認する。

| 対象 | 提案名・範囲 | 作成・変更の内容 |
|---|---|---|
| Worker | `kinoko-comments-staging-20261022` 1個 | 合成写真の検証UIとAPI。独自ドメインなし、別staging設定。既存本番Worker名を使わない |
| D1 | `kinoko-comments-staging-20261022` 1個 | 空DBへ既存migration3本。66件の公開ケース対応のみ参照し、本文・通報・返信は合成データだけ |
| Turnstile | 同名の専用widget 1個 | 実staging hostnameだけ許可。専用site key/secret。本番用との共有禁止 |
| Access application/policy | `kinoko-comments-staging-20261022` | 検証Worker全URL・previewも保護。承認された管理者だけAllow、Everyone/Bypassなし。既存アプリを変更しない |
| Access service token | `kinoko-comments-staging-work-20261022`、短期 | 自動テストとWork内localhostプロキシ専用。Service Authはこのapplicationだけに許可。ブラウザ・Git・チャットへ配布しない |
| Worker secrets | ADMIN_TOKEN / RATE_SECRET / TURNSTILE_SECRET | 各々別乱数・staging専用。管理API tokenとCloudflare account API tokenは別物 |
| ローカル設定 | Work内の限定ファイル・プロセス環境 | アカウントID/DB ID/Access AUD/hostname/秘密はリポジトリ外。権限600。実値入り設定をコミットしない |

作成に必要なCloudflare API権限はアカウント内のWorkers Scripts、D1、Access Applications/Policies、Access Service Tokens、Turnstileに限定する。ただし新規アカウントトークン発行は別の資格情報付与なので対象・期限を具体化して承認する。既存APIキーを探したりコピーしたりしない。GitHub ActionsへCloudflare秘密を登録しない。CLI/APIか画面操作かはアカウント確認後に選び、いずれも承認済み範囲だけで操作する。

無料Workers・D1・Turnstile・Zero Trustを優先。Zero Trustの初期設定ではFreeでも支払情報を求める旨が公式手順にある。既存Free組織がなければ、この手続きが必要か画面で確認し、支払情報や契約同意の段階で停止して管理者判断を求める。有料変更・カード登録・独自ドメイン購入を自動実行しない。新しいFreeアカウントを勝手に作らない。

## コード・環境の不整合と修正案

現行コードをそのままAccess付きURLへ配置しても、要求どおりの隔離検証はできない。以下を解決するまでdeployしない。今回の資料PRには実装を混入させず、必要なコードは独立Draft PRで検証する。

### 1. Access Cookieと公開コメントJS

`assets/research-comments.js` のAPI fetchは `credentials: "omit"`。AccessのCookie認証にはCookie送信が必要であり、同じoriginでもこの設定は送信しない。別originからのAPIは第三者Cookieやpreflightも問題になる。

修正案：検証UIとAPIを**同じstaging origin**へ配置する。検証専用ビルドだけ `same-origin` を指定し、API URLが自身のoriginと完全一致しなければ停止する。公開用JS・本番configを変えず、生成物の差分とhashを監査へ残す。Accessを外す、Everyone許可、秘密headerをJSへ埋める方式は禁止。CORSは引き続き明示originだけを許可し、ワイルドカードを使わない。

### 2. 本番Pages固定manifest

`comments/worker.mjs` の `active()` は本番Pagesのhost/pathを固定している。完全に隔離したstaging manifestのURLを指定すると拒否される。

修正案：staging専用entryと設定を作り、承認済み66ケース・registry SHAの**凍結manifest**を同じ隔離環境で用意する。検証用のmanifest取得方針だけを明示的に注入し、本番entryの固定URL制限は維持する。外部から渡したURLを任意fetchする汎用bypassは作らない。registry SHAをD1 metadata・manifest・設定で照合し、別registry/不一致/不明IDは拒否する。

注入を使用する検証では、本番Pagesへのmanifest HTTP取得まで実環境確認済みとは報告しない。検証時は本番Pagesを変更せず、本番API・DBへアクセスしない。

### 3. Accessとlocalhost管理室プロキシ

`admin/comments_client.py` はアプリ管理Bearer認証だけを送る。Accessが前段にあるとリダイレクト拒否等で安全停止する。

修正案：Work上で127.0.0.1限定の管理室を起動し、**検証専用サーバー側transport**からAccess service tokenの2 headerと専用管理Bearerを送る。接続先を承認済みstaging originへ固定し、redirect拒否・Origin/CSRF/Host確認を維持する。秘密はブラウザへ返さない。Windows管理室本体をトンネル、ポート転送、外部host bindで公開しない。

### 4. Accessの証明と配信経路

AccessをWorker単位のAll trafficで保護し、認証なしのAPI・UI・static・previewを先に拒否確認する。アプリも検証entryでAccessの証明を検証し、未設定/期限切れ/誤AUD/偽造headerで閉じる。Static Assetsのrouter経由ではctx.accessが渡らないという公式制限があるため、ctx.accessの存在だけに依存した構成にしない。署名済みAccess JWTのissuer/AUD/exp/署名を検証する方式か、対応する配信方式を選び、実環境で確認する。JWT本文やメールは監査へ記録しない。

### 5. 実Turnstileと自動テスト

現行Workerは既知のダミーsecretを拒否する。この本番保護を緩めない。実staging widgetの成功は承認された管理者の操作で取得した新しいtokenを実Siteverifyで検証し、hostname/action/期限/再利用拒否を確認する。自動ブラウザがbot判定される可能性があり、その場合は人間確認を管理者へ引き継ぐ。ダミーキー・モック成功を「実Turnstile成功」に数えない。実widget検証と、合成tokenによる失敗・欠落・timeoutの試験を別に記録する。

## 承認後の構築・終了手順

1. 対象アカウント、Free、既存リソース一覧を記録。アカウント・DB ID・hostnameはローカル台帳に保持し、公開レポートは名前と状態だけ。
2. 不整合を解消するstaging専用コードのDraft PR・ローカルテスト・CIを完了。本番entry・生成workflow・保護データのhashを比較。
3. 承認2の範囲でD1/Turnstile/Access/秘密を作る。WorkerはREAD/WRITE=false、routeとpreview無効から開始し、アプリ自体も認証必須で閉じる。承認前に公開Hello Worldを作らない。
4. 対象DBの名前・IDを照合してから、staging専用設定を明示してmigration3本を適用。defaultの `comments/wrangler.jsonc` に対するremote実行は禁止。D1のinstallation_id、66 cases、aliases、registry SHA、FK/triggerを検証する。
5. AccessのAll traffic、特定管理者・限定service tokenだけを許可。独自routeなし、preview無効を維持。未認証拒否を確認できるまでUI/APIを有効にしない。新Worker以外のAccessを変更しない。
6. 実Turnstile hostnameを照合し、staging内だけREAD/WRITEを一時有効にする。連打試験は小規模で既存3/分・20/日の制限を維持し、試験を分割して実行。回数枠を緩めない。ページング用21件以上の合成レコードは、承認したstaging DBへのfixture seedとして用意し、投稿制限を回避した本番APIの試験と混同しない。
7. [試験表](../audit/research-comments-staging-2026-10-22/test-matrix.json)を実行。実API・実D1・実Turnstile・障害注入・mock・Android実機の証跡を区別する。秘密付きcurl、raw HAR、token付きURLやログをGitHubへ保存しない。
8. 終了時はstaging WRITE=false、READ=false、releaseをnot-approvedへ戻し、Access保護を残す。新規投稿を拒否すること、本番Pages enabled=falseを確認。必要ならrouteも無効化する。エラーで終了しても最初に受付を閉じる。
9. ステージングDBの本人削除は合成コメントに限定。DB自体の削除やservice tokenの失効などは対象を提示し別承認を得る。検証用リソースは勝手に消さず、保存・破棄期限を決める。

## 費用・データ・実機確認

提案する検証は無料枠内の月0米ドルを目標とする。有料プランや従量契約へ変更しない。Freeでも利用上限による停止があり、無料を無条件に保証するものではない。課金プランが既に選ばれているアカウントは確認して停止する。カードが必要なFree手続きへの同意も別判断とする。

D1へ実ユーザーの本文・名前・IP・削除キーを移さない。既存の公開66ケースIDと対応hashは参照用に使い、写真は合成画像とする。認証時の管理者identityとCloudflare自身のログ保持は契約の対象であり、検証コメントとは別に扱う。アプリのログへidentityやsecretを出さない。

| Androidだけで管理者ができること | Workが担当できること | 後日Windowsで必要なこと |
|---|---|---|
| 承認、secure sign-in、必要なMFA、Accessログイン、実Turnstile操作、保護された検証画面の実機確認 | GitHub照合、コード/資料、隔離Cloudflare操作（承認後）、API/DB/ブラウザ試験、localhost管理室の代理検証、署名確認、監査 | 既存PCの下書きバックアップと安全更新、環境変数設定、実Windows上の管理室からの接続、保存先/端末固有の操作確認 |

Android通知・返信の新管理画面、名前所有権、調査時系列は[後続設計](research-comments-roadmap.md)だけ。今回新設・本番実装しない。

## 一次資料（2026-10-22確認）

- Workers AccessとStatic Assets/ctx.access制限：https://developers.cloudflare.com/workers/configuration/cloudflare-access/
- Access CORS：https://developers.cloudflare.com/cloudflare-one/troubleshooting/access/
- Access service tokens：https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/
- Zero Trust初期設定とFreeの支払情報：https://developers.cloudflare.com/cloudflare-one/setup/
- Freeプラン：https://www.cloudflare.com/plans/
- Workers料金：https://developers.cloudflare.com/workers/platform/pricing/
- D1料金：https://developers.cloudflare.com/d1/platform/pricing/
- Turnstile料金：https://developers.cloudflare.com/turnstile/plans/
- Turnstile自動試験の制約：https://developers.cloudflare.com/turnstile/troubleshooting/testing/
