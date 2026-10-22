# コメント隔離環境：Access通信の実装とZero Trustの承認境界

2026-10-22。PR #136は設計資料としてそのまま保持する。本書はその3つの不整合を解消するコードの説明であり、Cloudflareへの作成・契約・公開を承認するものではない。

## 構成と変更範囲

| 経路 | 本番 | 隔離検証 |
|---|---|---|
| UI/API | 既存Pages UI、credentials=omitを維持 | 専用Workerの同一HTTPS originのみ。生成したJSだけsame-origin、redirect=error |
| ケース照合 | 固定の本番Pages manifest URL制約を維持 | staging専用entryが同梱の凍結manifestを渡す。本番Pagesへの問い合わせなし |
| 管理室 | 従来の専用Bearer、localhost限定 | Python側でAccess service token 2ヘッダー＋専用管理Bearer。ブラウザに秘密を渡さない |
| Access | 本番への追加設定なし | 全パスで署名・issuer・AUD・exp・iat/nbfを検証。Static AssetsにもWorkerを先に通す |

本番の `comments/public-config.json`、`comments/wrangler.jsonc`、`assets/research-comments.js`、日次生成workflowと保護データは変更しない。共通Workerの変更はmanifest読取関数の依存注入のみ。デフォルトは従来の固定HTTPS Pages URLとredirect拒否で、環境変数やHTTP要求ではstagingポリシーを選べない。

### CookieとUI

`python comments/staging/build.py` は `comments/staging/generated/` に検証用HTML、同一origin限定JS、CSS、合成SVGだけを生成する。公開JSは書き換えない。公開JSの期待する変換位置が変わればビルドを停止する。画像は全て合成で、実ユーザーの本文や写真を複製しない。ケースIDと公開名称だけ既存registryを参照する。

`STAGING_ORIGIN` と要求URLのoriginが完全一致することを入口で確認する。`kinoko-comments-staging-….<account>.workers.dev` だけを許容し、preview別ホスト・本番Pages・任意ドメインは拒否。UI/APIを別originに配置する設定は用意しない。UIのconfigはサーバー生成で、API URLがlocation.originと異なる場合、外部APIへの接続前に停止する。Access CookieはHttpOnlyのままブラウザが送信し、JSで読み取らない。Access service tokenや管理BearerをUIへ埋め込まない。

全パスは `Cf-Access-Jwt-Assertion` をjoseで署名検証する。RS256限定、team domainをcloudflareaccess.comの固定HTTPS originに制限し、鍵取得先はその `/cdn-cgi/access/certs` のみ。issuer・AUD・期限・未来iat/nbf・必須claimを検査する。JWKSは3秒timeout、redirect拒否、5分cache。鍵の取得失敗や未知kidで拒否し、Cookieやメールヘッダーの存在だけで許可しない。`ctx.access` に依存しないためStatic Assets内部routerの制約を回避する。

Wranglerの `assets.run_worker_first=true` が必須。静的ファイルも認証後に許可リストからだけ配信する。CSPで外部スクリプト/フレーム/通信をTurnstileに限定し、HTMLへの埋込、外部フォーム送信を禁止。全応答はno-store。Accessログインへ転送されたfetchを追わず、入力・削除キーを保持したエラーにする。

### 凍結manifestとD1

`comments/staging/manifest.json` は現行66 ID・registry SHAの凍結値。レビューなしに日次更新しない。API/UIを処理する前に以下を照合する。

- 同梱 `comments/cases.json` の正規化SHA、凍結manifestのSHA、設定のREGISTRY_SHA256、D1 metadataのSHAが一致。
- D1のinstallation_idが承認済みstaging DB固有の `STAGING_INSTALLATION_ID` と一致。
- 全ケースIDと記事/写真アンカーhash、全alias対応、active ID集合が完全一致。

照合は3秒を超えたら停止。不明ID・余分なケース・alias追加/衝突・異なるDB/registryは読取・管理操作も許可しない。新しいDBの初回migration3本を使い、既存DBへseedを再適用しない。IDや実データを自動修正しない。将来対応表が変われば別PRで凍結値とDB migrationの整合をレビューする。

同じアカウント内でも本番とDB・installation ID・秘密・flagsを共有してはいけない。installation IDの照合は取り違え対策で、設定を扱う管理者の権限を代替しない。現段階では本番もstagingも作成・デプロイしていない。

### Windows管理室の接続

実Windowsの更新・既存下書きの移動は今回実行しない。後日の承認済み更新後、管理室を起動するプロセスに次の環境変数を設定する。実値をGit・チャット・JS・スクリーンショット・コマンド履歴へ貼らない。

| 変数 | 用途 |
|---|---|
| KINOKO_COMMENTS_TRANSPORT | staging-accessを明示 |
| KINOKO_COMMENTS_API_URL | 承認済みstaging originのみ |
| KINOKO_COMMENTS_STAGING_ORIGIN | 上と完全一致する固定接続先 |
| KINOKO_COMMENTS_ADMIN_TOKEN | 専用Workerのstaging管理Bearer |
| KINOKO_COMMENTS_ACCESS_CLIENT_ID | 当該Accessアプリに限定したservice token ID |
| KINOKO_COMMENTS_ACCESS_CLIENT_SECRET | 同service token secret |

一部欠落、接続先不一致、HTTP、パス/query/userinfo/非443port、改行入り秘密、未知transportは送信前に停止。directモードではAccess環境変数が残っていても送らず、設定不整合として停止する。UIリクエストで接続先・header・transportを指定できない。

接続先はAccessの**Service Auth**ポリシーで当該短期service tokenだけを許可する。`Authorization` は既存アプリ管理Bearer専用に残し、Accessは `CF-Access-Client-Id` と `CF-Access-Client-Secret` の2ヘッダーを使う。CloudflareアカウントAPI tokenとは別。公開UIのCookieセッションと混用しない。302等の転送は追わず、401/403・HTML応答・timeout・巨大/不正JSON・署名不一致は具体的な安全エラーにする。認証・SQL・ネットワークの生エラーに含まれ得る秘密は表示しない。

localhost限定・Host/Origin/CSRF、既存下書きの自動保存・復元・Draft PR作成経路は変更しない。管理室をTunnel・ポート転送・0.0.0.0等で公開しない。

## 承認後に使う設定例（現在実行しない）

`comments/staging/wrangler.example.jsonc` は実アカウントなしの閉鎖テンプレート。入口・DB名は本番と分離し、workers_dev/preview=false、READ/WRITE=false、RELEASE=not-approved、DB IDはplaceholder、remote=false。secretは一切記入しない。自動デプロイworkflow・Cloudflare権限・secretをGitHub Actionsに追加しない。

後日、別途承認された範囲でのみ、リポジトリ外またはignore対象の設定コピーへ専用名・DB ID・origin・Access team/AUD・installation ID等を指定する。保護なしのHello Worldを先に公開する方法は使わない。Access全URL保護とWorker自身のJWT拒否を維持し、匿名のUI/API/static/preview拒否を確認してから、stagingのみに受付を一時有効化する。実Turnstile検証、remote migration、デプロイは別承認。

終了時はstaging READ/WRITE=false、RELEASE=not-approvedへ戻し、新規投稿拒否を確認する。本番受付のfalseは解除しない。本人削除は既存仕様に従い有効な削除キーで許可されるが、stagingのAccess認証を迂回できない。管理者APIも公開flagsから独立した従来の認証が必要。

## Zero Trust Free：次に管理者が確認する操作

現状はログイン・メール認証完了（認証は管理者報告）、Workers Free Active、支払い方法なし、Worker/Pages 0、D1 0、Turnstile既存表示なし、Zero TrustはWelcome画面までを管理者提供画像で確認した。こちらのクラウドブラウザに同じログインが共有されたわけではない。

1. 普段のログイン済みブラウザでZero TrustのWelcome画面を開く。
2. **Get started** を押し、最初に出た画面を確認する。この段階では画面確認・無料選択肢の調査だけが承認範囲。
3. チーム名が先に必要な場合、入力/Nextが組織作成・名前確保に当たるか確認できるまで送信しない。候補名は `kinoko-comments-staging`（未取得・未確定）。その画面を管理者と確認する。
4. プラン比較が表示されたら **Zero Trust Free / $0** の存在、請求周期、席数、追加オプションや自動有料化の有無を読む。カード登録や契約確定と一体になっているボタンは押さない。無料でも契約確定は未承認。
5. **支払い情報・カード・PayPal・請求先情報の入力画面で停止**。入力・保存・購入・契約確定を行わず、秘密を隠した画面と表示料金を報告する。カードの自動入力も実行しない。
6. Freeが見当たらない、料金が$0でない、すでに契約がある場合も停止する。迂回のための別アカウント作成や既存設定変更を行わない。

2026-10-22確認のCloudflare公式手順では、Zero Trust Freeでも初期設定に支払い情報が必要と説明されている。Free選択時は課金しない旨の説明はあるが、今回の「カード登録・契約確定は未承認」という境界を越える理由にはしない。確認だけなら追加費用は発生させない。正式な加入・席数・将来の変更の判断は別途行う。

こちらの普段のブラウザ接続は現在未成立、クラウドブラウザは過去にセキュリティ検証で停止している。接続できていると装わず、必要箇所は管理者の画面共有で案内する。ログインやセキュリティ検証を無限に繰り返したり回避したりしない。

## ローカル/CI検証と未検証の区別

```text
npm ci --prefix comments --ignore-scripts --no-audit --no-fund
python -m pytest -q
python comments/staging/build.py
node --test comments/tests/api.test.mjs comments/tests/staging.test.mjs
node tests/browser/research_comments.cjs LOCAL_DIR
node tests/browser/comments_staging.cjs STAGING_LOCAL_DIR
```

Node24、Python3.11以上。ブラウザ試験は隔離したPlaywright/Chromiumを用いる。実JWT署名検証、SQLiteマイグレーション、ブラウザのHttpOnly Cookieとfetch、既存localhostサーバー・CSRF・Pythonプロキシを使う。Access edge・証明書API・Turnstileはローカル合成応答で、Cloudflareアカウント・Workers・D1・Turnstile・Accessには接続しない。Windows/UbuntuのCIと実Windows端末の設定確認も区別する。

実CloudflareのAccessポリシー・実Turnstile・D1 remote migration・Worker経路と無料枠・Android実機は未検証。PR #136の17項目試験表を引き継ぎ、環境構築の別承認後に実施する。本番Pages・写真・Best17・NEW14・研究同定・ID対応表に書き込まない。

## 一次資料（2026-10-22確認）

- https://developers.cloudflare.com/cloudflare-one/setup/ （Freeも支払い情報が必要）
- https://developers.cloudflare.com/workers/configuration/cloudflare-access/ （Static Assetsとctx.access）
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/ （JWT検証）
- https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/ （2ヘッダー・Service Auth）
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/ （Cookie）
- https://github.com/panva/jose （署名検証ライブラリ、固定version/lockfile）
