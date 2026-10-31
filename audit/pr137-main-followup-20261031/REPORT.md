# PR #137：最新main統合・Cloudflare非公開検証の準備

2026-10-31 JST。**Draft・未マージ。本番公開・Cloudflare接続/作成/secret/remote migration/deploy/契約/支払操作なし。** 最終HEAD/tree/CIと停止時のrefsはPR #137本文を正本として追記する。検証結果のためだけに同じコードを再コミットする自己参照は避ける。

## 開始状態と統合

- main: `b913ad7b07f689f14f5c8dcecea11b7c99363827`
- gh-pages: `c95280a6265214945de11d5d438684f5ca36837b`
- #137 HEAD: `1766b1693ec87a2945b98abc5456f48fc9a13026`、Draft/open/unmerged、3 ahead / 15 behind。
- #136 HEAD: `a7e2bc7fe2103b0f24f1feea600b294d4d6a41b8`、変更しない。
- #135 merge `090eac16c25129695452a10a076532c752d8bd27` と39ファイル実装、#136の5ファイル計画、#137の33ファイル・既存監査・CI履歴を再利用。

通常の2親mergeでmainの15コミット（#138正式トップ、#139 LightGallery/スター/写真復帰、#140 WebP差し替え）を取り込んだ。競合0。片側ファイルへの上書き、rebase、force、main/gh-pages pushなし。

merge commit `f784800f63cdf402096910a3c7300bfdbfe41419` は親が #137開始HEAD と開始main。ローカルmerge treeとGitHub上に作成したtree `be72b92d2831bb21f1c52195f2116b85ff9b91ff` の一致を確認し、GitHub pluginのexpected_sha付き・force=falseのref更新で既存PRブランチへ保存した。ローカルgit HTTPS pushは認証なしのため使用できず、履歴の同じ通常mergeをGitHubのGit object APIで保存した。認証情報を探索・複製していない。

## 実行コードの保持・保護

[protection.json](protection.json)の313ソースを最新mainと比較。差分として認める既存変更は、#137開始HEADとバイト一致する `.gitignore`、`admin/comments_client.py`、`comments/worker.mjs` だけ（依存packageは#137の新規追加）。main側も#135時点と一致することを二重条件にし、mainの新変更を旧PRの許可で隠さない。stagingの5実装/設定ファイルとpackage/lockも開始HEADとバイト一致。

特にmain.py、CSS/WebP7枚、LightGallery、record-stars、正式トップ、日次workflow、同期/削除ゲート、管理室localhost/Host/Origin/CSRF/下書き/復元/PR作成、手動EXIF、同定・対応表は今回改変しない。Workerの公開READ/WRITE、release、workers.dev/preview、公開configは閉鎖のまま。

保護数値は933写真 / Best17 / NEW14 / 研究66 / 退役7 / master141 / sources419 / WebP7。公開Bestのselection ID集合、master/sources全体、全ケース・アンカー・registry SHAと凍結/公開manifestを独立比較。pending0。写真ID/URL/EXIFを含むportal全体のhashを保存した。

旧#137監査のgh-pages `f38bd04…` と現在のportal hashは異なる。[履歴比較](published-history-difference.json)では写真ID集合、src・capture/EXIF等の全非article項目は一致し、差分は933件のarticle.article_pathだけ。例 articles/article_8.html→article_9.html。記事ID・元URLは同一で、生成記事リンクの再採番と確認した。ケースの安定ID照合はarticle_id＋全写真IDを使うため、この番号を恒久IDとして流用しない。今回この公開データを書き換えていない。

## 今回の追加変更と理由

| ファイル | 変更理由 |
|---|---|
| tests/browser/comments_integration_protection.py | 古いPR専用基準でなく最新main全体を保護し、既存#137の正確なバイトだけ許可。凍結registry・公開データ・WebPも照合 |
| tests/test_comments_preflight.py | migration順序/全アンカー/6 triggers/FK/空本文、seed再適用拒否とinstallation固有性、保護許可の否定試験3件 |
| comments/tests/staging.test.mjs | 認証前拒否試験を研究CSS・staging CSS・未知assetにも拡大。既存試験は維持 |
| tests/browser/ai_artwork_fixture.py | mainが既に持つWebPを比較用beforeから削除しない。既存HTML完全一致・全参照・画像寸法条件を維持し、保護比較へ上の厳密ゲートを適用 |
| tests/browser/shared_lightgallery_fixture.py | 公開後も旧dialog/スター間隔の厳しい比較を維持するためbeforeだけを#139直前の公開SHAに固定。afterは最新公開データ＋現在コード。最新mainの保護比較は別ゲートで継続 |
| .github/workflows/{ai-artwork,shared-lightgallery,hatena-release,layout-tuning}.yml | staging変更でmainの表示回帰も動くようpathsを追加。sharedの履歴専用保護比較は最新main全体の厳密比較に置換（履歴スクリプト自体は保存） |
| .github/workflows/research-comments.yml | 両OSで新規preflight・保護比較、固定Wranglerのdry-run、保護JSONのartifact保存。Cloudflare資格情報・deployは追加しない |
| docs/research-comments-staging-{plan,access,runbook}.md | #136の計画を履歴として再利用し、現契約未確認、最新版公式費用、承認表、10段階手順、閉鎖条件を明文化 |
| docs/research-comments-roadmap.md | #136の最終バイトをそのまま収録。後続A〜Cは設計のみで実装しない |
| 本audit | 最新保護・ローカル結果・失敗履歴・実環境未実施表を保存 |

## ローカル検証と限界

- 統合後の通常Python全件：1,128 PASS。今回追加3件を含む最終全件結果は[python-local.txt](python-local.txt)。focused 40件PASS。
- Worker/API/SQLite/実JWT署名/バックアップ・ローカル復元：24 PASS、fail/cancel/skip/todo 0。[worker-local.txt](worker-local.txt)。認証前asset試験を拡大済み。
- Node既存JavaScript全体：86 PASS、fail/cancel/skip/todo 0。[javascript-local.txt](javascript-local.txt)。全JS/mjsの構文検証と変更Python compile成功。
- 固定Wrangler 4.151.3の閉鎖テンプレート `deploy --dry-run` 成功。[wrangler-dry-run.txt](wrangler-dry-run.txt)。Cloudflare資格情報なし、metrics無効、upload/migrationなし。これは実環境の成立証明ではない。
- 最新公開入力から333 HTMLを再生成しmainとのバイト一致、旧表示参照0、7用途・全階層の参照を照合。[artwork-generation.json](artwork-generation.json)。同期や公開は実行していない。
- ローカルChromiumの取得はzip破損で失敗し、ローカルブラウザ再試験は実行できなかった。別版取得も失敗。環境のpackage導入も権限上成立しなかった。合格扱いにせず、最終HEADのGitHub ActionsでUbuntu/Windowsの実Chromiumを検証する。実Android・本人Windows端末・Cloudflare本体は未実施。
- 最初のローカル全件試験はsetup error表示を含み正常終了レポートを取得できなかった。ゲート・テストを変えず、該当sync 34件を個別実行してPASS、通常全件1,128 PASSを確認。初回原因は確定していない。[attempts.json](attempts.json)に未成功を残す。最終合格は最終実行ログとCIを根拠にする。

テストの削除・skip・安全条件緩和なし。旧PRのCI成功を最終HEADの代用にしない。最終CIの各job・重要step・ログはPR本文に記録する。実Cloudflare試験は[inherited-test-matrix.json](inherited-test-matrix.json)の17項目も含め未実施であり、模擬合格から状態を昇格させない。

## Cloudflareの準備・次の判断

[runbook](../../docs/research-comments-staging-runbook.md)が現在の手順。専用Worker/D1/widget/Access application・限定Service Auth/短期token/3 secretsを提案し、実アカウント・Free・名前・費用・権限の読み取り確認後に別承認を取る。今回ログイン要求も実接続も行わない。

WorkerとUI/APIは同一staging origin、JWTの署名/issuer/AUD/期限、全パスWorker-first、D1 installation/registry/全アンカー/全alias一致を必須とする。localhostのService Auth tokenと管理Bearerは別で、秘密をブラウザへ渡さない。preview/version/別hostの回避経路も実証対象。

無料枠は公式一次資料から2026-10-31に再確認。0円目標だが現契約・支払/追加契約・共有利用量未確認につき無条件保証しない。Workers Free 10msでのRS256＋全registry照合性能も実測待ち。費用・認証・DB整合に疑義があれば停止し、Paid移行や認証緩和で通さない。

**停止点：PR #137へ準備を保存し最終CIを確認した時点。Draft・未マージ。本番ブログ/Pages/受付設定、PR #136、Cloudflare契約・リソース・秘密に変更なし。**
