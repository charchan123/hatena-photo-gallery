# PR #136の3不整合修正：未デプロイの隔離Access入口

## 結論と承認範囲

最新main `090eac16c25129695452a10a076532c752d8bd27` から独立ブランチで実装。PR #136 (`a7e2bc7…`) は資料専用Draftとして変更しない。本PRは未マージで停止し、本番コメント受付falseを維持する。Cloudflareリソース・secret・remote migration・deploy・契約・支払い登録は実施しない。

開始gh-pagesは `f38bd04d9c953c1af77ab58724b3880df6bb46f9`。前回 `35f2c858…` から日次生成のHEADは進んだが、portal-data全体はバイト単位同一。933写真/Best17/NEW14/研究66/退役7を独立再確認した。[baseline.json](baseline.json)に全写真レコード/ID-URL対応hash、66 active ID、保護ファイルhashを保存。写真ID重複なし・退役ID混入なし・紐付けpending0・公開config無効。

## 修正と安全性

1. 同一originの隔離UI/APIをstaging専用entryで配信。公開JSは変更せず、オフラインビルドしたstaging JSだけCookieをsame-originで送る。API origin不一致は送信前に拒否。redirect追従なし、HttpOnly CookieをJSで読まない。
2. 共通Workerにmanifest読取依存を注入。デフォルトの本番Pages固定URL/redirect拒否は維持。stagingは同梱のレビュー済み凍結manifest、registry正規化hash、D1 metadata、installation ID、全ID/アンカー/alias完全一致で照合し、本番Pagesへ接続しない。
3. localhost管理室のPythonに明示staging-access transport。固定HTTPS originへAccess service tokenの2ヘッダー＋既存管理Bearer。資格情報はUI・ログへ返さない。不完全設定、誤target、認証失敗、302、HTML応答、timeout、過大JSON、署名不一致で停止。localhost/Host/Origin/CSRF/下書き/Draft PR作成処理は変更なし。

認証は全経路（UI/config/manifest/static/API/admin/OPTIONS）でJWT署名・issuer・AUD・exp/iat/nbfを検証。joseをversion固定・lockfile付きで導入。RS256限定、鍵取得先は固定team、3秒timeout/redirect拒否/5分cache。Static Assetsのctx.accessに依存せず、run_worker_firstと静的許可リストを使用。アプリBearerだけでもAccessだけでも管理者操作できない。UI/APIは別origin配置不可。

DB照合・静的asset取得は各3秒timeout。本文・削除キー・JWT・メール・IP・秘密・生SQLエラーをログやエラーへ出さない。本番の制限・Turnstile検証・回数制限・本人削除・ID保護・バックアップ署名は既存回帰を維持。新しいmigrationや既存ケースの書換えはない。

## 検証

最終結果は [results.json](results.json)。ローカルブラウザは実Chromiumと既存localhost Python管理室、署名付き合成JWT、メモリ内SQLiteを使用。Access edge/JWKS/Turnstile応答は合成で、**実Cloudflare検証ではない**。実Workers/D1/Turnstile・Accessポリシー・Android実機・既存Windows PCの更新は未実施。

初回のPython全件実行では既存admin syncのsetup33件がOUTPUT_INTEGRITY_ERRORで停止した。安全条件は変更せず、個別20件と診断付き全件1107件が成功した後、最終の通常全件実行も1107件合格した。最終の通常実行・GitHub Actionsの結果を採用し、初回失敗を隠さない。

ブラウザ試験の開発中に、既存UIの「未確認のみ」フィルターが公式返信を除外すること、投稿成功文の表示より一覧取得完了が後になることを確認。試験は実UIに合わせて未確認フィルターを解除し、表示完了を待つように修正。製品の検証条件や非表示処理を緩めていない。

初回HEADのWindowsログには、新規テストがUTF-8の日本語JSを既定cp1252で読んだことによる1件の失敗があった。後続native command成功によりPowerShellの複数コマンドstepがsuccessを返していたため、workflowの緑だけでは合格としない。新規テストのread_textを全てUTF-8明示へ修正し、このコメント回帰workflowだけrun shellをWindows/Ubuntuともfail-fastなbashに統一した。テスト削除・skip・条件緩和は行わず、修正後の最終HEADで全CIを再検証する。公開workflowや他のActions保守更新は変更しない。

### 比較・画面証跡

[images/](images/)にPC1280/900、1列680、スマートフォン390/320、管理室成功/認証エラーを保存する。同じ66ケースと合成コメントだけを使用する。秘密やユーザーのCloudflareダッシュボード画像は含めない。Cookie省略時403、同一origin送信時成功はブラウザの実fetchで数値検証する。

## ファイルと役割

- `comments/worker.mjs`：従来動作を既定値としてmanifest loaderだけ注入。
- `comments/staging/{worker.mjs,access.mjs,manifest.json,build.py,wrangler.example.jsonc}`：隔離入口、署名検証、凍結ID、合成UIビルド、閉鎖テンプレート。
- `comments/package.json` / `package-lock.json`：検証ライブラリの固定依存。
- `admin/comments_client.py`：サーバー専用Access transport、固定target、エラー処理。
- `comments/tests/staging*.mjs` / `tests/test_comments_staging.py` / `tests/browser/comments_staging*`：合成認証・DB・Cookie・プロキシ・画面・誤設定回帰。
- `.github/workflows/research-comments.yml`：既存の読取専用Windows/Ubuntu試験へ今回分を追加。公開workflowやActionsのNode保守更新は対象外。
- `.gitignore`：node_modules/生成検証UI/ローカル実値設定/secret/ローカルWranglerを除外。
- `docs/research-comments-staging-access.md` と既存導入資料の案内リンク：構成、設定、承認境界、Zero Trustの操作手順。
- 本監査フォルダー：基準、結果、画面証跡。

## セキュリティレビュー・残る確認

署名のないheaderやctxの存在だけで許可しない。nonce/URLで認証を迂回しない。一般JSにservice tokenを渡さず、Cookieセッションと管理Bearerを混同しない。Unknown origin/preview・別DB・不一致registry・追加aliasを拒否する。本番の公開スイッチを兼用しない。鍵回転は既存cache方針を使い、Access外周の短期service token失効・限定Service Authポリシーも実環境で確認する必要がある。

導入前に承認済みstaging hostname/AUD/installation IDを確定し、Access外周を全URLに適用した状態での匿名拒否を確認する。Wranglerテンプレートは意図的に未設定で、現状のまま動作・公開できない。公開前に無料枠とWorker-first配信、Turnstile実hostname/action/再利用拒否、実D1の障害を17項目試験表で確認する。これらは今回のローカル合格で代替しない。

Zero TrustはWelcomeまで。画面確認・Free選択肢調査のみ承認済み、チーム/組織作成・契約確定・カード入力・Accessアプリ作成は未承認。Freeでも公式手順では支払い情報が必要。支払い画面で停止し、入力しない。[具体的手順](../../docs/research-comments-staging-access.md#zero-trust-free次に管理者が確認する操作)を参照。

最終commit SHA・Draft PR URL・最終HEADのCI URL/結果は、自己参照による追加コミットを避けるためDraft PR本文に記録する。main/gh-pages/PR #136の最終照合も同本文に追補する。
