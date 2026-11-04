# 研究室コメント：非公開実装と承認後の導入手順

現段階は**Draft・未公開**。このPRをマージするだけではコメント受付は始まりません。Cloudflareアカウント接続、D1作成、secret登録、マイグレーション、Worker公開、ドメイン設定、公開設定の変更は、本書を確認した管理者の別途明示承認後に実施してください。本タスクでは実施していません。

Accessで保護する隔離検証環境は、[専用入口・通信設定・Zero Trustの承認境界](research-comments-staging-access.md)を参照してください。本番用の以下の設定手順をstagingへそのまま流用しません。

## 構成と運用

GitHub Pagesの研究室HTMLから、ケースの折り畳みを開いた時だけWorkersを呼びます。66ケース分を一括取得しません。コメント・公式返信・通報・監査履歴はD1へ保存します。写真・EXIF・記事・研究同定レジストリ・管理室の既存下書きはコメントDBへ移動しません。

Windows管理室の「研究室のコメント」からケース名検索、未確認コメント、通報・履歴、公式返信、非表示、復元、JSONバックアップを操作します。Cloudflareの画面を日常的に操作する必要はありません。管理者用WorkerトークンはPythonが環境変数から読み、ブラウザへ渡しません。CloudflareアカウントのAPIトークンは日常の管理室操作に不要です。

既存管理室のlocalhost・Host・Origin・CSRF検証を経由します。新たなコメント操作は既存Best Shot等の下書きやDraft PR作成経路を通さず、DB操作として明確に分離します。PR #134の保存・復元・PR作成処理は維持します。

## 永続IDとケース対応の承認

`comments/cases.json` は現在の公開66ケースを独立取得した対応表です。各 `id` は**現在のresearch case_idそのもの**で、再採番していません。

- 既存 `research_ui.build_research_cases()` のID計算・同定レジストリは変更しません。
- コメントIDのアンカーは記事の安定識別子＋写真observation_idの**完全な集合**です。名前・EXIF・画像URLでは照合しません。
- 表示上のcase_idは `render_ids` で明示的に許可します。元のIDは削除せず保持します。
- 名前変更でcase_idが変わった場合、写真追加・削除、統合・分割、記事識別子変更時は、自動で新しいケースへコメントを移しません。新しい紐付けは確認待ちとなり、従来のスレッドは「過去の研究ケースのコメント」で保管・閲覧できます。
- 同定レジストリで判明済みにしたケースは元のcase_idを維持するため、判明済み展示でも同じスレッドを使います。
- 管理室に紐付け確認待ち・保管件数を示します。新しいケースには対応表をレビューした別PRが必要です。

名前変更のみで、記事と全写真が完全一致することを人間が確認した場合に限り、同じ恒久IDの `render_ids` へ新しい表示IDを**追加**します。元ID・アンカーを上書きしません。統合・分割はこの単純aliasでは解決せず、別設計と明示判断が必要です。

`python comments/tools/seed.py` は対応表を検証して初回seed SQLを再生成する**オフラインのツール**です。既存DBへ初回seedを再適用しないでください。稼働後のalias追加は、アンカーを変えない専用D1 migrationと新registry hashの承認が必要です。対応表変更後は公開manifest・D1 metadata・WorkerのREGISTRY_SHA256を同時に照合するまで新規投稿が停止します。

日次同期はCloudflareへ問い合わせません。生成する `research-comment-cases.json` には現在有効な承認済み恒久IDだけを入れます。Workerは投稿前にこの固定GitHub Pages URLをGETし、registry hashとactive IDを検証します。取得失敗や差異では投稿だけを停止します。研究室・写真・日次同期の生成自体をAPI障害で止めません。

対応表の写真参照は既存の削除保護inventoryと未マージPRの保護対象にも追加しています。名前が確定した後も履歴写真が自動削除へ抜けません。この参照を解除する場合は別途レビューが必要で、研究アーカイブの承認だけでは自動解除しません。

## DB

初回migrationは `0001_comments.sql`（表・制約・index）、`0002_guards.sql`（返信・ID・削除保護trigger）、`0003_reviewed_cases.sql`（承認対象の66ケース）です。

| 表 | 保存する情報 |
|---|---|
| metadata | schema・registry SHA-256・DBごとのランダムinstallation ID |
| cases / aliases | 恒久ID・名称・記事/写真アンカーhash・旧/表示IDの対応 |
| comments | UUID、case_id、返信先、role、本文、名前、時刻、状態、削除キーhash、確認済み状態 |
| requests | 種別・要求ID hash・payload hash・結果ID（二重登録防止） |
| reports | 対象ID・理由・一時的な通報者hash・時刻 |
| audit | 対象ID・操作・管理者/投稿者・時刻。本文・名前・秘密を記録しない |
| limits | 期限付きの回数と匿名化key。生IPは保存しない |

各コメントの恒久ID・所属case・role・親・時刻は後からUPDATE不可。aliasの付け替え・削除もtriggerで禁止します。一般利用者は返信先・公式roleを指定できません。公式返信は認証された管理者APIのみが作り、一般投稿と別のバッジをサーバー由来のroleで表示します。

## 公開API

- `GET /v1/cases/:case/comments?after=SEQ`：古い順、20件ずつ。戻り値のnext_cursorで続ける。
- `POST /v1/cases/:case/comments`：nickname、body、request_id、delete_token、turnstile_token。
- `POST /v1/cases/:case/comments/:id/delete`：本人のdelete_token。
- `POST /v1/cases/:case/comments/:id/reports`：理由・要求ID・Turnstile。

本文500 Unicode文字、名前30文字、通報理由200文字。空白のみ・不正型・制御文字・過大リクエスト・未知fieldを拒否。名前は変更可能ですが、管理・公式・運営・admin等はNFKC正規化・空白除去後に禁止します。HTML/Markdownとして解釈せず、表示はtextContentだけです。SQLはbind済みprepared statementだけを使います。

投稿前にブラウザで256bitの削除キーを安全乱数で発行し、要求IDとともにlocalStorageへ保存します。DBにはコメントIDに結び付けたSHA-256 hashだけを保存します。URL・ログ・DOMにキーを出しません。キーはニックネームと無関係で、削除後はDB hashも無効化します。他の端末への自動復元はできません。同じoriginの悪意あるスクリプトやブラウザ保存データの消去からキーを保護することはできないため、公開前に同origin上の信頼しないHTML/JSを置かないことを確認してください。

送信結果が不明なら、要求ID・削除キー・入力を保持して同じ要求を再確認します。再送で新規登録せず、別payloadで同じ要求IDを使えば409です。投稿直後は古い順のページを保ちつつ、新しい自分の投稿をすぐ表示します。API障害ではコメント欄にエラーを出し、写真・リンク・研究室全体を維持します。

本人削除は名前・本文・hashを消し、関連通報の理由も消します。公開側に本文を返さず、最小限のtombstoneと操作履歴を残します。投稿停止・Turnstile障害時も、削除キーが有効なら本人削除は可能です。管理者は本人削除を復元できません。通常モデレーションは非表示とし、本文を消さず復元できます。通報だけでは自動非表示にしません。

## 認証・制限・障害

管理者APIは32文字以上の専用ランダムBearer token。Origin付き管理者要求を拒否し、公開CORSで管理者認証を許可しません。Windowsプロキシは固定HTTPSベースURLの許可された操作だけに接続し、redirectを追わず、10秒timeout・20MiB上限を設けます。ブラウザには設定済みかどうかだけを知らせます。

公開CORSは承認したHTTPS originだけ。POSTはJSONのみ、Cookieは使いません。TurnstileはWorkerでsiteverify・success・hostname・action・5分以内を検証します。検証は5秒、ケースmanifestは3秒、API全体は12秒、ブラウザは10秒でtimeoutします。D1処理が応答後に完了しても、同じ要求IDで安全に結果を再確認できます。

現在の初期制限（公開前の判断対象）：公開API全体4,000回/日、同一IPの読取60回/分・投稿3回/分/20回/日・通報5回/分/10回/日。削除は同じ投稿枠を使います。管理者操作は500回/日。IPは日単位HMACへ変換し、本文にIPを保存しません。毎日04:17 UTCのmaintenanceで期限切れcounterと24時間以上経過した通報者hashを消します（最大おおむね48時間）。通報理由・監査は管理上必要な履歴として残ります。

同一回線を使う家族などは制限を共有します。大量アクセスでD1やTurnstileが使えない場合は受付を停止し、推測で認証成功や投稿成功にしません。アプリのconsoleには秘密・IP・本文・SQLエラーをログ出力しません。Wranglerのobservabilityも初期無効です。Cloudflare自身のアクセスログ保持・プライバシー条件は契約時に別途確認してください。

## バックアップと復元

管理室「JSONバックアップを取得」はD1 batchの一貫した読取で全7管理表を取得し、SHA-256とHMAC署名をPythonで検証してからダウンロードします。失敗・途中応答・署名不一致を成功表示しません。rate counterは個人情報最小化のためバックアップ対象外で、通報者hashもバックアップ内では通報IDに置換します。16MiBを超えた場合は不完全なJSONを返さず、Cloudflare公式D1 exportへの切替を求めます。日常的には定期的・重要操作前に取得し、暗号化したPCフォルダー等へ保存してください。

バックアップは削除前の本文を含む場合があります。無期限保管を避け、暗号化・アクセス制限・保持期間を管理者が決めてください。本人削除後は古いバックアップの保持も見直してください。

復元ツールは本番へ接続できず、**新しいローカルSQLite**だけを作ります。旧バックアップと、現在DBから取得した新しい署名付きバックアップの両方が必要です。installation ID・registry・全ケース対応が違えば停止し、後から行われた本人削除と元投稿receiptを保持し、古いブラウザ要求の再送でも本文を復活させません。既存ローカルDBの上書きも拒否します。

```powershell
# 両JSONを信頼できる場所に置き、専用tokenを環境変数へ設定した上で実行
node comments/tools/restore.mjs backup.json current-signed-backup.json new-local.sqlite --approved-local-restore
```

署名secretを紛失・更新している場合やregistry変更後の古いバックアップは自動復元しません。管理者判断で安全な移行手順を別途作成してください。復元時には現在の削除記録が完全かを人間が確認する必要があります。ローカル復元試験後に本番へ適用するには**別途明示承認**が必要です。本番復元APIや「一発で本番へ上書き」ボタンは実装していません。

## 導入前に管理者が決めること

1. Cloudflareアカウント、Free/Paid、担当者、通知先。自動的な有料移行はしない。
2. WorkerのHTTPSホスト名、許可origin（GitHub Pages等）、Turnstile許可hostname。
3. コメント公開開始日、初期回数制限、禁止投稿・通報対応の運用。
4. 通報・監査・バックアップの保持期間、暗号化保管先、定期バックアップ担当。
5. 全66ケース対応と、将来の名前変更・統合・分割の判断方法。
6. Windows PC側への安全なコード更新・環境変数設定（このタスクの対象外）。

## 承認後の設定手順（本タスクでは実行禁止）

1. 別の隔離staging用アカウント/DBと鍵を準備。実データを流し込まず、まず合成データで検証する。
2. 管理者承認後にD1作成。`comments/wrangler.jsonc`のplaceholder database_id/nameを置き換える。local検証は必ず `--local`、remote bindingはfalseを維持。本番migrationは別承認後だけ `wrangler d1 migrations apply ... --remote` を実行する。
3. Turnstile widget作成。実hostnameを登録し、site keyだけを公開設定へ、secretをWorker secretへ。テスト用キーで本番受付を始めない。
4. Worker secretとしてADMIN_TOKEN、RATE_SECRET、TURNSTILE_SECRETを設定（それぞれ十分な別の乱数）。secretをwrangler.jsonc、Git、HTML、JSに書かない。
5. WorkersのMANIFEST_URLを固定Pages URLへ、TURNSTILE_HOSTNAME・ALLOWED_ORIGINS・REGISTRY_SHA256を承認値へ設定。migrationのmetadataと照合する。
6. まず全公開flagをfalseのままWorkerを公開（これ自体も別承認）。管理室接続・実D1 migration・Turnstile・CORS・削除・backup/restoreをstagingで検証する。本PRはローカルSQL＋D1 adapterでの検証であり、未接続の実Cloudflare動作を確認済みとはしていない。
7. Windowsのプロセス環境変数 `KINOKO_COMMENTS_API_URL` と `KINOKO_COMMENTS_ADMIN_TOKEN` を設定し、管理室を再起動。tokenはブラウザの設定欄へ入力しない。PR #134のPC更新作業は別タスクで下書きをバックアップしてから行う。
8. 公開を明示承認後、WorkerのRELEASE_APPROVALをapproved、READをtrue。さらに新規受付承認後WRITEをtrueにし、`comments/public-config.json`をenabled・api_url・site key・release_approvalの承認識別子で更新する専用PRを作る。GitHub Pages公開も別承認。**両側の解除が揃わなければ公開投稿は始まらない。**

Wranglerを使う場合は公式手順に従い、承認済みのWrangler 4系を隔離環境へインストールしてください。自動deployスクリプトやCloudflare credentialをCIへ加えていません。

## 費用の目安（2026-10-22公式資料確認）

個人ブログ規模なら、Workers Freeの10万リクエスト/日、D1 Freeの読取500万行/日・書込10万行/日・合計5GB、無料Turnstileの範囲内で**月額0米ドルを目指す構成**です。実利用・DBの行読取量次第なので無料を保証しません。無料枠超過時はD1が停止し、データが失われるわけではありません。有料Workersは最低月額5米ドルからで、従量・為替等は別です。有料化・費用発生は承認が必要です。

一次資料：
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/d1/platform/pricing/
- https://developers.cloudflare.com/turnstile/plans/
- https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
- https://developers.cloudflare.com/d1/worker-api/d1-database/
- https://developers.cloudflare.com/d1/best-practices/local-development/

## ローカル検証

Pythonの既存requirementsとrequirements-devを隔離環境へ導入。Node 24で以下を実行します。本番Cloudflare接続は不要です。

```text
python -m pytest -q
node --test comments/tests/api.test.mjs
python comments/tools/seed.py
node tests/browser/research_comments.cjs LOCAL_EVIDENCE_DIR
```

ブラウザ試験にはPlaywright/Chromiumを隔離導入し、PLAYWRIGHT_MODULE_PATHを指定します。Python fixtureとNodeのローカルWorker/D1 adapterだけを使用。ケース参照・写真の元情報は読み取り専用で、投稿・通報・削除は全て一時SQLiteの合成データに対して行います。
