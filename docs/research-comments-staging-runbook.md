# 研究室コメント：初回の非公開Cloudflare検証手順

更新：2026-10-31 JST。PR #137の最新main追従・準備作業。**この文書は実行承認ではない。今回の到達点はオフライン試験・CI・手順書まで。以下のCloudflare操作は一件も実施していない。**

## 現在の判断

| 区分 | 内容 |
|---|---|
| 確定 | PR #135はmainに統合済み。#137のAccess入口、同一origin通信、凍結registry、localhostプロキシを再利用する。#139・#140・正式トップを通常mergeで取り込む |
| 確定 | 本番公開config enabled=false / API・site key空。両WranglerのREAD/WRITE=false、not-approved、workers_dev=false、preview_urls=falseを維持 |
| 未確定 | 現在のCloudflare account、Workers/Zero Trust契約、カード保存・未確定請求、既存資源、team domain、AUD、実hostname、実Windows端末状態 |
| 仮定 | 管理者1名の少量検証。Workers Free＋D1 Free＋Turnstile Free＋Zero Trust Freeを利用できる場合に限定。既存の有料契約を変更する権限は含めない |
| 外部確認要 | Free有効化時の支払・超過同意の適用範囲、アカウントの実料金、All trafficの実ポリシー、Service Authの実JWT、実Turnstile、D1/CPU性能、Android・Windows実機 |

写真933 / Best17 / 通知14 / 研究66 / 退役7 / master141 / sources419 / WebP7を最新のmain・gh-pagesから照合。件数だけでなく保護ソース・公開portal（写真ID/URL/EXIFを含む）・manifestをhash比較する。[統合監査](../audit/pr137-main-followup-20261031/REPORT.md)を参照。数値が変われば原因を調べ、基準を黙って書き換えない。

## 必要なリソースと権限（すべて提案・未作成）

| 対象 | 提案 | 分離・権限 |
|---|---|---|
| Worker 1個 | kinoko-comments-staging-20261031 | staging/worker.mjs専用entry。新規の名前。production用Worker、routes、DNSに触れない |
| D1 1個 | kinoko-comments-staging-20261031 | 新規空DB。binding DB、固有installation ID。実投稿・写真はコピーしない |
| Turnstile widget 1個 | 同名、Managed | 確定したstaging hostname 1つだけ。本番widget/secretを共有しない。pre-clearance不要 |
| Access self-hosted application 1個 | 同名、当該WorkerのAll traffic | 管理者本人の正確なメール1件だけAllow。Everyone、全ドメイン許可、Bypassなし |
| Access Service Auth policy | 上のapplicationだけ | 当該短期service token 1個だけ許可。別application・アカウント全体に広げない |
| Access service token 1個 | kinoko-comments-staging-local-20261031 | 期限は検証期間以内で、画面で選べる最短を提案。Pythonプロキシだけで使う |
| Worker secret 3個 | ADMIN_TOKEN / RATE_SECRET / TURNSTILE_SECRET | 個別のstaging専用値。前2者は32文字以上の十分な安全乱数。TURNSTILE_SECRETは専用widgetが発行する値 |
| ローカル設定 | リポジトリ外またはignore対象の*.local.jsonc、プロセス環境 | secret・認証JWT・カード情報をGit/チャット/スクリーンショット/シェル履歴へ残さない |

Cloudflare account API tokenは構築時だけに必要となり得る別資格情報。選択account内のWorkers Scripts、D1、Access Apps/Policies、Access Service Tokens、Turnstileの必要な操作に限定し、権限名・対象・期限を承認表に列挙する。Billing変更・DNS変更・全アカウント権限は付与しない。ブラウザ操作で済む場合はCLI用tokenを新設しない。GitHub ActionsへCloudflare資格情報を登録しない。

## 設定値と認証経路

`comments/staging/wrangler.example.jsonc` はそのままでは閉鎖・未設定。実値の設定コピーだけを後日の承認対象にする。

| 設定 | 必須条件 |
|---|---|
| name / DB ID | 上の専用名・選択account・新規DB IDの組を照合。同名既存は上書きせず停止 |
| STAGING_ORIGIN | https://kinoko-comments-staging-20261031.<account-subdomain>.workers.dev（account-subdomainは未確定）。ホスト全体を完全一致させる |
| ENVIRONMENT / MANIFEST_URL | staging / staging:bundled。本番Pagesへmanifestを取りに行かない |
| ALLOWED_ORIGINS / TURNSTILE_HOSTNAME | 前者はSTAGING_ORIGINと完全一致、後者はそのhostnameだけ |
| ACCESS_TEAM_DOMAIN / ACCESS_AUD | 選択teamのhttps://<team>.cloudflareaccess.com / 当該Accessアプリの64桁AUD。空は拒否 |
| REGISTRY_SHA256 | 240e897c1edfddcef4d658f774885373be254c704c7f03b7535ac4f606bb10c5。cases.json・manifest・D1 metadataの4者一致 |
| STAGING_INSTALLATION_ID | 新規DBの初回seedが作った32桁値を、DB識別情報と照合して設定。別DBの値を再利用しない |
| TURNSTILE_SITE_KEY | staging専用の公開site key。HTML/configに公開可。secretはWorker secretだけ |
| 初回と終了時のflags | PUBLIC_READ_ENABLED=false / PUBLIC_WRITE_ENABLED=false / RELEASE_APPROVAL=not-approved |
| URLと配信 | 初回workers_dev=false、preview_urls=false、独自routeなし。assets.run_worker_first=trueを全パスに適用。観測ログ無効 |

ブラウザは同一originのUI/APIへHttpOnlyのAccess Cookieを送る。公開用JSのcredentials=omitは維持し、生成したstaging JSだけsame-origin＋redirect拒否。JSがCookie/JWTを読む必要はない。

Workerは全パスのCf-Access-Jwt-Assertionをjoseで検証する。RS256署名、固定team issuer、当該AUD、exp、iat、nbfを確認。鍵取得は固定teamの/cdn-cgi/access/certsだけ、3秒timeout・redirect拒否。不明kid・失効・未来時刻・鍵取得不能は403。存在するheaderやメールだけで通さない。Static Assets・config・manifest・OPTIONS・不明pathも認証前に返さない。静的許可リスト以外は認証後も404。

localhost管理室は既存Host/Origin/CSRF検証を維持。Pythonのstaging-access transportだけがCF-Access-Client-Id / CF-Access-Client-Secretを付け、Authorizationは別のADMIN_TOKENに使う。Access成功だけでも管理Bearerだけでも管理APIには入れない。環境変数6つは[既存Access資料](research-comments-staging-access.md#windows管理室の接続)参照。UI指定URL・secret注入・redirect・HTML応答を拒否。Windows管理室を外部公開しない。

## 2026-10-31確認の無料枠と課金経路

| 製品 | Freeの公表枠 | 超過・有料化の扱い |
|---|---|---|
| Workers | account共通100,000 requests/日、CPU 10ms/呼出 | Worker-firstは静的配信もWorker要求を消費。Free要求枠超過は429、CPU超過はエラー。Paidは最低$5/月＋要求・CPU等の従量課金 |
| D1 | 500万rows read/日、10万rows written/日、account合計5GB | Free超過時はquery/追加書込が停止。1DB 500MB・10DB。Paidでは月間読取250億/書込5000万・5GBの包含枠を超えて課金 |
| Turnstile | 20 widgets、各10 hostnames、challenge/検証要求は無制限 | Enterpriseは別契約。stagingは1 widgetのみ。widget枠超過を理由に自動契約しない |
| Access / Zero Trust | Free 50 users | 同一人物の再ログインは追加席なし。service tokenは席を消費しない。満席時は新規ログイン拒否。有料席・追加製品は別契約 |

日次Free枠はUTC 00:00（日本時間09:00）に更新。D1のindex・レート制限・audit・backup・Wrangler/ダッシュボードSQLも使用量に入る。1投稿=1行だけと見積もらない。RS256検証と66ケースの都度照合がFree CPU 10msに収まるかは実測前で未確定。超えた場合は停止して原因調査し、検証を通すためにPaidへ変えない。

**0円は目標であり、無条件保証ではない。** 現契約・保存カード・未確定請求を今回確認していない。他のWorkers/D1と枠を共有し、既存Paid契約・追加ログ製品・別サービス・ドメイン購入等には請求経路がある。Zero Trust Free初期設定も公式には支払情報入力が必要とされる。Freeの一般説明だけで画面の超過請求同意を承認済みにしない。不明ならBillingの書面回答を得るまで停止する。

Budget alertsは通知機能で利用停止・課金上限ではない。全製品共通の「$0で強制停止」が確認できたとは報告しない。Workers Logsは2026-12-01に価格体系変更予定なので、その日以後の再開時は再確認する。支払情報登録、規約/超過同意、プラン変更は検証リソース承認に自動包含せず、必要なら別判断にする。

## 次の作業段階：1〜10

**今回ここで停止する。1のための接続・ログインにも管理者の明示操作が必要。ログイン情報をチャットへ貼らせない。3以降は今回実行しない。**

1. **読み取り確認**：管理者の明示希望後に安全なサインインを引き継ぐ。accountを本人が選び、Workers契約、Zero Trust契約・席数、BillingのSubscriptions / Payment methodsのマスク状態 / Invoices / Billable Usage、既存Worker/D1/widget/Accessを読む。Activate/Save/Upgrade/同意は押さない。ログイン壁や確認不能なら未確認で停止。カード番号等を記録しない。
2. **具体化**：衝突しない名前、実host、account、Freeの可否、必要権限、検証期間、予想利用量、secret保管先をローカル台帳に確定。既存Paid・別account・枠不足なら、費用承認なしに進めない。下の承認表を実値に基づいて完成させる。
3. **別承認**：対象リソース・プラン・料金リスク・公開範囲・停止条件を管理者へ提示し、作成/secret/remote migration/deployの明示承認を得る。必要なFree有効化/カード/規約同意は別項目に分ける。
4. **閉鎖状態で構築**：新規D1とwidgetを用意。閉鎖テンプレートの専用Workerをworkers_dev=false・preview=false・routeなし・READ/WRITE=falseで初回配置する。URLを持たない閉鎖コードから開始し、公開Hello Worldを挟まない。専用WorkerへのAccess All trafficを設定する。管理者メール1件と限定Service Authのみ。既存hostname/pathアプリが優先して保護を上書きしないか確認。アカウント全Workerを一括変更しない。Access設定を確認するまでworkers.devを有効化しない。
5. **新規空DBだけmigration**：ID/account/name/configを二者照合し、SQL実行先のpreview_database_idや別envへの自動選択を使わない。専用設定を毎回明示し、0001_comments.sql → 0002_guards.sql → 0003_reviewed_cases.sqlの順にWrangler D1 migrationを適用する。事前にlistで未適用だけであることを確認。既存DB・非空DB・履歴不明・部分失敗では止める。execute --fileでseedを再投入しない。3件の適用履歴、schema_version=1、66ケース・全alias・全identity_hash、registry SHA、foreign_key_check、6 triggers、本文0を照合。生成されたinstallation IDを専用設定へ結び付ける。fixtureは合成本文・名前のみ、66公開IDは対応参照だけ。ページ送り用21件以上は別途承認した少量fixtureとして投入し、API投稿レート試験と区別する。
6. **外周・認証を先に実証**：正確なstaging hostだけworkers.devを有効化。previewは無効のまま。未認証UI/HTML/JS/CSS/SVG/config/manifest/API/admin/OPTIONS/不明pathでloginまたは401/403を確認し、アプリ本文を返さない。偽造header・別AUD・期限切れ・ログアウト後・既知preview/version/deployment URL・別host/route・HEADも確認。認証済み管理者CookieでUIが読めること、限定service token＋Bearerでlocalhost経由だけ管理操作が可能なことを確認。401/403/302/HTML/timeoutなら失敗として秘密を隠して記録する。実service JWTの検証に失敗したらJWT要件を緩めず止める。
7. **stagingのみ短期開放して試験**：外周合格後、承認範囲内でstagingだけREAD/WRITE=true・release=approved。実widgetを管理者が操作し、新規tokenで投稿/通報のSiteverify成功、失敗・欠落・5分超・同じtoken再使用拒否、hostname/action一致を確認。自動bot判定なら本人の手操作へ引き継ぎ、認証を回避しない。投稿/表示/20件paging/本人削除/通報/公式返信/非表示/復元/確認済み/重複防止/制限/不正入力を実D1で確認。バックアップは署名検証後に限定保存し、復元は新規ローカルDBだけ。remote restoreは承認に含めない。DB/manifest/JWKS/Turnstile障害・API障害の実試験と合成障害注入を区別する。
8. **実機**：AndroidでAccess login・Turnstile・投稿・削除・ページ送り・画面回転、Windowsで既存下書きのバックアップ後に管理室の接続・返信・保存・復元を確認。実GitHubへの不要なDraft PRを試験作成しない。既存Draft PR経路は隔離Git/browser回帰を根拠にし、端末固有設定だけ確認する。
9. **停止・非公開確認**：成功/失敗にかかわらずstaging WRITE=false→READ=false、release=not-approvedへ戻し、認証済みでも新規投稿/通報/公開一覧が拒否されることを確認する。Accessは残し、workers.devも停止し、preview/route無効を再確認。flagsだけでは管理API/本人削除を全停止しないので、URL閉鎖も行う。service tokenは承認した終了手順で失効、DBは保持/破棄方針の別判断まで削除しない。閉鎖不能なら最優先の障害として報告し、一般公開へ進めない。
10. **報告**：実環境/合成/未実施を区別して件数・失敗・費用状態・停止確認を記録。本番config=false・main/gh-pages不変を確認。本番公開は改めて別承認を待つ。PR #137はDraft・未マージのまま。

操作方法は利用時のWrangler公式ヘルプで確認し、migration/deployのコピー実行用コマンドに実secretを埋め込まない。今回実行できるのは次のオフライン操作のみ。

```sh
npm ci --prefix comments --ignore-scripts --no-audit --no-fund
python -m pytest -q
python comments/tools/seed.py  # オフライン再生成。差分なしを確認
python comments/staging/build.py
node --test comments/tests/api.test.mjs comments/tests/staging.test.mjs
python tests/browser/comments_integration_protection.py /tmp/comments-protection.json origin/main
# 固定版Wranglerを隔離インストールした後。認証/remoteフラグを付けない。
wrangler deploy --dry-run --config comments/staging/wrangler.example.jsonc --outdir /tmp/comments-bundle
```

## 次回の承認表と即時停止条件

| 承認項目 | 提示する内容 |
|---|---|
| 実リソース | 上記1 Worker・1 D1・1 widget・1 Access app・限定policy・短期service token・3 secrets。確定したaccount/名前/期間は次回提示 |
| プラン | Workers Free / D1 Free / Turnstile Free / Zero Trust Free。現契約は未確認。Paid・addon・支払操作は含めない |
| 費用 | 少量Free枠内の0円目標。既存契約・初期設定条件・将来価格・枠共有により無条件保証不可。疑義は契約前停止 |
| 本番影響 | はてな・Pages・本番Worker/DB・日次同期・写真・既存下書きに変更なし。公開コメント無効のまま |
| 公開範囲 | 管理者本人と限定machine credentialだけ。URLを知るだけでは閲覧不可。合成写真/本文のみ |
| 即時停止 | 有料表示/同意・未知資源衝突・匿名のHTML/API/static成功・認証回避・秘密漏出・registry/DB/alias差異・migration部分失敗・CPU/Free枠超過・本番変更・閉鎖不能 |

未認証で一度でも本文が読めたら受付を閉じ、URLを無効化して原因を調べる。テスト合格のためのAccess緩和、Everyone/Bypass、JWT検証削除、レート制限解除、Paid移行は採用しない。

## 一次資料（2026-10-31閲覧）

- [Workers料金](https://developers.cloudflare.com/workers/platform/pricing/)・[制限](https://developers.cloudflare.com/workers/platform/limits/)
- [Static Assets料金](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/)・[Worker-first配信](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/)
- [D1料金](https://developers.cloudflare.com/d1/platform/pricing/)・[制限](https://developers.cloudflare.com/d1/platform/limits/)
- [Turnstileプラン](https://developers.cloudflare.com/turnstile/plans/)・[サーバー検証](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)
- [Accessプラン](https://www.cloudflare.com/plans/)・[席管理](https://developers.cloudflare.com/cloudflare-one/team-and-resources/users/seat-management/)
- [Zero Trust初期設定](https://developers.cloudflare.com/cloudflare-one/setup/)・[Service tokens](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)
- [Worker全体/hostnameのAccess](https://developers.cloudflare.com/workers/configuration/cloudflare-access/)・[workers.dev](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/)・[Previews](https://developers.cloudflare.com/workers/previews/)
- [JWT検証](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/)・[Budget alertsは上限ではない](https://developers.cloudflare.com/billing/manage/budget-alerts/)

PR #136の[既存計画](research-comments-staging-plan.md)と[後続要件](research-comments-roadmap.md)を引き継いだ。通知・スマホ専用管理・名前所有権・調査時系列は設計段階のまま、今回実装しない。
